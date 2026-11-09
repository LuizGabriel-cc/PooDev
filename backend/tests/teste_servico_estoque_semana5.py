
from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, Mock

from gestao_lab.aplicacao.servicos import ServicoEstoque
from gestao_lab.dominio.erros import (
    AcessoNegado, DadosInvalidos
)
from gestao_lab.dominio.laboratorios import Laboratorio
from gestao_lab.dominio.usuarios import (
    ChefeLaboratorio, Professor
)


chefe = ChefeLaboratorio(
    id=1,
    laboratorio_id=1,
    nome="Chefe Teste",
    email="chefe@example.org",
    senha_hash="hash_teste",
    programa_pos="Computacao"
)

laboratorio = Laboratorio(
    id=1,
    nome="Laboratorio Teste",
    localizacao="Bloco A",
    chefe_usuario_id=1
)

tx = MagicMock()
tx.__enter__.return_value = tx
tx.laboratorios.buscar_por_id.return_value = laboratorio

autenticacao = Mock()
autenticacao.identificar_na_transacao.return_value = chefe

servico = ServicoEstoque(
    lambda: tx,
    autenticacao
)

# TESTE 1 - Cadastrar um item.
tx.estoque.criar.side_effect = (
    lambda chefe_id, item, motivo: replace(item, id=7)
)

item = servico.cadastrar(
    "token_teste",
    nome="Alcool 70%",
    unidade="L",
    lote="L001",
    quantidade="5",
    limite_estoque_baixo="2",
    validade=date(2026, 12, 31)
)

assert item.id == 7
assert item.quantidade == Decimal("5")

print("Teste 1: cadastro funcionando.")

# TESTE 2 - Listar e consultar.
tx.estoque.listar.return_value = [item]
tx.estoque.buscar.return_value = item

assert len(servico.listar("token_teste")) == 1
assert servico.consultar("token_teste", 7) == item

print("Teste 2: consultas funcionando.")

# TESTE 3 - Registrar saída.
tx.estoque.movimentar.return_value = Decimal("3")

saldo = servico.movimentar(
    "token_teste",
    item_id=7,
    variacao="-2",
    motivo="Uso em pesquisa"
)

assert saldo == Decimal("3")
tx.estoque.movimentar.assert_called_once_with(
    1, 7, Decimal("-2"), "Uso em pesquisa"
)

print("Teste 3: saída funcionando.")

# TESTE 4 - Impedir estoque negativo.
try:
    servico.movimentar(
        "token_teste",
        item_id=7,
        variacao="-10",
        motivo="Saida excessiva"
    )
except DadosInvalidos:
    pass
else:
    raise AssertionError(
        "Saída maior que o saldo deveria falhar."
    )

assert tx.estoque.movimentar.call_count == 1

print("Teste 4: estoque negativo bloqueado.")

# TESTE 5 - Consultar movimentações.
tx.estoque.listar_movimentacoes.return_value = []

assert servico.listar_movimentacoes(
    "token_teste", item_id=7
) == []

tx.estoque.listar_movimentacoes.assert_called_with(
    1, 7
)

print("Teste 5: histórico de movimentações funcionando.")

# TESTE 6 - Bloquear Professor comum.
professor = Professor(
    id=2,
    laboratorio_id=1,
    nome="Professor Teste",
    email="professor@example.org",
    senha_hash="hash_teste",
    programa_pos="Computacao"
)

autenticacao.identificar_na_transacao.return_value = professor

try:
    servico.cadastrar(
        "token_teste",
        nome="Produto proibido",
        unidade="un"
    )
except AcessoNegado:
    pass
else:
    raise AssertionError(
        "Professor não deveria cadastrar estoque."
    )

print("Teste 6: permissão do Chefe funcionando.")

print("Todos os 6 testes da Etapa 5C passaram!")
