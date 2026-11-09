
from dataclasses import asdict
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

from gestao_lab.dominio.estoque import (
    ItemEstoque, MovimentacaoEstoque
)
from gestao_lab.infraestrutura.postgres import (
    EstoquePostgres, UnidadeTrabalhoPostgres
)


conexao = Mock()
repositorio = EstoquePostgres(conexao)

item = ItemEstoque(
    laboratorio_id=1,
    nome="Alcool 70%",
    lote="L001",
    unidade="L",
    quantidade="2.5000",
    limite_estoque_baixo="3",
    validade=date(2026, 12, 31)
)

linha = {**asdict(item), "id": 7}

# TESTE 1 - Cadastrar item.
conexao.execute.return_value.fetchone.return_value = linha

salvo = repositorio.criar(
    chefe_id=1,
    item=item,
    motivo="Cadastro inicial"
)

assert salvo.id == 7
assert salvo.quantidade == Decimal("2.5000")

chamadas = conexao.execute.call_args_list

assert len(chamadas) == 3
assert "exigir_chefe" in chamadas[0].args[0]
assert "contexto_operacao" in chamadas[1].args[0]
assert "INSERT INTO gestao_lab.item_estoque" in chamadas[2].args[0]

print("Teste 1: cadastro correto.")

# TESTE 2 - Buscar e listar itens.
conexao.execute.return_value.fetchone.return_value = linha
conexao.execute.return_value.fetchall.return_value = [linha]

assert repositorio.buscar(7, 1).id == 7
assert len(repositorio.listar(1)) == 1

print("Teste 2: consultas corretas.")

# TESTE 3 - Movimentar estoque.
conexao.execute.return_value.fetchone.return_value = {
    "quantidade": Decimal("1.2500")
}

saldo = repositorio.movimentar(
    chefe_id=1,
    item_id=7,
    variacao=Decimal("-1.2500"),
    motivo="Uso em pesquisa"
)

assert saldo == Decimal("1.2500")
assert "gestao_lab.movimentar_estoque" in (
    conexao.execute.call_args.args[0]
)

print("Teste 3: movimentação correta.")

# TESTE 4 - Consultar histórico de movimentações.
conexao.execute.return_value.fetchall.return_value = [{
    "id": 10,
    "laboratorio_id": 1,
    "item_id": 7,
    "registrado_por": 1,
    "variacao": Decimal("-1.2500"),
    "quantidade_anterior": Decimal("2.5000"),
    "quantidade_posterior": Decimal("1.2500"),
    "motivo": "Uso em pesquisa",
    "criado_em": datetime.now(timezone.utc)
}]

movimentos = repositorio.listar_movimentacoes(1, 7)

assert len(movimentos) == 1
assert isinstance(movimentos[0], MovimentacaoEstoque)

print("Teste 4: histórico correto.")

# TESTE 5 - Classes concretas.
assert EstoquePostgres.__abstractmethods__ == frozenset()
assert UnidadeTrabalhoPostgres.__abstractmethods__ == frozenset()

print("Teste 5: interfaces implementadas.")
print("Todos os 5 testes da Etapa 5B passaram!")
