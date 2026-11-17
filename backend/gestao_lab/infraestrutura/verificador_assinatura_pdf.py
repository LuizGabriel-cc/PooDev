"""Confere assinaturas PDF com uma cadeia configurada, sem acesso à rede."""
from io import BytesIO
import logging
from pathlib import Path

from ..dominio.assinaturas_pdf import EstadoAssinatura, ResultadoAssinatura


LOG = logging.getLogger(__name__)
POLITICA_PDF = "poodev-pades-offline-v1"


def _carregar_crl(caminho):
    from asn1crypto import crl, pem

    dados = caminho.read_bytes()
    if pem.detect(dados):
        tipo, _, dados = pem.unarmor(dados)
        if tipo not in {"X509 CRL", "CRL"}:
            raise ValueError("Tipo PEM inválido para uma lista de revogação.")
    return crl.CertificateList.load(dados, strict=True)


def _falha_criptografica(status):
    if not status.intact or not status.valid:
        return "A assinatura ou o carimbo de tempo não corresponde aos bytes do PDF."
    if status.revoked:
        return "Um certificado da cadeia foi revogado."
    return None


class VerificadorAssinaturaPDF:
    def __init__(self, caminhos_raizes=(), caminhos_intermediarios=(), caminhos_crls=()):
        self._caminhos_raizes = tuple(Path(c) for c in caminhos_raizes)
        self._caminhos_intermediarios = tuple(Path(c) for c in caminhos_intermediarios)
        self._caminhos_crls = tuple(Path(c) for c in caminhos_crls)

    def verificar(self, arquivo: bytes) -> ResultadoAssinatura:
        try:
            from pyhanko.keys import load_certs_from_pemder
            from pyhanko.pdf_utils.reader import PdfFileReader
            from pyhanko.sign.diff_analysis import ModificationLevel
            from pyhanko.sign.fields import SigSeedSubFilter, enumerate_sig_fields
            from pyhanko.sign.validation import validate_pdf_signature, validate_pdf_timestamp
            from pyhanko.sign.validation.dss import DocumentSecurityStore
            from pyhanko.sign.validation.errors import NoDSSFoundError
            from pyhanko.sign.validation.settings import KeyUsageConstraints
            from pyhanko.sign.validation.status import SignatureCoverageLevel
            from pyhanko_certvalidator import ValidationContext
        except ImportError:
            return ResultadoAssinatura(
                EstadoAssinatura.INDETERMINADA,
                detalhe="Instale a dependência pyHanko antes de validar assinaturas."
            )
        if not self._caminhos_raizes:
            return ResultadoAssinatura(
                EstadoAssinatura.INDETERMINADA,
                detalhe="Configure os certificados das autoridades confiáveis para validar o PDF."
            )
        try:
            raizes = list(load_certs_from_pemder([str(c) for c in self._caminhos_raizes]))
            intermediarias = list(load_certs_from_pemder([str(c) for c in self._caminhos_intermediarios]))
            listas_revogacao = [_carregar_crl(caminho) for caminho in self._caminhos_crls]
            if not raizes:
                raise ValueError("Nenhuma autoridade confiável foi carregada.")
        except (OSError, ValueError, TypeError) as erro:
            LOG.warning("Configuração de confiança PDF inválida: %s", type(erro).__name__)
            return ResultadoAssinatura(
                EstadoAssinatura.INDETERMINADA,
                detalhe="Confira os arquivos de certificados e listas de revogação configurados."
            )

        try:
            leitor = PdfFileReader(BytesIO(arquivo))
            filtros_suportados = {filtro.value for filtro in SigSeedSubFilter}
            if any(
                objeto.get_object().get("/SubFilter") not in filtros_suportados
                for _, objeto, _ in enumerate_sig_fields(leitor, filled_status=True)
            ):
                return ResultadoAssinatura(
                    EstadoAssinatura.INDETERMINADA,
                    detalhe="O PDF contém uma assinatura em formato não reconhecido."
                )
            assinaturas = leitor.embedded_regular_signatures
            carimbos = leitor.embedded_timestamp_signatures
            if len(assinaturas) + len(carimbos) != len(leitor.embedded_signatures):
                return ResultadoAssinatura(
                    EstadoAssinatura.INDETERMINADA,
                    detalhe="O PDF contém um tipo de assinatura não reconhecido."
                )
            if not assinaturas:
                return ResultadoAssinatura(
                    EstadoAssinatura.SEM_ASSINATURA, detalhe="O PDF não contém assinatura digital de um autor."
                )

            try:
                dss = DocumentSecurityStore.read_dss(leitor)
            except NoDSSFoundError:
                dss = None

            # Cada contexto é independente. O DSS só fornece dados auxiliares,
            # e o pyHanko confere a autenticidade e a vigência das listas e respostas.
            configuracao = dict(
                trust_roots=raizes, other_certs=intermediarias, crls=listas_revogacao,
                allow_fetching=False, revocation_mode="hard-fail"
            )

            def novo_contexto():
                if dss is not None:
                    return dss.as_validation_context(configuracao)
                return ValidationContext(**configuracao)

            nomes = []
            inconclusiva = False
            campos_assinatura = {assinatura.field_name for assinatura in assinaturas}
            for assinatura in assinaturas:
                status = validate_pdf_signature(
                    assinatura, signer_validation_context=novo_contexto(),
                    key_usage_settings=KeyUsageConstraints(key_usage={"digital_signature"})
                )
                falha = _falha_criptografica(status)
                for carimbo_assinatura in (status.timestamp_validity, status.content_timestamp_validity):
                    if carimbo_assinatura is not None:
                        falha = falha or _falha_criptografica(carimbo_assinatura)
                if falha:
                    return ResultadoAssinatura(EstadoAssinatura.INVALIDA, detalhe=falha)
                if (
                    status.coverage < SignatureCoverageLevel.ENTIRE_REVISION
                    or status.docmdp_ok is False
                    or status.modification_level in {ModificationLevel.ANNOTATIONS, ModificationLevel.OTHER}
                    or (
                        status.modification_level == ModificationLevel.FORM_FILLING
                        and status.diff_result.changed_form_fields - campos_assinatura
                    )
                ):
                    return ResultadoAssinatura(
                        EstadoAssinatura.INVALIDA,
                        detalhe="Há uma revisão incompleta ou uma alteração de conteúdo após a assinatura."
                    )
                if not status.bottom_line or status.modification_level is None:
                    inconclusiva = True
                    continue
                nome = status.signing_cert.subject.native.get("common_name", "")
                nomes.append(str(nome).split(":", 1)[0].strip())

            for carimbo in carimbos:
                status = validate_pdf_timestamp(carimbo, validation_context=novo_contexto())
                falha = _falha_criptografica(status)
                if falha:
                    return ResultadoAssinatura(EstadoAssinatura.INVALIDA, detalhe=falha)
                if (
                    status.coverage < SignatureCoverageLevel.ENTIRE_REVISION
                    or status.modification_level in {ModificationLevel.ANNOTATIONS, ModificationLevel.OTHER}
                ):
                    return ResultadoAssinatura(
                        EstadoAssinatura.INVALIDA, detalhe="O carimbo de tempo não cobre uma revisão válida."
                    )
                if not status.trusted or status.modification_level is None:
                    inconclusiva = True

            if inconclusiva:
                return ResultadoAssinatura(
                    EstadoAssinatura.INDETERMINADA,
                    detalhe="Não foi possível confirmar a confiança das assinaturas. "
                    "Confira a cadeia, a vigência dos certificados e as listas de revogação exigidas."
                )
            return ResultadoAssinatura(
                EstadoAssinatura.VALIDA, tuple(nomes),
                "Assinaturas verificadas com a cadeia e as informações de revogação exigidas pela política local.",
                POLITICA_PDF
            )
        except Exception as erro:
            LOG.warning("Não foi possível validar assinatura PDF: %s", type(erro).__name__)
            return ResultadoAssinatura(
                EstadoAssinatura.INDETERMINADA, detalhe="Não foi possível concluir a verificação do PDF."
            )
