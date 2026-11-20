"""Caso de uso do agente de estoque: consulta, recomendação e decisão humana."""
from datetime import datetime, timedelta, timezone

from ..dominio.agente_estoque import AgenteEspecialistaEstoque
from ..dominio.erros import AcessoNegado, DadosInvalidos
from ..dominio.usuarios import ChefeLaboratorio


class ServicoAgenteEstoque:
    def __init__(self, transacao, autenticacao, agente=None):
        self._transacao = transacao
        self._autenticacao = autenticacao
        self._agente = agente or AgenteEspecialistaEstoque()

    def _chefe_e_laboratorio(self, tx, token):
        chefe = self._autenticacao.identificar_na_transacao(tx, token)
        if not isinstance(chefe, ChefeLaboratorio) or not chefe.ativo or chefe.id is None:
            raise AcessoNegado("Somente o Chefe de Laboratório pode usar o agente.")
        laboratorio = tx.laboratorios.buscar_por_id(chefe.laboratorio_id)
        if (laboratorio is None or not laboratorio.ativo
                or laboratorio.chefe_usuario_id != chefe.id):
            raise AcessoNegado("Chefe não autorizado para este laboratório.")
        return chefe, laboratorio

    def analisar(self, token, *, registrar=False, agora=None):
        if type(registrar) is not bool:
            raise DadosInvalidos("Parâmetro de análise inválido.")
        momento = agora or datetime.now(timezone.utc)
        with self._transacao() as tx:
            chefe, laboratorio = self._chefe_e_laboratorio(tx, token)
            resultados = []
            for item in tx.estoque.listar(laboratorio.id):
                if not item.ativo:
                    continue
                movimentos, primeiro, ultimo_id = tx.agente_estoque.historico(
                    laboratorio.id, item.id,
                    momento - timedelta(days=self._agente.parametros.janela_dias),
                    bloquear=registrar,
                )
                # O item pode ter sido alterado entre a listagem e a aquisição
                # do bloqueio; reconsulta o saldo sob a mesma transação.
                if registrar:
                    item = tx.estoque.buscar(item.id, laboratorio.id)
                    if item is None or not item.ativo:
                        continue
                analise = self._agente.analisar(
                    item, movimentos, primeiro, ultimo_id, agora=momento
                )
                resultados.append(analise)
                if registrar and analise.situacao == "REPOSICAO_SUGERIDA":
                    tx.agente_estoque.registrar(analise)
            return resultados

    def listar_recomendacoes(self, token):
        with self._transacao() as tx:
            _, laboratorio = self._chefe_e_laboratorio(tx, token)
            return tx.agente_estoque.listar_recomendacoes(laboratorio.id)

    def decidir(self, token, recomendacao_id: int, decisao: str):
        if type(recomendacao_id) is not int or recomendacao_id <= 0:
            raise DadosInvalidos("Recomendação inválida.")
        if decisao not in ("ACEITA", "DESCARTADA"):
            raise DadosInvalidos("Decisão inválida.")
        with self._transacao() as tx:
            chefe, laboratorio = self._chefe_e_laboratorio(tx, token)
            if not tx.agente_estoque.decidir(
                laboratorio.id, recomendacao_id, chefe.id, decisao
            ):
                raise DadosInvalidos("Recomendação não encontrada ou já analisada.")
