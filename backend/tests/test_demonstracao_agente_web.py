"""O modo de apresentação usa o motor real, mas nunca persiste dados.

Estes testes não necessitam de PostgreSQL e não criam registros.
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from gestao_lab.apresentacao.web import AplicacaoWeb
from gestao_lab.dominio.cenarios_demonstracao_estoque import (
    CENARIOS_DISPONIVEIS, executar_cenario,
)
from gestao_lab.dominio.erros import DadosInvalidos
from gestao_lab.dominio.usuarios import ChefeLaboratorio, Professor
from gestao_lab.infraestrutura.configuracao import Configuracao
from test_web import ClienteWSGI

AGORA = datetime(2026, 11, 21, 15, tzinfo=timezone.utc)
TOKEN = "a" * 43


@pytest.mark.parametrize("codigo,regra,situacao,prazo", [
    ("risco", "R07", "REPOSICAO_SUGERIDA", Decimal("7.00")),
    ("normal", "R08", "NORMAL", Decimal("35.00")),
    ("minimo", "R01", "MINIMO_ATINGIDO", None),
    ("recente", "R04", "INCONCLUSIVA", None),
    ("esparso", "R05", "INCONCLUSIVA", None),
    ("descarte", "R07", "REPOSICAO_SUGERIDA", Decimal("7.00")),
    ("sem_classificacao", "R03", "INCONCLUSIVA", None),
    ("vencido", "R02", "INCONCLUSIVA", None),
])
def test_motor_real_classifica_cenarios_ficticios(codigo, regra, situacao, prazo):
    caso = executar_cenario(codigo, agora=AGORA)
    assert caso.analise.regra_aplicada == regra
    assert caso.analise.situacao == situacao
    assert caso.analise.previsao_dias == prazo
    assert caso.analise.saldo == {"normal": Decimal("40"), "minimo": Decimal("4")}.get(codigo, Decimal("12"))
    assert caso.saldo_inicial + sum((m.variacao for m in caso.movimentos), Decimal(0)) == caso.analise.saldo
    assert all(m.laboratorio_id == 999991 for m in caso.movimentos)
    assert all(m.item_id == 999991 for m in caso.movimentos)


def test_descarte_nao_influencia_media_e_saldo_permanece_coerente():
    caso = executar_cenario("descarte", agora=AGORA)
    assert caso.analise.consumo_total == Decimal("10")
    assert sum((-m.variacao for m in caso.movimentos if m.finalidade == "DESCARTE"), Decimal(0)) == 5
    assert caso.analise.consumo_diario == Decimal("1")
    assert caso.saldo_inicial == Decimal("27")


def test_cenarios_invalidos_sao_rejeitados():
    with pytest.raises(DadosInvalidos):
        executar_cenario("inexistente", agora=AGORA)


def _web(perfil="chefe"):
    chefe = ChefeLaboratorio(
        id=1, laboratorio_id=1, nome="Chefe", email="chefe@example.org",
        senha_hash="hash de teste", programa_pos="Biologia",
    )
    professor = Professor(
        id=2, laboratorio_id=1, nome="Professor", email="prof@example.org",
        senha_hash="hash de teste", programa_pos="Biologia",
    )
    usuarios = {"chefe": chefe, "professor": professor}
    usuario = usuarios.get(perfil)
    autenticacao = Mock()
    autenticacao.identificar.return_value = usuario
    agente = Mock()
    agente.analisar.return_value = []
    agente.listar_recomendacoes.return_value = []
    configuracao = Configuracao("postgresql://localhost/banco_nao_utilizado", b"a" * 32)
    cliente = ClienteWSGI(AplicacaoWeb(autenticacao, Mock(), configuracao, agente_estoque=agente))
    if perfil is not None:
        cliente.cookies["lab_sessao"] = TOKEN
    return cliente, agente


def test_tela_demonstra_risco_sem_realizar_consultas_ou_gravacoes_do_agente():
    cliente, agente = _web()
    resposta = cliente.requisitar("/agente-estoque/demonstracao")
    assert resposta.status == 200
    assert "SIMULAÇÃO: NENHUM DADO É GRAVADO" in resposta.body
    assert "R07" in resposta.body
    assert "7.00 dias" in resposta.body
    assert "DEMO-RISCO" in resposta.body
    assert "/agente-estoque" in resposta.body
    assert 'method="get" action="/agente-estoque/demonstracao"' in resposta.body
    agente.assert_not_called()
    agente.analisar.assert_not_called()
    agente.listar_recomendacoes.assert_not_called()
    agente.decidir.assert_not_called()


@pytest.mark.parametrize("codigo,regra", [(c, r) for c, r in (
    ("normal", "R08"), ("minimo", "R01"), ("recente", "R04"),
    ("esparso", "R05"), ("descarte", "R07"),
    ("sem_classificacao", "R03"), ("vencido", "R02"),
)])
def test_escolha_pelo_navegador_eh_segura_e_sem_escrita(codigo, regra):
    cliente, agente = _web()
    resposta = cliente.requisitar(f"/agente-estoque/demonstracao?cenario={codigo}")
    assert resposta.status == 200
    assert f' <strong>{regra} ' in resposta.body or f'>{regra} ' in resposta.body
    agente.analisar.assert_not_called()
    agente.decidir.assert_not_called()


@pytest.mark.parametrize("perfil,status", [("professor", 403), (None, 303)])
def test_acesso_ao_modo_simulado_eh_restrito_ao_chefe(perfil, status):
    cliente, agente = _web(perfil)
    resposta = cliente.requisitar("/agente-estoque/demonstracao")
    assert resposta.status == status
    agente.analisar.assert_not_called()


def test_modo_simulado_nao_aceita_post_ou_cenarios_inventados():
    cliente, agente = _web()
    assert cliente.requisitar("/agente-estoque/demonstracao?cenario=outro").status == 400
    assert cliente.requisitar("/agente-estoque/demonstracao?cenario=risco&cenario=normal").status == 400
    pagina = cliente.requisitar("/agente-estoque/demonstracao")
    assert cliente.requisitar("/agente-estoque/demonstracao", {"csrf": cliente.csrf(pagina)}).status == 405
    agente.analisar.assert_not_called()
    agente.decidir.assert_not_called()


def test_painel_real_apresenta_link_para_demonstra_sem_abrir_simulacao():
    cliente, agente = _web()
    pagina = cliente.requisitar("/agente-estoque")
    assert pagina.status == 200
    assert 'href="/agente-estoque/demonstracao"' in pagina.body
    agente.analisar.assert_called_once()
    agente.listar_recomendacoes.assert_called_once()
