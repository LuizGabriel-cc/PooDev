from ..dominio.erros import AcessoNegado, DadosInvalidos
from ..dominio.assinaturas_pdf import (
    EstadoAssinatura, ResultadoAssinatura, nomes_compativeis,
)
from ..dominio.protocolos import validar_documento_pdf
from ..dominio.usuarios import ChefeLaboratorio


class ServicoProtocolos:
    """Cadastro e validação de protocolos sob a identidade da sessão autenticada."""

    def __init__(self, transacao, autenticacao, verificador=None):
        self._transacao = transacao
        self._autenticacao = autenticacao
        self._verificador = verificador

    def _ator(self, tx, token):
        ator = self._autenticacao.identificar_na_transacao(tx, token)
        if ator is None:
            raise AcessoNegado("Entre novamente para continuar.")
        return ator

    @staticmethod
    def _protocolo(tx, protocolo_id, laboratorio_id):
        if type(protocolo_id) is not int or protocolo_id <= 0:
            raise DadosInvalidos("Selecione um protocolo válido.")
        protocolo = tx.protocolos.buscar(protocolo_id, laboratorio_id)
        if protocolo is None:
            raise DadosInvalidos("Protocolo não encontrado neste laboratório.")
        return protocolo

    def listar(self, token):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            return tx.protocolos.listar(ator.laboratorio_id)

    def consultar(self, token, protocolo_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            protocolo = self._protocolo(tx, protocolo_id, ator.laboratorio_id)
            equipamentos = (
                tx.recursos.listar_equipamentos(ator.laboratorio_id)
                if isinstance(ator, ChefeLaboratorio) and protocolo.validado and protocolo.pdf_verificado
                else []
            )
            return protocolo, equipamentos

    def cadastrar(self, token, *, titulo, nome_arquivo, pdf_original):
        """Recebe PDF assinado externamente e registra somente se a verificação passar.

        A integridade criptográfica e a confiança são analisadas pela camada
        de infraestrutura. A compatibilidade de nomes é um requisito para o
        cadastro. O Chefe confirma a identidade na validação administrativa.
        """
        titulo, nome_arquivo = validar_documento_pdf(titulo, nome_arquivo, pdf_original)
        # Evita processar criptografia de documentos enviados por sessões inválidas.
        # A sessão é conferida novamente antes de gravar, caso tenha sido revogada.
        with self._transacao() as tx:
            self._ator(tx, token)
        if self._verificador is None:
            raise DadosInvalidos("Verificação de assinaturas não está configurada.")
        resultado = self._verificador.verificar(pdf_original)
        if not resultado.valida:
            raise DadosInvalidos(
                f"Assinatura não aceita: {resultado.detalhe or resultado.estado.value}"
            )
        if not resultado.politica:
            raise DadosInvalidos("A política usada para verificar a assinatura não foi identificada.")
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            if not any(nomes_compativeis(ator.nome, nome) for nome in resultado.signatarios):
                raise DadosInvalidos(
                    "O nome no certificado não corresponde ao autor cadastrado. "
                    "Confira a identidade antes de enviar o documento."
                )
            tx.contexto(ator.id, "Cadastro de protocolo com assinatura digital verificada")
            protocolo_id = tx.protocolos.criar(
                ator.laboratorio_id, ator.id, titulo, nome_arquivo, pdf_original
            )
            tx.protocolos.registrar_assinatura_pdf_verificada(ator.id, protocolo_id, resultado.politica)
            return protocolo_id

    def assinar(self, token, protocolo_id):
        raise DadosInvalidos(
            "Não é possível assinar pelo PooDev. Assine no gov.br e envie o PDF assinado."
        )

    def verificar_assinatura(self, token, protocolo_id):
        """Retorna a situação técnica atual sem marcar o PDF como assinado."""
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            protocolo = self._protocolo(tx, protocolo_id, ator.laboratorio_id)
            if not protocolo.pdf_verificado:
                return ResultadoAssinatura(
                    EstadoAssinatura.INDETERMINADA,
                    detalhe="O registro não tem evidência de verificação digital no cadastro."
                )
            arquivo = tx.protocolos.arquivo(protocolo_id, ator.laboratorio_id)
            if arquivo is None or self._verificador is None:
                return ResultadoAssinatura(
                    EstadoAssinatura.INDETERMINADA,
                    detalhe="Não foi possível repetir a verificação técnica neste momento."
                )
            resultado = self._verificador.verificar(arquivo[1])
            if resultado.valida and not any(
                nomes_compativeis(protocolo.autor_nome, nome)
                for nome in resultado.signatarios
            ):
                return ResultadoAssinatura(
                    EstadoAssinatura.AUTORIA_DIVERGENTE, resultado.signatarios,
                    "A assinatura é criptograficamente válida, mas o nome do certificado "
                    "não corresponde ao autor cadastrado.", resultado.politica
                )
            return resultado

    def validar(self, token, protocolo_id, *, identidade_conferida=False):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            if not isinstance(ator, ChefeLaboratorio):
                raise AcessoNegado("Somente o Chefe pode validar protocolos.")
            protocolo = self._protocolo(tx, protocolo_id, ator.laboratorio_id)
            if not protocolo.pdf_verificado:
                raise DadosInvalidos("Envie o PDF assinado em um novo protocolo antes da validação.")
            if protocolo.validado:
                raise DadosInvalidos("Este protocolo já está validado.")
            if identidade_conferida is not True:
                raise DadosInvalidos("Confirme a identidade do signatário antes de validar o protocolo.")
            arquivo = tx.protocolos.arquivo(protocolo_id, ator.laboratorio_id)
            if arquivo is None or self._verificador is None:
                raise DadosInvalidos("Não foi possível conferir o PDF assinado.")
            resultado = self._verificador.verificar(arquivo[1])
            if not resultado.valida or not any(
                nomes_compativeis(protocolo.autor_nome, nome)
                for nome in resultado.signatarios
            ):
                raise DadosInvalidos(
                    "Assinatura não confirmada ou signatário diferente do autor."
                )
            tx.contexto(ator.id, "Validação administrativa após conferência de assinatura e identidade")
            tx.protocolos.validar(ator.id, protocolo_id)

    def vincular(self, token, protocolo_id, equipamento_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            if not isinstance(ator, ChefeLaboratorio):
                raise AcessoNegado("Somente o Chefe pode vincular protocolos a equipamentos.")
            protocolo = self._protocolo(tx, protocolo_id, ator.laboratorio_id)
            if not protocolo.validado or not protocolo.pdf_verificado:
                raise DadosInvalidos("Vincule um protocolo com assinatura digital verificada e validação do Chefe.")
            if type(equipamento_id) is not int or equipamento_id <= 0:
                raise DadosInvalidos("Selecione um equipamento válido.")
            if not any(
                e.id == equipamento_id
                for e in tx.recursos.listar_equipamentos(ator.laboratorio_id)
            ):
                raise DadosInvalidos("Equipamento não encontrado neste laboratório.")
            tx.contexto(ator.id, "Vínculo entre protocolo e equipamento")
            tx.protocolos.vincular(
                protocolo_id, equipamento_id, ator.laboratorio_id, ator.id
            )

    def baixar(self, token, protocolo_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            self._protocolo(tx, protocolo_id, ator.laboratorio_id)
            arquivo = tx.protocolos.arquivo(protocolo_id, ator.laboratorio_id)
            if arquivo is None:
                raise DadosInvalidos("Arquivo do protocolo não encontrado.")
            return arquivo
