"""Regressões do painel de pendências e do descarte de material vencido.

São testes isolados. A migração SQL deve ser verificada em PostgreSQL de testes.
"""
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, Mock

import pytest

from gestao_lab.aplicacao.servicos import ServicoEstoque
from gestao_lab.apresentacao.paginas_estoque import painel
from gestao_lab.dominio.erros import DadosInvalidos
from gestao_lab.dominio.estoque import ItemEstoque, MovimentacaoEstoque
from gestao_lab.dominio.laboratorios import Laboratorio
from gestao_lab.dominio.usuarios import ChefeLaboratorio
from gestao_lab.infraestrutura.postgres import EstoquePostgres


@pytest.fixture
def chefe():
    return ChefeLaboratorio(
        id=1, laboratorio_id=1, nome="Chefe Teste",
        email="chefe@example.org", senha_hash="hash_teste",
        programa_pos="Biologia"
    )


@pytest.fixture
def servico(chefe):
    tx = MagicMock()
    tx.__enter__.return_value = tx
    tx.laboratorios.buscar_por_id.return_value = Laboratorio(
        id=1, nome="Laboratório Teste", localizacao="Bloco A",
        chefe_usuario_id=1
    )
    autenticacao = Mock()
    autenticacao.identificar_na_transacao.return_value = chefe
    return ServicoEstoque(lambda: tx, autenticacao), tx


def item_vencido():
    return ItemEstoque(
        id=7, laboratorio_id=1, nome="Reagente teste",
        lote="DEMO-001", unidade="L", quantidade="4",
        limite_estoque_baixo="1", validade=date(2020, 1, 1)
    )


def test_motivo_de_descarte_acima_do_limite_e_recusado(servico):
    app, tx = servico
    tx.estoque.buscar.return_value = item_vencido()
    with pytest.raises(DadosInvalidos, match="500"):
        app.movimentar(
            "token", item_id=7, variacao="-1",
            motivo="x" * 501, finalidade="DESCARTE",
        )
    tx.estoque.movimentar.assert_not_called()


def test_descarte_encaminha_motivo_e_finalidade_separadamente(servico):
    app, tx = servico
    tx.estoque.buscar.return_value = item_vencido()
    tx.estoque.movimentar.return_value = Decimal("0")
    motivo = "x" * 500
    saldo = app.movimentar(
        "token", item_id=7, variacao="-4",
        motivo=motivo, finalidade="DESCARTE"
    )
    assert saldo == 0
    tx.estoque.movimentar.assert_called_once_with(
        1, 7, Decimal("-4"), motivo, "DESCARTE"
    )
    tx.estoque.avaliar_alertas_item.assert_called_once_with(7)


def test_entrada_continua_permitida(servico):
    app, tx = servico
    tx.estoque.buscar.return_value = replace(item_vencido(), quantidade=Decimal("0"))
    tx.estoque.movimentar.return_value = Decimal("5")
    assert app.movimentar("token", item_id=7, variacao="5", motivo="Reposição") == 5
    tx.estoque.movimentar.assert_called_once_with(1, 7, Decimal("5"), "Reposição", "USO")


def test_finalidade_de_descarte_sem_saida_e_recusada(servico):
    app, tx = servico
    with pytest.raises(DadosInvalidos, match="Descarte"):
        app.movimentar(
            "token", item_id=7, variacao="1", motivo="Ajuste",
            finalidade="DESCARTE"
        )
    tx.estoque.movimentar.assert_not_called()


def test_pendencias_sao_restritas_ao_laboratorio(servico):
    app, tx = servico
    registros = [{"item_id": 7, "laboratorio_id": 1, "vencido": True}]
    tx.estoque.listar_pendencias.return_value = registros
    assert app.listar_pendencias("token") == registros
    tx.estoque.listar_pendencias.assert_called_once_with(1)


def test_repositorio_consulta_view_e_alertas_nao_resolvidos():
    con = Mock()
    con.execute.return_value.fetchall.return_value = []
    repo = EstoquePostgres(con)
    assert repo.listar_pendencias(42) == []
    consulta = con.execute.call_args.args[0]
    assert "vw_pendencias_estoque" in consulta
    assert "vencido DESC NULLS LAST" in consulta
    assert con.execute.call_args.args[1] == (42,)
    repo.listar_alertas(42, 5)
    consulta = con.execute.call_args.args[0]
    assert "resolvida_em IS NULL" in consulta
    assert con.execute.call_args.args[1] == (42, 5)


def test_pagina_mostra_vencido_com_saldo_suficiente_e_escapa_html(chefe):
    item = replace(item_vencido(), nome="Reagente <teste>")
    pendencias = [{
        "item_id": 7, "laboratorio_id": 1,
        "nome": "Reagente <teste>", "lote": "DEMO-001",
        "unidade": "L", "quantidade": Decimal("4"),
        "limite_estoque_baixo": Decimal("1"),
        "validade": date(2020, 1, 1), "estoque_baixo": False,
        "vencido": True, "validade_proxima": False
    }]
    html = painel(chefe, "csrf", [item], [], pendencias=pendencias)
    assert "Pendências do estoque" in html
    assert html.count("Vencido") == 2
    assert 'name="finalidade"' in html
    assert "&lt;teste&gt;" in html
    assert "Reagente <teste>" not in html


def test_pagina_le_historico_anterior_com_motivo_longo(chefe):
    motivo_legado = "Descarte: " + ("x" * 500)
    anterior = MovimentacaoEstoque(
        laboratorio_id=1, item_id=7, registrado_por=1,
        variacao="-1", quantidade_anterior="4", quantidade_posterior="3",
        motivo=motivo_legado, criado_em=datetime.now(timezone.utc),
    )
    descarte = replace(anterior, motivo="Reagente vencido", finalidade="DESCARTE")
    html = painel(chefe, "csrf", [], [anterior, descarte])
    assert f"<td>—</td><td>{motivo_legado}</td>" in html
    assert "<td>Descarte</td><td>Reagente vencido</td>" in html
