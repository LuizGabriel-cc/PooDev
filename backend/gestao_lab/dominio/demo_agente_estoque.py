"""Demonstração REPRODUZÍVEL do motor de inferência, sem PostgreSQL.

Executar a partir de backend/: python -m gestao_lab.dominio.demo_agente_estoque
Os registros são sintéticos, NÃO são previsões do laboratório real.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .agente_estoque import AgenteEspecialistaEstoque
from .estoque import ItemEstoque, MovimentacaoEstoque

AGORA = datetime(2026, 11, 20, 15, tzinfo=timezone.utc)


def item(saldo="12"):
    return ItemEstoque(
        id=1, laboratorio_id=1, nome="Reagente sintético",
        lote="DEMO-IA", unidade="L", quantidade=saldo,
        limite_estoque_baixo="5",
    )


def usos(dias=10):
    return [
        MovimentacaoEstoque(
            id=dia, laboratorio_id=1, item_id=1, registrado_por=1,
            variacao=Decimal("-1"),
            quantidade_anterior=Decimal(12+dia),
            quantidade_posterior=Decimal(11+dia),
            motivo="Consumo fictício para avaliação", finalidade="USO",
            criado_em=AGORA - timedelta(days=dia),
        )
        for dia in range(1, dias+1)
    ]


def executar():
    agente = AgenteEspecialistaEstoque()
    movimentos = usos()
    cenarios = (
        ("Risco em sete dias", item(), movimentos, AGORA-timedelta(days=10), "REPOSICAO_SUGERIDA", Decimal("7")),
        ("Saldo confortável", item("40"), movimentos, AGORA-timedelta(days=10), "NORMAL", Decimal("35")),
        ("Abaixo do mínimo", item("4"), movimentos, AGORA-timedelta(days=10), "MINIMO_ATINGIDO", None),
        ("Consumo insuficiente", item(), movimentos[:1], AGORA-timedelta(days=10), "INCONCLUSIVA", None),
    )
    for titulo, material, eventos, primeiro, esperado, prazo_esperado in cenarios:
        analise = agente.analisar(material, eventos, primeiro, max(m.id for m in eventos), agora=AGORA)
        assert analise.situacao == esperado, (titulo, analise.situacao)
        assert (analise.previsao_dias is None if prazo_esperado is None else analise.previsao_dias == prazo_esperado), titulo
        print(f"{titulo}: {analise.situacao} | regra={analise.regra_aplicada} "
              f"| prazo={analise.previsao_dias} | qualidade={analise.qualidade}")
    print("4 cenários sintéticos aprovados (sem banco de dados).")


if __name__ == "__main__":
    executar()
