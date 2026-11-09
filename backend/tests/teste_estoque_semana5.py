
from datetime import date, datetime, timezone
from decimal import Decimal

from gestao_lab.dominio.estoque import (
    ItemEstoque,
    MovimentacaoEstoque
)
from gestao_lab.dominio.erros import DadosInvalidos


item = ItemEstoque(
    laboratorio_id=1,
    nome="Alcool 70%",
    unidade="L",
    lote="L001",
    quantidade="2.5000",
    limite_estoque_baixo="3",
    validade=date(2026, 11, 15)
)

assert item.estoque_baixo()
assert item.validade_proxima(
    10, hoje=date(2026, 11, 8)
)

movimento = MovimentacaoEstoque(
    laboratorio_id=1,
    item_id=5,
    registrado_por=2,
    variacao="-1.2500",
    quantidade_anterior="2.5000",
    quantidade_posterior="1.2500",
    motivo="Uso em pesquisa",
    criado_em=datetime.now(timezone.utc)
)

assert movimento.variacao == Decimal("-1.2500")

try:
    ItemEstoque(
        laboratorio_id=1,
        nome="Item inválido",
        unidade="un",
        quantidade=-1
    )
except DadosInvalidos:
    pass
else:
    raise AssertionError(
        "Quantidade negativa deveria ser rejeitada."
    )

print("Testes da Etapa 5A passaram!")
