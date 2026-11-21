"""Testes isolados RF26/RF29, sem precisar de PostgreSQL."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, Mock

import pytest

from gestao_lab.aplicacao.agente_estoque import ServicoAgenteEstoque
from gestao_lab.apresentacao.paginas_agente_estoque import painel
from gestao_lab.dominio.agente_estoque import AgenteEspecialistaEstoque, ParametrosAgenteEstoque
from gestao_lab.dominio.erros import AcessoNegado, DadosInvalidos
from gestao_lab.dominio.estoque import ItemEstoque, MovimentacaoEstoque
from gestao_lab.dominio.laboratorios import Laboratorio
from gestao_lab.dominio.usuarios import Aluno, ChefeLaboratorio

AGORA = datetime(2026, 11, 20, 15, tzinfo=timezone.utc)


def item(lab=1, saldo="12", nome="Reagente"):
    return ItemEstoque(id=10, laboratorio_id=lab, nome=nome, lote="A-1",
                       unidade="L", quantidade=saldo, limite_estoque_baixo="5")


def movimento(dias, finalidade="USO", quantidade="-1", lab=1, item_id=10, numero=1):
    q = Decimal(quantidade)
    anterior = Decimal("30")
    return MovimentacaoEstoque(id=numero, laboratorio_id=lab, item_id=item_id,
                               registrado_por=1, variacao=q,
                               quantidade_anterior=anterior,
                               quantidade_posterior=anterior + q,
                               motivo="Operação de teste", finalidade=finalidade,
                               criado_em=AGORA - timedelta(days=dias))


def dez_dias_de_uso():
    return [movimento(dias, numero=dias) for dias in range(1, 11)]


def calcular(movimentos, *, saldo="12", agora=AGORA):
    return AgenteEspecialistaEstoque().analisar(
        item(saldo=saldo), movimentos, AGORA - timedelta(days=10),
        max([m.id for m in movimentos], default=None), agora=agora,
    )


def test_exemplo_documento_12_menos_5_ritmo_1_por_dia():
    resultado = calcular(dez_dias_de_uso())
    assert resultado.situacao == "REPOSICAO_SUGERIDA"
    assert resultado.consumo_diario == Decimal("1")
    assert resultado.previsao_dias == Decimal("7.00")
    assert resultado.dias_com_consumo == 10
    assert "7.00 dia" in resultado.justificativa


def test_descartes_e_entradas_nao_geram_consumo():
    movimentos = dez_dias_de_uso()
    movimentos.append(movimento(2, finalidade="DESCARTE", quantidade="-5", numero=70))
    movimentos.append(movimento(4, finalidade=None, quantidade="5", numero=71))
    resultado = calcular(movimentos)
    assert resultado.consumo_total == Decimal("10")
    assert resultado.previsao_dias == Decimal("7.00")


def test_saida_legada_sem_classificacao_torna_previsao_inconclusiva():
    movimentos = dez_dias_de_uso() + [movimento(2, finalidade=None, numero=80)]
    resultado = calcular(movimentos)
    assert resultado.situacao == "INCONCLUSIVA"
    assert resultado.previsao_dias is None
    assert "sem finalidade" in resultado.justificativa


def test_historico_insuficiente_ou_sem_consumo_nao_inventa_previsao():
    agente = AgenteEspecialistaEstoque()
    curto = [movimento(1, numero=1)]
    resultado = agente.analisar(item(), curto, AGORA - timedelta(days=1), 1, agora=AGORA)
    assert resultado.situacao == "INCONCLUSIVA" and resultado.previsao_dias is None
    sem_uso = [movimento(9, finalidade="DESCARTE", numero=1)]
    resultado = agente.analisar(item(), sem_uso, AGORA - timedelta(days=10), 1, agora=AGORA)
    assert resultado.situacao == "INCONCLUSIVA" and resultado.previsao_dias is None


def test_saldo_normal_e_minimo_atingido():
    assert calcular(dez_dias_de_uso(), saldo="100").situacao == "NORMAL"
    atingido = calcular([], saldo="5")
    assert atingido.situacao == "MINIMO_ATINGIDO"
    assert atingido.previsao_dias is None


def test_rejeita_historico_de_outro_laboratorio_e_item():
    with pytest.raises(DadosInvalidos, match="outro item ou laboratório"):
        calcular(dez_dias_de_uso() + [movimento(1, lab=2, numero=99)])
    with pytest.raises(DadosInvalidos, match="outro item ou laboratório"):
        calcular(dez_dias_de_uso() + [movimento(1, item_id=11, numero=99)])


def test_parametros_configuraveis_e_validos():
    parametros = ParametrosAgenteEstoque(antecedencia_dias=10)
    res = AgenteEspecialistaEstoque(parametros).analisar(
        item(saldo="14"), dez_dias_de_uso(), AGORA - timedelta(days=10),
        10, agora=AGORA,
    )
    assert res.situacao == "REPOSICAO_SUGERIDA"
    with pytest.raises(DadosInvalidos):
        ParametrosAgenteEstoque(janela_dias=4, minimo_dias_observados=7)


def _servico(chefe_ativo=True):
    chefe = ChefeLaboratorio(id=1, laboratorio_id=1, nome="Chefe",
                            email="chefe@example.org", senha_hash="hash", programa_pos="Bio")
    tx = MagicMock()
    tx.__enter__.return_value = tx
    tx.laboratorios.buscar_por_id.return_value = Laboratorio(
        id=1, nome="Laboratório", localizacao="Bloco A", chefe_usuario_id=1
    )
    auth = Mock()
    auth.identificar_na_transacao.return_value = chefe
    tx.estoque.listar.return_value = [item()]
    tx.estoque.buscar.return_value = item()
    tx.agente_estoque.historico.return_value = (
        dez_dias_de_uso(), AGORA - timedelta(days=10), 10
    )
    return ServicoAgenteEstoque(lambda: tx, auth), tx, auth, chefe


def test_servico_so_grava_em_analise_explicita():
    servico, tx, _, _ = _servico()
    assert servico.analisar("token", agora=AGORA)[0].situacao == "REPOSICAO_SUGERIDA"
    tx.agente_estoque.registrar.assert_not_called()
    servico.analisar("token", registrar=True, agora=AGORA)
    tx.agente_estoque.registrar.assert_called_once()
    assert tx.agente_estoque.historico.call_args.kwargs["bloquear"] is True


def test_professor_aluno_nao_podem_analisar_ou_decidir():
    servico, tx, auth, _ = _servico()
    auth.identificar_na_transacao.return_value = Aluno(
        id=2, laboratorio_id=1, nome="Aluno", email="aluno@example.org",
        senha_hash="hash", matricula="123", tipo="GRADUACAO", orientador_id=1
    )
    with pytest.raises(AcessoNegado):
        servico.analisar("token", agora=AGORA)
    with pytest.raises(AcessoNegado):
        servico.decidir("token", 1, "ACEITA")
    tx.agente_estoque.registrar.assert_not_called()
    tx.agente_estoque.decidir.assert_not_called()


def test_decisao_valida_somente_no_proprio_laboratorio():
    servico, tx, _, _ = _servico()
    tx.agente_estoque.decidir.return_value = True
    servico.decidir("token", 8, "DESCARTADA")
    tx.agente_estoque.decidir.assert_called_once_with(1, 8, 1, "DESCARTADA")
    with pytest.raises(DadosInvalidos):
        servico.decidir("token", 8, "PENDENTE")
    tx.agente_estoque.decidir.return_value = False
    with pytest.raises(DadosInvalidos, match="já analisada"):
        servico.decidir("token", 9, "ACEITA")


def test_html_escapa_nome_e_justificativa():
    _, _, _, chefe = _servico()
    analise = AgenteEspecialistaEstoque().analisar(
        item(nome="<script>alert(1)</script>"), dez_dias_de_uso(),
        AGORA - timedelta(days=10), 10, agora=AGORA,
    )
    html = painel(chefe, "csrf", [analise], [])
    assert "&lt;script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "agente-estoque/analisar" in html


def test_mae_retrospectivo_com_historico_suficiente():
    movimentos = [movimento(dia, numero=dia) for dia in range(1, 31)]
    resultado = AgenteEspecialistaEstoque().analisar(
        item(), movimentos, AGORA - timedelta(days=40), 30, agora=AGORA
    )
    assert resultado.mae is not None
    assert resultado.mae >= 0


def test_repositorio_deduplica_mesma_evidencia_sem_reabrir_decisao():
    from gestao_lab.infraestrutura.agente_estoque_postgres import RepositorioAgenteEstoquePostgres
    banco = Mock()
    banco.execute.return_value.fetchone.return_value = {"id": 33}
    repo = RepositorioAgenteEstoquePostgres(banco)
    analise = calcular(dez_dias_de_uso())
    assert repo.registrar(analise) == 33
    assert banco.execute.call_count == 1
    consulta, argumentos = banco.execute.call_args.args
    assert "ultimo_movimento_id" in consulta
    assert argumentos == (1, 10, 10)


def test_rota_web_de_analise_e_decisao_exigem_chefe():
    from types import SimpleNamespace
    from gestao_lab.apresentacao.web import AplicacaoWeb
    servico, tx, _, chefe = _servico()
    # Evita que a passagem dos dias altere o resultado do teste de rota.
    # O cenário sintético do módulo foi fixado em AGORA.
    analisar_original = servico.analisar
    servico.analisar = lambda token, *, registrar=False: analisar_original(
        token, registrar=registrar, agora=AGORA
    )
    app = AplicacaoWeb(Mock(), Mock(), SimpleNamespace(segredo_csrf=b"x" * 32),
                       agente_estoque=servico)
    resposta = app._rotear_agente_estoque(
        "/agente-estoque/analisar", "POST", {}, {}, "token", chefe, "csrf",
    )
    assert resposta.status == 303
    assert ("Location", "/agente-estoque?resultado=analise") in resposta.headers
    tx.agente_estoque.registrar.assert_called_once()
    tx.agente_estoque.decidir.return_value = True
    resposta = app._rotear_agente_estoque(
        "/agente-estoque/decidir", "POST", {},
        {"recomendacao_id": "4", "decisao": "ACEITA"}, "token", chefe, "csrf",
    )
    assert resposta.status == 303
    tx.agente_estoque.decidir.assert_called_once_with(1, 4, 1, "ACEITA")
    with pytest.raises(AcessoNegado):
        app._rotear_agente_estoque(
            "/agente-estoque", "GET", {}, {}, "token", "professor", "csrf",
        )
