"""Previsão explicável e conservadora de risco de estoque mínimo (RF26).

Esta é uma estratégia estatística simples com regras especialistas; não depende de
API externa ou modelo de linguagem. Os parâmetros são PROVISÓRIOS até aprovação
pela professora (Definicao_Agente_Controle_Estoque_PooDev.pdf).
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from .erros import DadosInvalidos
from .estoque import ItemEstoque, MovimentacaoEstoque
from .regras_especialistas_estoque import FatosEstoque, MotorInferenciaEstoque

FUSO_LABORATORIO = timezone(timedelta(hours=-3))  # Consistente com o fuso da aplicação.


@dataclass(frozen=True)
class ParametrosAgenteEstoque:
    janela_dias: int = 30
    antecedencia_dias: int = 7
    minimo_dias_observados: int = 7
    minimo_dias_com_consumo: int = 3

    def __post_init__(self):
        valores = (self.janela_dias, self.antecedencia_dias,
                   self.minimo_dias_observados, self.minimo_dias_com_consumo)
        if any(type(v) is not int or v <= 0 for v in valores):
            raise DadosInvalidos("Os parâmetros do agente devem ser inteiros positivos.")
        if self.minimo_dias_observados > self.janela_dias:
            raise DadosInvalidos("Observação mínima excede a janela histórica.")
        if self.minimo_dias_com_consumo > self.janela_dias:
            raise DadosInvalidos("Dias de consumo excedem a janela histórica.")


@dataclass(frozen=True)
class AnaliseEstoque:
    laboratorio_id: int
    item_id: int
    nome: str
    lote: str
    unidade: str
    saldo: Decimal
    limite_minimo: Decimal
    instante: datetime
    inicio_janela: datetime
    dias_observados: int
    dias_com_consumo: int
    consumo_total: Decimal
    consumo_diario: Decimal | None
    previsao_dias: Decimal | None
    mae: Decimal | None
    mae_referencia: Decimal | None
    qualidade: str  # ESTAVEL, VARIAVEL ou NAO_AVALIADA; não é probabilidade
    regra_aplicada: str
    ultimo_movimento_id: int | None
    situacao: str  # INCONCLUSIVA, MINIMO_ATINGIDO, NORMAL, REPOSICAO_SUGERIDA
    justificativa: str


class AgenteEspecialistaEstoque:
    """Isola a política de análise do banco, do HTTP e das decisões humanas."""

    def __init__(self, parametros: ParametrosAgenteEstoque | None = None):
        self.parametros = parametros or ParametrosAgenteEstoque()
        self._motor = MotorInferenciaEstoque()

    def analisar(
        self,
        item: ItemEstoque,
        movimentos: list[MovimentacaoEstoque],
        primeiro_registro: datetime | None,
        ultimo_movimento_id: int | None,
        *,
        agora: datetime | None = None,
    ) -> AnaliseEstoque:
        instante = agora or datetime.now(timezone.utc)
        if instante.tzinfo is None or instante.utcoffset() is None:
            raise DadosInvalidos("A data da análise exige fuso horário.")
        janela = instante - timedelta(days=self.parametros.janela_dias)
        if primeiro_registro is not None and (
            primeiro_registro.tzinfo is None or primeiro_registro.utcoffset() is None
        ):
            raise DadosInvalidos("A data do primeiro registro exige fuso horário.")
        for movimento in movimentos:
            if (movimento.laboratorio_id != item.laboratorio_id
                    or movimento.item_id != item.id):
                raise DadosInvalidos("O histórico contém registros de outro item ou laboratório.")
        validos = [m for m in movimentos if janela <= m.criado_em <= instante]
        inicio = max(janela, primeiro_registro) if primeiro_registro else instante
        dias_observados = max(0, int((instante - inicio).total_seconds() // 86400))
        usos = [m for m in validos if m.variacao < 0 and m.finalidade == "USO"]
        nao_classificadas = [m for m in validos if m.variacao < 0 and m.finalidade is None]
        consumo_total = sum((-m.variacao for m in usos), Decimal("0"))
        datas_consumo = {m.criado_em.astimezone(FUSO_LABORATORIO).date() for m in usos}

        # Calcula os fatos ANTES de inferir: a política de decisão está na base
        # de conhecimento, não em uma sequência opaca de ifs da camada web.
        media = (consumo_total / Decimal(dias_observados)
                 if consumo_total > 0 and dias_observados > 0 else None)
        prazo = ((item.quantidade - item.limite_estoque_baixo) / media).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ) if media and item.quantidade > item.limite_estoque_baixo else None
        expirado = (item.validade is not None
                    and item.validade < instante.astimezone(FUSO_LABORATORIO).date())
        fatos = FatosEstoque(
            minimo_atingido=item.quantidade <= item.limite_estoque_baixo,
            lote_vencido=expirado,
            saidas_sem_classificacao=len(nao_classificadas),
            dias_observados=dias_observados,
            minimo_dias_observados=self.parametros.minimo_dias_observados,
            dias_com_consumo=len(datas_consumo),
            minimo_dias_com_consumo=self.parametros.minimo_dias_com_consumo,
            consumo_total=consumo_total, consumo_diario=media,
            previsao_dias=prazo, antecedencia_dias=self.parametros.antecedencia_dias,
        )
        regra, situacao, explicacao = self._motor.inferir(fatos)
        calculavel = situacao in ("NORMAL", "REPOSICAO_SUGERIDA")
        mae = mae_ref = None
        qualidade = "NAO_AVALIADA"
        if calculavel:
            mae, mae_ref = self._mae_retrospectivo(usos, inicio, instante)
            if mae is not None:
                # Classificação qualitativa heurística; não é probabilidade.
                qualidade = "ESTAVEL" if mae <= media / Decimal("2") else "VARIAVEL"
            explicacao = (
                f"Foram considerados {consumo_total} {item.unidade} consumidos em "
                f"{len(datas_consumo)} dias com saídas por USO, durante {dias_observados} dias "
                f"observados. Ritmo médio: {media.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)} "
                f"{item.unidade}/dia. Estimativa: {prazo} dia(s) até o mínimo, "
                f"supondo consumo médio constante. Entradas e descartes não são consumo. "
                f"Reavaliar quando novas movimentações forem registradas. " + explicacao
            )
            if mae is not None:
                explicacao += (
                    f" MAE retrospectivo do modelo: {mae} {item.unidade}/dia; "
                    f"referência ingênua (último dia de treino): {mae_ref} "
                    f"{item.unidade}/dia; estabilidade heurística: {qualidade}. "
                    "Essas métricas não garantem acurácia futura."
                )
            if item.validade is not None and item.validade <= (
                instante.astimezone(FUSO_LABORATORIO).date() + timedelta(days=int(prazo))
            ):
                explicacao += " A validade pode ocorrer antes de atingir o limite previsto."
        return AnaliseEstoque(
            laboratorio_id=item.laboratorio_id, item_id=item.id,
            nome=item.nome, lote=item.lote, unidade=item.unidade,
            saldo=item.quantidade, limite_minimo=item.limite_estoque_baixo,
            instante=instante, inicio_janela=janela,
            dias_observados=dias_observados, dias_com_consumo=len(datas_consumo),
            consumo_total=consumo_total,
            consumo_diario=media if calculavel else None,
            previsao_dias=prazo if calculavel else None,
            mae=mae, mae_referencia=mae_ref, qualidade=qualidade,
            regra_aplicada=regra, ultimo_movimento_id=ultimo_movimento_id,
            situacao=situacao, justificativa=explicacao,
        )

    @staticmethod
    def _mae_retrospectivo(usos, inicio: datetime, instante: datetime) -> tuple[Decimal | None, Decimal | None]:
        """Treino anterior à última semana vs 7 dias completos de teste.

        Referência ingênua: consumo no último dia completo do treinamento,
        repetido nos 7 dias de avaliação. Os dois modelos usam o MESMO corte
        temporal; jamais utilizam dados do período avaliado para treinar.
        """
        hoje = instante.astimezone(FUSO_LABORATORIO).date()
        primeiro_dia = inicio.astimezone(FUSO_LABORATORIO).date()
        corte = hoje - timedelta(days=7)
        dias_treino = (corte - primeiro_dia).days
        if dias_treino < 7:
            return None, None
        diaria = {}
        for m in usos:
            dia = m.criado_em.astimezone(FUSO_LABORATORIO).date()
            diaria[dia] = diaria.get(dia, Decimal("0")) - m.variacao
        if len([dia for dia, qtd in diaria.items() if primeiro_dia <= dia < corte and qtd > 0]) < 3:
            return None, None
        total_treino = sum((qtd for dia, qtd in diaria.items()
                            if primeiro_dia <= dia < corte), Decimal("0"))
        media_treino = total_treino / Decimal(dias_treino)
        referencia = diaria.get(corte - timedelta(days=1), Decimal("0"))
        erros_modelo = erros_ref = Decimal("0")
        for n in range(7):
            real = diaria.get(corte + timedelta(days=n), Decimal("0"))
            erros_modelo += abs(real - media_treino)
            erros_ref += abs(real - referencia)
        fmt = Decimal("0.0001")
        return ((erros_modelo / 7).quantize(fmt, rounding=ROUND_HALF_UP),
                (erros_ref / 7).quantize(fmt, rounding=ROUND_HALF_UP))
