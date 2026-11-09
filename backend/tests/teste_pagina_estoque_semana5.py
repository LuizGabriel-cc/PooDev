
from datetime import datetime, timezone
from decimal import Decimal
from gestao_lab.dominio.estoque import (
    ItemEstoque, MovimentacaoEstoque
)
from gestao_lab.dominio.usuarios import ChefeLaboratorio
from gestao_lab.apresentacao.paginas_estoque import painel


chefe = ChefeLaboratorio(
    id=1, laboratorio_id=1,
    nome="Chefe Teste",
    email="chefe@example.org",
    senha_hash="hash_teste",
    programa_pos="Computacao"
)

item = ItemEstoque(
    id=7, laboratorio_id=1,
    nome="Alcool <teste>",
    unidade="L", lote="L001",
    quantidade="2",
    limite_estoque_baixo="3"
)

movimento = MovimentacaoEstoque(
    id=10, laboratorio_id=1,
    item_id=7, registrado_por=1,
    variacao="-1",
    quantidade_anterior="3",
    quantidade_posterior="2",
    motivo="<script>teste</script>",
    criado_em=datetime.now(timezone.utc)
)

html = painel(
    chefe, "csrf-teste",
    [item], [movimento]
)

assert "Gestão de Estoque" in html
assert 'name="acao" value="cadastrar"' in html
assert 'name="acao" value="movimentar"' in html
assert html.count('name="csrf"') >= 2
assert "Estoque baixo" in html

# Proteção contra HTML não confiável.
assert "<script>" not in html
assert "&lt;script&gt;" in html
assert "&lt;teste&gt;" in html

print("Testes da Etapa 5D passaram!")
