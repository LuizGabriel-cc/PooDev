from ..dominio.erros import AcessoNegado, DadosInvalidos
from ..dominio.usuarios import Aluno, ChefeLaboratorio, texto_obrigatorio


ESTADOS_MANUTENCAO = {
    "DISPONIVEL": "Disponível",
    "MANUTENCAO": "Em manutenção",
    "DANIFICADO": "Danificado",
}
TIPOS_OCORRENCIA = {"DANO": "Dano", "FALTA_ESTOQUE": "Falta de estoque", "OUTRO": "Outro"}


class ServicoOperacoes:
    def __init__(self, transacao, autenticacao):
        self._transacao = transacao
        self._autenticacao = autenticacao

    def _ator(self, tx, token, perfil=None):
        ator = self._autenticacao.identificar_na_transacao(tx, token)
        if ator is None:
            raise AcessoNegado("Entre novamente para continuar.")
        if perfil is not None and not isinstance(ator, perfil):
            raise AcessoNegado("Seu perfil não permite esta operação.")
        return ator

    def listar_restricoes(self, token):
        with self._transacao() as tx:
            ator = self._ator(tx, token, (Aluno, ChefeLaboratorio))
            chefe = isinstance(ator, ChefeLaboratorio)
            lab = ator.laboratorio_id
            aluno = None if chefe else ator.id
            return (
                tx.operacoes.proibicoes(lab, aluno), tx.operacoes.pedidos(lab, aluno),
                tx.operacoes.alunos_ativos(lab) if chefe else [],
                tx.operacoes.equipamentos(lab) if chefe else [],
            )

    def proibir(self, token, *, aluno, equipamento, motivo):
        motivo = texto_obrigatorio(motivo, "Motivo", 500)
        with self._transacao() as tx:
            chefe = self._ator(tx, token, ChefeLaboratorio)
            if not tx.operacoes.proibir(chefe, aluno, equipamento, motivo):
                raise DadosInvalidos("Selecione um aluno ativo e um equipamento do laboratório.")

    def solicitar(self, token, *, proibicao, justificativa):
        justificativa = texto_obrigatorio(justificativa, "Justificativa", 500)
        with self._transacao() as tx:
            aluno = self._ator(tx, token, Aluno)
            if not tx.operacoes.solicitar(aluno, proibicao, justificativa):
                raise AcessoNegado("Selecione uma proibição ativa da sua conta.")

    def responder(self, token, *, pedido, aprovar, resposta):
        if type(aprovar) is not bool:
            raise DadosInvalidos("Selecione uma decisão.")
        resposta = texto_obrigatorio(resposta, "Resposta", 500)
        with self._transacao() as tx:
            chefe = self._ator(tx, token, ChefeLaboratorio)
            if not tx.operacoes.responder(chefe, pedido, aprovar, resposta):
                raise DadosInvalidos("Selecione um pedido pendente do laboratório.")

    def listar_manutencao(self, token):
        with self._transacao() as tx:
            chefe = self._ator(tx, token, ChefeLaboratorio)
            return tx.operacoes.equipamentos(chefe.laboratorio_id)

    def mudar_estado(self, token, *, equipamento, estado, motivo):
        if estado not in ESTADOS_MANUTENCAO:
            raise DadosInvalidos("Selecione um estado de manutenção válido.")
        motivo = texto_obrigatorio(motivo, "Motivo", 500)
        with self._transacao() as tx:
            chefe = self._ator(tx, token, ChefeLaboratorio)
            if not tx.operacoes.mudar_estado(chefe, equipamento, estado, motivo):
                raise DadosInvalidos("Selecione um equipamento do laboratório.")

    def listar_ocorrencias(self, token):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            lab = ator.laboratorio_id
            autor = None if isinstance(ator, ChefeLaboratorio) else ator.id
            return tx.operacoes.ocorrencias(lab, autor), tx.operacoes.recursos(lab), tx.operacoes.itens_ativos(lab)

    def registrar_ocorrencia(self, token, *, tipo, descricao, recurso=None, item=None):
        if tipo not in TIPOS_OCORRENCIA:
            raise DadosInvalidos("Selecione um tipo de ocorrência válido.")
        if (recurso is not None and item is not None or tipo == "DANO" and item is not None
                or tipo == "FALTA_ESTOQUE" and recurso is not None):
            raise DadosInvalidos("Selecione no máximo um recurso ou item compatível com a ocorrência.")
        descricao = texto_obrigatorio(descricao, "Descrição", 500)
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            tx.contexto(ator.id, "Registro de ocorrência")
            tx.operacoes.registrar_ocorrencia(ator, tipo, descricao, recurso, item)

    def encerrar_ocorrencia(self, token, ocorrencia):
        with self._transacao() as tx:
            chefe = self._ator(tx, token, ChefeLaboratorio)
            tx.contexto(chefe.id, "Ocorrência resolvida")
            if not tx.operacoes.encerrar_ocorrencia(chefe.laboratorio_id, ocorrencia):
                raise DadosInvalidos("Selecione uma ocorrência aberta do laboratório.")

    def listar_avisos(self, token):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            return tx.operacoes.avisos(ator)

    def marcar_lida(self, token, notificacao):
        with self._transacao() as tx:
            ator = self._ator(tx, token)
            if not tx.operacoes.marcar_lida(ator, notificacao):
                raise AcessoNegado("Selecione uma notificação da sua conta.")
