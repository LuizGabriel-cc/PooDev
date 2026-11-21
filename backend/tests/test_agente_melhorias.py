"""Melhorias de IA: conhecimento explícito, análise preventiva e comparação."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock, MagicMock

from gestao_lab.aplicacao.agente_estoque import ServicoAgenteEstoque
from gestao_lab.dominio.agente_estoque import AgenteEspecialistaEstoque
from gestao_lab.dominio.regras_especialistas_estoque import BASE_CONHECIMENTO
from gestao_lab.infraestrutura.agente_estoque_postgres import RepositorioAgenteEstoquePostgres
from test_agente_estoque import AGORA, item, movimento, dez_dias_de_uso, calcular


def test_base_de_conhecimento_explicita_com_prioridades_sem_duplicatas():
    codigos = [regra.codigo for regra in BASE_CONHECIMENTO]
    assert codigos == [f"R{n:02d}" for n in range(1, 9)]
    assert len(set(codigos)) == len(codigos)
    assert len({regra.descricao for regra in BASE_CONHECIMENTO}) == 8


def test_inferencia_identifica_regras_de_risco_e_insuficiencia():
    assert calcular(dez_dias_de_uso()).regra_aplicada == "R07"
    assert calcular(dez_dias_de_uso(), saldo="100").regra_aplicada == "R08"
    assert calcular([], saldo="5").regra_aplicada == "R01"
    curto = AgenteEspecialistaEstoque().analisar(
        item(), [movimento(1)], AGORA - timedelta(days=1), 1, agora=AGORA
    )
    assert curto.regra_aplicada == "R04"
    nao_classificado = calcular(dez_dias_de_uso() + [movimento(2, None, numero=98)])
    assert nao_classificado.regra_aplicada == "R03"
    assert nao_classificado.previsao_dias is None


def test_comparacao_mae_em_conjunto_retrospectivo_independente():
    # 30 dias com consumo constante, incluindo treino e 7 dias finais.
    movimentos = [movimento(dia, numero=dia) for dia in range(1, 31)]
    analise = AgenteEspecialistaEstoque().analisar(
        item(), movimentos, AGORA - timedelta(days=40), 30, agora=AGORA
    )
    assert analise.mae is not None
    assert analise.mae_referencia is not None
    assert analise.mae >= 0 and analise.mae_referencia >= 0
    assert analise.qualidade in ("ESTAVEL", "VARIAVEL")
    assert "não garantem acurácia futura" in analise.justificativa


def test_pouco_historico_nao_exibe_mae_nem_qualidade_inventada():
    analise = calcular(dez_dias_de_uso())
    assert analise.mae is None
    assert analise.mae_referencia is None
    assert analise.qualidade == "NAO_AVALIADA"


def test_auto_monitora_somente_lotes_validos_e_registra_so_risco():
    tx = MagicMock()
    tx.__enter__.return_value = tx
    tx.agente_estoque.itens_para_monitoramento.return_value = [
        {"laboratorio_id": 1, "item_id": 10},
        {"laboratorio_id": 1, "item_id": 11},
    ]
    lab = Mock(ativo=True)
    tx.laboratorios.buscar_por_id.return_value = lab
    tx.agente_estoque.historico.return_value = (
        dez_dias_de_uso(), AGORA - timedelta(days=10), 10
    )
    tx.estoque.buscar.side_effect = [item(), item(saldo="100")]
    servico = ServicoAgenteEstoque(lambda: tx, Mock())
    resumo = servico.analisar_automaticamente(agora=AGORA)
    assert resumo == {"lotes": 2, "riscos": 1}
    tx.agente_estoque.registrar.assert_called_once()
    assert tx.agente_estoque.historico.call_args.kwargs["bloquear"] is True


def test_auto_nao_avalia_lote_sem_laboratorio_ativo():
    tx = MagicMock()
    tx.__enter__.return_value = tx
    tx.agente_estoque.itens_para_monitoramento.return_value = [
        {"laboratorio_id": 3, "item_id": 9}
    ]
    tx.laboratorios.buscar_por_id.return_value = Mock(ativo=False)
    servico = ServicoAgenteEstoque(lambda: tx, Mock())
    assert servico.analisar_automaticamente(agora=AGORA) == {"lotes": 0, "riscos": 0}
    tx.agente_estoque.registrar.assert_not_called()


def test_notificacao_somente_na_insercao_sem_duplicar_mesma_evidencia():
    analise = calcular(dez_dias_de_uso())
    conexao = Mock()
    # Consulta de duplicidade retorna vazio, pendência vazio, INSERT retorna ID.
    respostas = [None, None, {"id": 60}, None]
    def execute(_sql, _params=None):
        cursor = Mock()
        cursor.fetchone.return_value = respostas.pop(0)
        return cursor
    conexao.execute.side_effect = execute
    repo = RepositorioAgenteEstoquePostgres(conexao)
    assert repo.registrar(analise) == 60
    assert conexao.execute.call_count == 4
    assert "gestao_lab.notificar" in conexao.execute.call_args.args[0]
    # Na segunda análise, mesmo último movimento deve retornar ID anterior.
    conexao.execute.reset_mock()
    conexao.execute.side_effect = None
    conexao.execute.return_value.fetchone.return_value = {"id": 60}
    assert repo.registrar(analise) == 60
    assert conexao.execute.call_count == 1


def test_painel_exibe_regra_e_comparacao_de_metricas():
    from gestao_lab.apresentacao.paginas_agente_estoque import painel
    from gestao_lab.dominio.usuarios import ChefeLaboratorio
    chefe = ChefeLaboratorio(
        id=1, laboratorio_id=1, nome="Chefe", email="chefe@exemplo.org",
        senha_hash="hash", programa_pos="Biologia"
    )
    analise = AgenteEspecialistaEstoque().analisar(
        item(), [movimento(d, numero=d) for d in range(1, 31)],
        AGORA - timedelta(days=40), 30, agora=AGORA
    )
    html = painel(chefe, "csrf", [analise], [])
    assert "Regra aplicada: R07" in html
    assert "MAE de referência:" in html
    assert "estabilidade retrospectiva" in html
