"""Fluxo real de persistência, notificação e revisão. Banco descartável apenas.

A previsão fictícia injetada aqui serve EXCLUSIVAMENTE para testar a
integração PostgreSQL; não é apresentada como evidência de precisão do agente.
A precisão das previsões é avaliada nos testes de domínio isolados.
"""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest

from gestao_lab.aplicacao.servicos import ServicoEstoque
from gestao_lab.aplicacao.agente_estoque import ServicoAgenteEstoque
from gestao_lab.dominio.agente_estoque import AgenteEspecialistaEstoque

pytestmark = pytest.mark.integracao


def test_banco_preserva_recomendacao_decisao_e_notificacao(sistema):
    estoque = ServicoEstoque(sistema.transacao, sistema.auth)
    lote = estoque.cadastrar(
        sistema.token, nome=f"Reagente de integração {sistema.chave}",
        unidade="L", lote="IA-TESTE", quantidade="12", limite_estoque_baixo="5",
    )
    with sistema.transacao() as tx:
        movimentos, primeiro, ultimo = tx.agente_estoque.historico(
            lote.laboratorio_id, lote.id, datetime.now(timezone.utc) - timedelta(days=30), bloquear=True
        )
        analise_real = AgenteEspecialistaEstoque().analisar(
            lote, movimentos, primeiro, ultimo
        )
        assert analise_real.situacao == "INCONCLUSIVA"
        assert ultimo is not None
        # Massa sintética apenas para testar a escrita e a notificação.
        simulacao = replace(
            analise_real, situacao="REPOSICAO_SUGERIDA",
            consumo_total=Decimal("10"), consumo_diario=Decimal("1"),
            previsao_dias=Decimal("7"),
            justificativa="SIMULAÇÃO DE INTEGRAÇÃO. NÃO É UMA PREVISÃO REAL."
        )
        recomendacao = tx.agente_estoque.registrar(simulacao)
        assert recomendacao > 0
        assert tx.agente_estoque.registrar(simulacao) == recomendacao

    with sistema.transacao() as tx:
        rows = tx._conexao.execute("""
            SELECT id FROM gestao_lab.recomendacao_estoque
            WHERE laboratorio_id=%s AND item_id=%s
        """, (lote.laboratorio_id, lote.id)).fetchall()
        assert len(rows) == 1
        avisos = tx._conexao.execute("""
            SELECT id FROM gestao_lab.notificacao
            WHERE laboratorio_id=%s AND destinatario_id=%s AND tipo='AGENTE_ESTOQUE'
              AND referencia->>'recomendacao_id'=%s
        """, (lote.laboratorio_id, sistema.chefe.id, str(recomendacao))).fetchall()
        assert len(avisos) == 1

    agente = ServicoAgenteEstoque(sistema.transacao, sistema.auth)
    agente.decidir(sistema.token, recomendacao, "ACEITA")
    with sistema.transacao() as tx:
        row = tx._conexao.execute("""
            SELECT situacao, decidido_por, decidido_em FROM gestao_lab.recomendacao_estoque
            WHERE id=%s AND laboratorio_id=%s
        """, (recomendacao, lote.laboratorio_id)).fetchone()
        assert row["situacao"] == "ACEITA"
        assert row["decidido_por"] == sistema.chefe.id and row["decidido_em"] is not None
        assert tx.estoque.buscar(lote.id, lote.laboratorio_id).quantidade == Decimal("12")
