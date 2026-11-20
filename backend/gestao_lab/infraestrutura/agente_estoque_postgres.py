"""Persistência isolada do agente. Não altera saldos, reservas ou alertas RF08."""
from ..dominio.estoque import MovimentacaoEstoque


class RepositorioAgenteEstoquePostgres:
    def __init__(self, conexao):
        self._conexao = conexao

    def historico(self, laboratorio_id, item_id, desde, *, bloquear=False):
        if bloquear:
            # Serializa análise/gravação com movimentações do mesmo lote.
            self._conexao.execute("""
                SELECT id FROM gestao_lab.item_estoque
                WHERE id = %s AND laboratorio_id = %s FOR UPDATE
            """, (item_id, laboratorio_id))
        resumo = self._conexao.execute("""
            SELECT min(criado_em) AS primeiro_registro,
                   max(id) AS ultimo_movimento_id
            FROM gestao_lab.movimentacao_estoque
            WHERE laboratorio_id = %s AND item_id = %s
        """, (laboratorio_id, item_id)).fetchone()
        linhas = self._conexao.execute("""
            SELECT id, laboratorio_id, item_id, registrado_por, variacao,
                   quantidade_anterior, quantidade_posterior, motivo,
                   criado_em, finalidade
            FROM gestao_lab.movimentacao_estoque
            WHERE laboratorio_id = %s AND item_id = %s AND criado_em >= %s
            ORDER BY criado_em ASC, id ASC
        """, (laboratorio_id, item_id, desde)).fetchall()
        return ([MovimentacaoEstoque(**linha) for linha in linhas],
                resumo["primeiro_registro"], resumo["ultimo_movimento_id"])

    def registrar(self, analise):
        """Uma pendência por lote; só reemite após nova movimentação.

        O serviço já bloqueou o item antes da leitura, portanto duas análises
        não podem produzir recomendações repetidas em paralelo.
        """
        if analise.situacao != "REPOSICAO_SUGERIDA" or analise.ultimo_movimento_id is None:
            return None
        args = (analise.laboratorio_id, analise.item_id)
        ja_analisado = self._conexao.execute("""
            SELECT id FROM gestao_lab.recomendacao_estoque
            WHERE laboratorio_id = %s AND item_id = %s AND ultimo_movimento_id = %s
        """, (*args, analise.ultimo_movimento_id)).fetchone()
        if ja_analisado:
            return ja_analisado["id"]
        pendente = self._conexao.execute("""
            SELECT id FROM gestao_lab.recomendacao_estoque
            WHERE laboratorio_id = %s AND item_id = %s AND situacao = 'PENDENTE'
            FOR UPDATE
        """, args).fetchone()
        campos = (
            analise.instante, analise.inicio_janela, analise.saldo,
            analise.limite_minimo, analise.dias_observados,
            analise.dias_com_consumo, analise.consumo_total,
            analise.consumo_diario, analise.previsao_dias,
            analise.mae, analise.justificativa, analise.ultimo_movimento_id,
        )
        if pendente:
            # Atualiza a evidência de uma única recomendação ainda pendente.
            self._conexao.execute("""
                UPDATE gestao_lab.recomendacao_estoque SET
                    analisado_em = %s, inicio_janela = %s, saldo = %s,
                    limite_minimo = %s, dias_observados = %s,
                    dias_com_consumo = %s, consumo_total = %s,
                    consumo_diario = %s, previsao_dias = %s,
                    mae = %s, justificativa = %s, ultimo_movimento_id = %s,
                    atualizado_em = clock_timestamp()
                WHERE id = %s AND laboratorio_id = %s AND situacao = 'PENDENTE'
            """, (*campos, pendente["id"], analise.laboratorio_id))
            return pendente["id"]
        linha = self._conexao.execute("""
            INSERT INTO gestao_lab.recomendacao_estoque (
                laboratorio_id, item_id, analisado_em, inicio_janela,
                saldo, limite_minimo, dias_observados, dias_com_consumo,
                consumo_total, consumo_diario, previsao_dias, mae,
                justificativa, ultimo_movimento_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (*args, *campos)).fetchone()
        return linha["id"]

    def listar_recomendacoes(self, laboratorio_id):
        return self._conexao.execute("""
            SELECT r.id, r.laboratorio_id, r.item_id, i.nome, i.lote,
                   i.unidade, r.analisado_em, r.inicio_janela, r.saldo,
                   r.limite_minimo, r.dias_observados, r.dias_com_consumo,
                   r.consumo_total, r.consumo_diario, r.previsao_dias,
                   r.mae, r.justificativa, r.situacao, r.decidido_em,
                   u.nome AS decidido_por_nome
            FROM gestao_lab.recomendacao_estoque r
            JOIN gestao_lab.item_estoque i
              ON i.id = r.item_id AND i.laboratorio_id = r.laboratorio_id
            LEFT JOIN gestao_lab.usuario u ON u.id = r.decidido_por
            WHERE r.laboratorio_id = %s
            ORDER BY (r.situacao = 'PENDENTE') DESC, r.analisado_em DESC, r.id DESC
            LIMIT 100
        """, (laboratorio_id,)).fetchall()

    def decidir(self, laboratorio_id, recomendacao_id, chefe_id, decisao):
        resultado = self._conexao.execute("""
            UPDATE gestao_lab.recomendacao_estoque
               SET situacao = %s, decidido_por = %s, decidido_em = clock_timestamp(),
                   atualizado_em = clock_timestamp()
             WHERE id = %s AND laboratorio_id = %s AND situacao = 'PENDENTE'
            RETURNING id
        """, (decisao, chefe_id, recomendacao_id, laboratorio_id)).fetchone()
        return resultado is not None
