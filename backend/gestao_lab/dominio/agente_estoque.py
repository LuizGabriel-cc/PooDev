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
    ultimo_movimento_id: int | None
    situacao: str  # INCONCLUSIVA, MINIMO_ATINGIDO, NORMAL, REPOSICAO_SUGERIDA
    justificativa: str


class AgenteEspecialistaEstoque:
    """Isola a política de análise do banco, do HTTP e das decisões humanas."""

    def __init__(self, parametros: ParametrosAgenteEstoque | None = None):
        self.parametros = parametros or ParametrosAgenteEstoque()

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

        def resposta(situacao: str, texto: str, media=None, dias=None, mae=None):
            return AnaliseEstoque(
                laboratorio_id=item.laboratorio_id, item_id=item.id,
                nome=item.nome, lote=item.lote, unidade=item.unidade,
                saldo=item.quantidade, limite_minimo=item.limite_estoque_baixo,
                instante=instante, inicio_janela=janela,
                dias_observados=dias_observados, dias_com_consumo=len(datas_consumo),
                consumo_total=consumo_total, consumo_diario=media,
                previsao_dias=dias, mae=mae, ultimo_movimento_id=ultimo_movimento_id,
                situacao=situacao, justificativa=texto,
            )

        if item.quantidade <= item.limite_estoque_baixo:
            return resposta("MINIMO_ATINGIDO", "O limite mínimo já foi atingido; o alerta normal de estoque (RF08) permanece independente.")
        if item.validade is not None and item.validade < instante.astimezone(FUSO_LABORATORIO).date():
            return resposta("INCONCLUSIVA", "Lote vencido: não é confiável projetar consumo de uso; consulte os alertas de validade (RF08).")
        if nao_classificadas:
            return resposta("INCONCLUSIVA", "Existem saídas históricas sem finalidade classificada; não foram tratadas como consumo.")
        if dias_observados < self.parametros.minimo_dias_observados:
            return resposta("INCONCLUSIVA", f"Apenas {dias_observados} dia(s) observados; mínimo provisório: {self.parametros.minimo_dias_observados}.")
        if len(datas_consumo) < self.parametros.minimo_dias_com_consumo:
            return resposta("INCONCLUSIVA", f"Consumo em {len(datas_consumo)} dia(s); mínimo provisório: {self.parametros.minimo_dias_com_consumo} dias distintos.")
        if consumo_total <= 0:
            return resposta("INCONCLUSIVA", "Não há consumo efetivo suficiente; nenhuma previsão foi estimada.")

        media = consumo_total / Decimal(dias_observados)
        if media <= 0:
            return resposta("INCONCLUSIVA", "Não foi possível estimar o consumo diário.")
        prazo = ((item.quantidade - item.limite_estoque_baixo) / media).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        mae = self._mae_retrospectivo(usos, inicio, instante)
        texto = (
            f"Foram considerados {consumo_total} {item.unidade} consumidos em "
            f"{len(datas_consumo)} dias com saídas por USO, durante {dias_observados} dias "
            f"observados. Ritmo médio: {media.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)} "
            f"{item.unidade}/dia. Estimativa: {prazo} dia(s) até o mínimo, "
            f"supondo consumo médio constante. Entradas e descartes não são consumo. "
            f"Reavaliar quando novas movimentações forem registradas."
        )
        if item.validade is not None and item.validade <= (
            instante.astimezone(FUSO_LABORATORIO).date() + timedelta(days=int(prazo))
        ):
            texto += " A validade pode ocorrer antes de atingir o limite previsto."
        situacao = ("REPOSICAO_SUGERIDA" if prazo <= self.parametros.antecedencia_dias
                    else "NORMAL")
        return resposta(situacao, texto, media, prazo, mae)

    @staticmethod
    def _mae_retrospectivo(usos, inicio: datetime, instante: datetime) -> Decimal | None:
        """Erro da média histórica dos dias anteriores frente aos 7 dias completos finais."""
        hoje = instante.astimezone(FUSO_LABORATORIO).date()
        primeiro_dia = inicio.astimezone(FUSO_LABORATORIO).date()
        primeiro_dia_validacao = hoje - timedelta(days=7)
        dias_treino = (primeiro_dia_validacao - primeiro_dia).days
        if dias_treino < 7:
            return None
        treino = sum((-m.variacao for m in usos
                     if m.criado_em.astimezone(FUSO_LABORATORIO).date() < primeiro_dia_validacao), Decimal("0"))
        treino_dias_com_consumo = {
            m.criado_em.astimezone(FUSO_LABORATORIO).date() for m in usos
            if m.criado_em.astimezone(FUSO_LABORATORIO).date() < primeiro_dia_validacao
        }
        if len(treino_dias_com_consumo) < 3:
            return None
        media_treino = treino / Decimal(dias_treino)
        erro = Decimal("0")
        for n in range(7):
            dia = primeiro_dia_validacao + timedelta(days=n)
            consumo_dia = sum((-m.variacao for m in usos
                              if m.criado_em.astimezone(FUSO_LABORATORIO).date() == dia), Decimal("0"))
            erro += abs(consumo_dia - media_treino)
        return (erro / Decimal("7")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
