"""Cenários sintéticos reproduzíveis para demonstrar o MESMO agente no site.

Nenhuma função deste módulo abre conexão, grava movimentações, gera avisos ou
persistências. Os identificadores e datas pertencem somente à memória do processo.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .agente_estoque import AgenteEspecialistaEstoque, AnaliseEstoque, FUSO_LABORATORIO
from .erros import DadosInvalidos
from .estoque import ItemEstoque, MovimentacaoEstoque


# Código, título e propósito ficam em uma lista fechada: não há SQL ou execução
# de conteúdo submetido pelo navegador.
CENARIOS_DISPONIVEIS = (
    ("risco", "Risco de reposição (R07)", "Consumo regular: previsão de 7 dias até o mínimo."),
    ("normal", "Estoque confortável (R08)", "Mesmo consumo; saldo suficiente para 35 dias."),
    ("minimo", "Mínimo já atingido (R01)", "Saldo abaixo do mínimo; o alerta RF08 continua independente."),
    ("recente", "Histórico recente (R04)", "Apenas 2 dias de observação; previsão recusada."),
    ("esparso", "Poucos dias com uso (R05)", "Histórico longo, mas consumo registrado em um único dia."),
    ("descarte", "Descarte não é consumo (R07)", "Descartes não entram no cálculo da média diária de uso."),
    ("sem_classificacao", "Saída não classificada (R03)", "Saída sem finalidade impede previsão confiável."),
    ("vencido", "Lote vencido (R02)", "Lote vencido exige atenção à validade, não uma previsão de consumo."),
)


@dataclass(frozen=True)
class ResultadoDemonstracao:
    codigo: str
    titulo: str
    descricao: str
    analise: AnaliseEstoque
    movimentos: tuple[MovimentacaoEstoque, ...]
    saldo_inicial: Decimal


def executar_cenario(codigo: str, *, agora: datetime | None = None) -> ResultadoDemonstracao:
    """Aplica o agente real a dados totalmente fictícios, sem E/S ou gravações."""
    metadados = {id_: (titulo, descricao) for id_, titulo, descricao in CENARIOS_DISPONIVEIS}
    if codigo not in metadados:
        raise DadosInvalidos("Cenário de demonstração inválido.")
    instante = agora or datetime.now(timezone.utc)
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise DadosInvalidos("O cenário exige data com fuso horário.")

    # Tuplas: (dias antes da análise, variação de saldo, finalidade).
    dez_usos = [(dia, Decimal("-1"), "USO") for dia in range(10, 0, -1)]
    eventos = list(dez_usos)
    saldo_final = Decimal("12")
    dias_observados = 10
    validade = None
    if codigo == "normal":
        saldo_final = Decimal("40")
    elif codigo == "minimo":
        saldo_final = Decimal("4")
    elif codigo == "recente":
        dias_observados = 2
        eventos = [(1, Decimal("-1"), "USO")]
    elif codigo == "esparso":
        eventos = [(2, Decimal("-1"), "USO")]
    elif codigo == "descarte":
        eventos.append((3, Decimal("-5"), "DESCARTE"))
    elif codigo == "sem_classificacao":
        eventos.append((2, Decimal("-1"), None))
    elif codigo == "vencido":
        validade = instante.astimezone(FUSO_LABORATORIO).date() - timedelta(days=1)

    # Ordena do evento mais antigo ao mais recente e mantém saldos auditáveis
    # entre os movimentos, sem usar a tabela de movimentações do PostgreSQL.
    eventos.sort(key=lambda evento: evento[0], reverse=True)
    saldo_inicial = saldo_final - sum((variacao for _, variacao, _ in eventos), Decimal("0"))
    saldo = saldo_inicial
    movimentos = []
    for indice, (dias, variacao, finalidade) in enumerate(eventos, start=1):
        movimentos.append(MovimentacaoEstoque(
            id=indice, laboratorio_id=999991, item_id=999991,
            registrado_por=999991, variacao=variacao,
            quantidade_anterior=saldo,
            quantidade_posterior=saldo + variacao,
            finalidade=finalidade,
            motivo="DADO FICTÍCIO — simulação didática",
            criado_em=instante - timedelta(days=dias),
        ))
        saldo += variacao
    assert saldo == saldo_final
    item = ItemEstoque(
        id=999991, laboratorio_id=999991,
        nome="Reagente fictício (não cadastrado)",
        lote="DEMO-" + codigo.upper(), unidade="L",
        quantidade=saldo_final, limite_estoque_baixo=Decimal("5"),
        validade=validade,
    )
    analise = AgenteEspecialistaEstoque().analisar(
        item, movimentos, instante - timedelta(days=dias_observados),
        movimentos[-1].id if movimentos else None, agora=instante,
    )
    titulo, descricao = metadados[codigo]
    return ResultadoDemonstracao(
        codigo, titulo, descricao, analise, tuple(movimentos), saldo_inicial
    )
