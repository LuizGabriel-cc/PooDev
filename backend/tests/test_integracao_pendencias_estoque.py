"""Verifica as pendências e movimentações em um banco PostgreSQL de testes.

Depende da fixture `sistema` e da variável TEST_DATABASE_URL.
O conftest só permite banco com nome de teste e cria um laboratório isolado.
"""
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date, timedelta
from time import monotonic, sleep

import pytest
from test_web import ClienteWSGI

from gestao_lab.aplicacao.servicos import ServicoEstoque
from gestao_lab.apresentacao.web import AplicacaoWeb
from gestao_lab.dominio.erros import DadosInvalidos
from gestao_lab.infraestrutura.configuracao import Configuracao

pytestmark = pytest.mark.integracao


def consultar(sistema, sql, parametros=()):
    with sistema.transacao() as tx:
        return tx._conexao.execute(sql, parametros).fetchall()


def test_alerta_unico_ate_regularizar_e_reabrir(sistema):
    app = ServicoEstoque(sistema.transacao, sistema.auth)
    item = app.cadastrar(
        sistema.token,
        nome=f"Estoque baixo {sistema.chave}",
        unidade="un", lote="DEMO-001", quantidade="1",
        limite_estoque_baixo="2"
    )
    for _ in range(3):
        with sistema.transacao() as tx:
            tx.estoque.avaliar_alertas(sistema.chefe.laboratorio_id)
    avisos = consultar(sistema, """
        SELECT id, resolvida_em, chave_deduplicacao
        FROM gestao_lab.notificacao
        WHERE destinatario_id=%s AND tipo='ESTOQUE_BAIXO'
          AND referencia->>'item_id'=%s
        ORDER BY id
    """, (sistema.chefe.id, str(item.id)))
    assert len(avisos) == 1 and avisos[0]["resolvida_em"] is None
    assert any(p["item_id"] == item.id for p in app.listar_pendencias(sistema.token))

    app.movimentar(sistema.token, item_id=item.id, variacao="2", motivo="Reposição")
    antigos = consultar(sistema, """
        SELECT resolvida_em, chave_deduplicacao
        FROM gestao_lab.notificacao WHERE id=%s
    """, (avisos[0]["id"],))
    assert antigos[0]["resolvida_em"] is not None and antigos[0]["chave_deduplicacao"] is None
    assert not any(p["item_id"] == item.id for p in app.listar_pendencias(sistema.token))

    app.movimentar(sistema.token, item_id=item.id, variacao="-2", motivo="Uso")
    avisos = consultar(sistema, """
        SELECT id FROM gestao_lab.notificacao
        WHERE destinatario_id=%s AND tipo='ESTOQUE_BAIXO'
          AND referencia->>'item_id'=%s
    """, (sistema.chefe.id, str(item.id)))
    assert len(avisos) == 2


def test_vencido_fica_pendente_ate_descarte_total(sistema):
    app = ServicoEstoque(sistema.transacao, sistema.auth)
    item = app.cadastrar(
        sistema.token,
        nome=f"Vencido {sistema.chave}", unidade="L",
        lote="DEMO-002", quantidade="4", limite_estoque_baixo="1",
        validade=date.today() - timedelta(days=2)
    )
    pendencias = app.listar_pendencias(sistema.token)
    pendencia = next(p for p in pendencias if p["item_id"] == item.id)
    assert pendencia["vencido"] and not pendencia["estoque_baixo"]

    with pytest.raises(DadosInvalidos, match="vencido"):
        app.movimentar(sistema.token, item_id=item.id, variacao="-1", motivo="Uso")

    # A chamada SQL legada também precisa impedir consumo de material vencido.
    with pytest.raises(DadosInvalidos, match="vencido"), sistema.transacao() as tx:
        tx._conexao.execute(
            "SELECT gestao_lab.movimentar_estoque(%s, %s, -1, 'Uso')",
            (sistema.chefe.id, item.id),
        )

    configuracao = Configuracao(sistema.url, b"segredo-de-teste-com-32-caracteres")
    cliente = ClienteWSGI(
        AplicacaoWeb(sistema.auth, sistema.cadastro, configuracao, estoque=app)
    )
    cliente.cookies["lab_sessao"] = sistema.token
    formulario = cliente.requisitar("/estoque")
    assert formulario.status == 200
    motivo = "x" * 500
    campos = {"acao": "movimentar", "item_id": item.id, "variacao": "-4",
              "motivo": motivo, "finalidade": "DESCARTE"}
    assert cliente.requisitar("/estoque", campos).status == 403
    assert cliente.requisitar("/estoque", {**campos, "csrf": cliente.csrf(formulario)}).status == 303
    painel = cliente.requisitar("/estoque")
    assert painel.status == 200
    assert f"<td>Descarte</td><td>{motivo}</td>" in painel.body

    movimento = app.listar_movimentacoes(sistema.token, item_id=item.id)[0]
    assert movimento.finalidade == "DESCARTE"
    assert movimento.motivo == motivo
    pendencia = next(p for p in app.listar_pendencias(sistema.token) if p["item_id"] == item.id)
    assert pendencia["estoque_baixo"] and not pendencia["vencido"]
    aviso_validade = consultar(sistema, """
        SELECT resolvida_em FROM gestao_lab.notificacao
        WHERE destinatario_id=%s AND tipo='VALIDADE'
          AND referencia->>'item_id'=%s
    """, (sistema.chefe.id, str(item.id)))
    assert len(aviso_validade) == 1 and aviso_validade[0]["resolvida_em"] is not None

    with sistema.transacao() as tx:
        tx._conexao.execute("UPDATE gestao_lab.item_estoque SET ativo = false WHERE id = %s", (item.id,))
    with pytest.raises(DadosInvalidos, match="inativo"):
        app.movimentar(sistema.token, item_id=item.id, variacao="1", motivo="Reposição")


