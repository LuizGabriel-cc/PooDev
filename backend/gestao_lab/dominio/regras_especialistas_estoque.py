"""Base de conhecimento explícita e motor de inferência do agente (RF26).

Ordem = prioridade: a primeira regra verdadeira encerra a inferência.
A escolha é deliberadamente auditável e independente de HTTP/PostgreSQL.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable


@dataclass(frozen=True)
class FatosEstoque:
    minimo_atingido: bool
    lote_vencido: bool
    saidas_sem_classificacao: int
    dias_observados: int
    minimo_dias_observados: int
    dias_com_consumo: int
    minimo_dias_com_consumo: int
    consumo_total: Decimal
    consumo_diario: Decimal | None
    previsao_dias: Decimal | None
    antecedencia_dias: int


@dataclass(frozen=True)
class RegraConhecimento:
    codigo: str
    conclusao: str
    descricao: str
    condicao: Callable[[FatosEstoque], bool]
    explicacao: Callable[[FatosEstoque], str]


# Declaração pública das regras, apropriada para discussão acadêmica.
BASE_CONHECIMENTO = (
    RegraConhecimento(
        "R01", "MINIMO_ATINGIDO", "Saldo no mínimo ou abaixo dele",
        lambda f: f.minimo_atingido,
        lambda f: "O limite mínimo já foi atingido; o alerta normal de estoque (RF08) permanece independente.",
    ),
    RegraConhecimento(
        "R02", "INCONCLUSIVA", "Lote vencido",
        lambda f: f.lote_vencido,
        lambda f: "Lote vencido: não é confiável projetar consumo de uso; consulte os alertas de validade (RF08).",
    ),
    RegraConhecimento(
        "R03", "INCONCLUSIVA", "Saída sem classificação de finalidade",
        lambda f: f.saidas_sem_classificacao > 0,
        lambda f: "Existem saídas históricas sem finalidade classificada; não foram tratadas como consumo.",
    ),
    RegraConhecimento(
        "R04", "INCONCLUSIVA", "Janela observada insuficiente",
        lambda f: f.dias_observados < f.minimo_dias_observados,
        lambda f: (f"Apenas {f.dias_observados} dia(s) observados; "
                   f"mínimo provisório: {f.minimo_dias_observados}."),
    ),
    RegraConhecimento(
        "R05", "INCONCLUSIVA", "Poucos dias distintos de consumo",
        lambda f: f.dias_com_consumo < f.minimo_dias_com_consumo,
        lambda f: (f"Consumo em {f.dias_com_consumo} dia(s); mínimo provisório: "
                   f"{f.minimo_dias_com_consumo} dias distintos."),
    ),
    RegraConhecimento(
        "R06", "INCONCLUSIVA", "Consumo nulo ou média não calculável",
        lambda f: f.consumo_total <= 0 or f.consumo_diario is None or f.consumo_diario <= 0,
        lambda f: "Não há consumo efetivo suficiente; nenhuma previsão foi estimada.",
    ),
    RegraConhecimento(
        "R07", "REPOSICAO_SUGERIDA", "Prazo até o mínimo dentro da antecedência",
        lambda f: f.previsao_dias is not None and f.previsao_dias <= f.antecedencia_dias,
        lambda f: (f"Prazo previsto de {f.previsao_dias} dia(s) dentro dos "
                   f"{f.antecedencia_dias} dias de antecedência: avaliar reposição."),
    ),
    RegraConhecimento(
        "R08", "NORMAL", "Prazo acima do horizonte de alerta",
        lambda f: f.previsao_dias is not None and f.previsao_dias > f.antecedencia_dias,
        lambda f: "Estimativa acima do horizonte de alerta; acompanhar as próximas movimentações.",
    ),
)


class MotorInferenciaEstoque:
    """Encadeamento direto de regras com prioridade explícita."""

    def __init__(self, regras=BASE_CONHECIMENTO):
        self.regras = tuple(regras)

    def inferir(self, fatos: FatosEstoque) -> tuple[str, str, str]:
        for regra in self.regras:
            if regra.condicao(fatos):
                return regra.codigo, regra.conclusao, regra.explicacao(fatos)
        # Fail closed, sem previsão inventada quando fatos não se encaixarem.
        return "R00", "INCONCLUSIVA", "Não foi possível inferir uma situação confiável."
