from ..dominio import assinatura_rsa
from ..dominio.erros import AcessoNegado, DadosInvalidos
from ..dominio.assinaturas_pdf import EstadoAssinatura, ResultadoAssinatura
from ..dominio.protocolos import SITUACOES_LISTAGEM_PROTOCOLO, validar_documento_pdf
from ..dominio.usuarios import ChefeLaboratorio


class ServicoProtocolos:
    """Coordena envio, assinatura pelo autor e validação pelo Chefe."""

    def __init__(self, transacao, autenticacao):
        self._transacao = transacao
        self._autenticacao = autenticacao

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

    def listar(self, token, *, situacao=None):
        if situacao is not None and situacao not in SITUACOES_LISTAGEM_PROTOCOLO:
            raise DadosInvalidos("Selecione uma situação válida para os protocolos.")
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            return tx.protocolos.listar(ator.laboratorio_id, situacao=situacao)

    def consultar(self, token, protocolo_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            protocolo = self._protocolo(tx, protocolo_id, ator.laboratorio_id)
            equipamentos = (
                tx.recursos.listar_equipamentos(ator.laboratorio_id)
                if isinstance(ator, ChefeLaboratorio) and protocolo.validado else []
            )
            return protocolo, equipamentos

    def cadastrar(self, token, *, titulo, nome_arquivo, pdf_original):
        titulo, nome_arquivo = validar_documento_pdf(titulo, nome_arquivo, pdf_original)
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            tx.contexto(ator.id, "Envio de protocolo para assinatura no sistema")
            return tx.protocolos.criar(ator.laboratorio_id, ator.id, titulo, nome_arquivo, pdf_original)

    def assinar(self, token, protocolo_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            tx.usuarios.buscar_por_id(ator.id, bloquear=True)
            tx.protocolos.bloquear_laboratorio(ator.laboratorio_id)
            ator = self._ator(tx, token)
            protocolo = self._protocolo(tx, protocolo_id, ator.laboratorio_id)
            if protocolo.autor_id != ator.id:
                raise AcessoNegado("Somente o autor pode assinar este protocolo.")
            if protocolo.assinado:
                raise DadosInvalidos("Este protocolo já foi assinado.")
            arquivo = tx.protocolos.arquivo(protocolo_id, ator.laboratorio_id)
            if arquivo is None:
                raise DadosInvalidos("Arquivo do protocolo não encontrado.")
            chave = tx.protocolos.chave_autor(ator.id, ator.laboratorio_id)
            if chave is None:
                chave = assinatura_rsa.gerar_chave()
                tx.protocolos.salvar_chave_autor(ator.id, ator.laboratorio_id, *chave)
            modulo, publico, privado = chave
            resumo = assinatura_rsa.resumo_sha256(arquivo[1])
            assinatura = assinatura_rsa.assinar_resumo(resumo, modulo, publico, privado)
            tx.contexto(ator.id, "Assinatura RSA com SHA-256 pelo autor autenticado")
            tx.protocolos.registrar_assinatura_rsa(ator.id, protocolo_id, assinatura, resumo)

    @staticmethod
    def _verificar(tx, protocolo):
        if not protocolo.assinado:
            return ResultadoAssinatura(EstadoAssinatura.SEM_ASSINATURA,
                                       detalhe="O autor ainda precisa assinar este protocolo.")
        evidencia = tx.protocolos.evidencia_assinatura(protocolo.id, protocolo.laboratorio_id)
        if evidencia is None:
            return ResultadoAssinatura(
                EstadoAssinatura.INDETERMINADA,
                detalhe="Este registro usa a assinatura anterior. Envie uma nova versão e assine pelo sistema.",
            )
        arquivo = tx.protocolos.arquivo(protocolo.id, protocolo.laboratorio_id)
        if arquivo is None:
            return ResultadoAssinatura(EstadoAssinatura.INDETERMINADA, detalhe="Arquivo indisponível.")
        resumo = assinatura_rsa.resumo_sha256(arquivo[1])
        valida = resumo == evidencia["resumo"] and assinatura_rsa.verificar_resumo(
            resumo, evidencia["assinatura"], evidencia["modulo"], evidencia["expoente_publico"],
        )
        return ResultadoAssinatura(
            EstadoAssinatura.VALIDA if valida else EstadoAssinatura.INVALIDA,
            (protocolo.autor_nome,),
            "Assinatura RSA e resumo SHA-256 conferidos." if valida
            else "A assinatura ou o resumo não corresponde ao PDF armazenado.",
            assinatura_rsa.POLITICA_ASSINATURA,
        )

    def verificar_assinatura(self, token, protocolo_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            return self._verificar(tx, self._protocolo(tx, protocolo_id, ator.laboratorio_id))

    def validar(self, token, protocolo_id, *, identidade_conferida=False):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            if not isinstance(ator, ChefeLaboratorio):
                raise AcessoNegado("Somente o Chefe pode validar protocolos.")
            tx.protocolos.bloquear_laboratorio(ator.laboratorio_id)
            protocolo = self._protocolo(tx, protocolo_id, ator.laboratorio_id)
            if protocolo.validado:
                raise DadosInvalidos("Este protocolo já está validado.")
            if not self._verificar(tx, protocolo).valida:
                raise DadosInvalidos("O protocolo precisa de uma assinatura válida do autor.")
            if identidade_conferida is not True:
                raise DadosInvalidos("Confira o conteúdo e a autoria antes de validar o protocolo.")
            tx.contexto(ator.id, "Validação do conteúdo e da autoria pelo Chefe após verificar RSA")
            tx.protocolos.validar(ator.id, protocolo_id)

    def vincular(self, token, protocolo_id, equipamento_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            if not isinstance(ator, ChefeLaboratorio):
                raise AcessoNegado("Somente o Chefe pode vincular protocolos a equipamentos.")
            tx.protocolos.bloquear_laboratorio(ator.laboratorio_id)
            protocolo = self._protocolo(tx, protocolo_id, ator.laboratorio_id)
            if not protocolo.validado or not self._verificar(tx, protocolo).valida:
                raise DadosInvalidos("Vincule um protocolo assinado no sistema e validado pelo Chefe.")
            if type(equipamento_id) is not int or equipamento_id <= 0:
                raise DadosInvalidos("Selecione um equipamento válido.")
            if not any(e.id == equipamento_id for e in tx.recursos.listar_equipamentos(ator.laboratorio_id)):
                raise DadosInvalidos("Equipamento não encontrado neste laboratório.")
            tx.contexto(ator.id, "Vínculo entre protocolo e equipamento")
            tx.protocolos.vincular(protocolo_id, equipamento_id, ator.laboratorio_id, ator.id)

    def baixar(self, token, protocolo_id):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            self._protocolo(tx, protocolo_id, ator.laboratorio_id)
            arquivo = tx.protocolos.arquivo(protocolo_id, ator.laboratorio_id)
            if arquivo is None:
                raise DadosInvalidos("Arquivo do protocolo não encontrado.")
            return arquivo