def test_validade_usa_data_de_sao_paulo_e_ordena_vencidos_primeiro(sistema):
    with sistema.transacao() as tx:
        tx._conexao.execute("SET LOCAL TIME ZONE 'Pacific/Kiritimati'")
        datas = tx._conexao.execute("""
            SELECT gestao_lab.data_local_estoque('2026-11-17 02:59:59+00') AS antes,
                   gestao_lab.data_local_estoque('2026-11-17 03:00:00+00') AS depois,
                   gestao_lab.data_local_estoque() AS hoje
        """).fetchone()
    assert datas["antes"] == date(2026, 11, 16)
    assert datas["depois"] == date(2026, 11, 17)

    app = ServicoEstoque(sistema.transacao, sistema.auth)
    sem_validade = app.cadastrar(
        sistema.token, nome="Sem validade", unidade="un", quantidade="1", limite_estoque_baixo="2",
    )
    vencido = app.cadastrar(
        sistema.token, nome="Vencido", unidade="un", quantidade="1",
        validade=datas["hoje"] - timedelta(days=1),
    )
    pendencias = app.listar_pendencias(sistema.token)
    assert [pendencia["item_id"] for pendencia in pendencias] == [vencido.id, sem_validade.id]
    assert pendencias[1]["vencido"] is False
    assert pendencias[1]["validade_proxima"] is False


@pytest.mark.concorrencia
def test_monitor_rele_item_depois_de_reposicao_concorrente(sistema):
    app = ServicoEstoque(sistema.transacao, sistema.auth)
    item = app.cadastrar(
        sistema.token, nome="Reposição concorrente", unidade="un", quantidade="1", limite_estoque_baixo="2",
    )
    pid_monitor = Future()

    def executar_monitor():
        with sistema.transacao() as tx:
            pid_monitor.set_result(tx._conexao.info.backend_pid)
            return tx.estoque.avaliar_alertas(item.laboratorio_id)

    with ThreadPoolExecutor(max_workers=1) as executor:
        with sistema.transacao() as tx:
            tx.estoque.movimentar(sistema.chefe.id, item.id, 2, "Reposição")
            tx.estoque.avaliar_alertas_item(item.id)
            monitor = executor.submit(executar_monitor)
            pid = pid_monitor.result(timeout=5)
            limite = monotonic() + 3
            while monotonic() < limite:
                bloqueadores = tx._conexao.execute(
                    "SELECT pg_blocking_pids(%s) AS pids", (pid,),
                ).fetchone()["pids"]
                if tx._conexao.info.backend_pid in bloqueadores:
                    break
                sleep(0.02)
            else:
                pytest.fail("O monitor não aguardou a reposição.")
        assert monitor.result(timeout=5) == 0

    avisos = consultar(sistema, """
        SELECT resolvida_em FROM gestao_lab.notificacao
        WHERE laboratorio_id = %s AND referencia->>'item_id' = %s
    """, (item.laboratorio_id, str(item.id)))
    assert len(avisos) == 1
    assert avisos[0]["resolvida_em"] is not None
