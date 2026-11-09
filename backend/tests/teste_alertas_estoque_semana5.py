
from datetime import datetime, timezone
from unittest.mock import Mock

from gestao_lab.infraestrutura.postgres import EstoquePostgres
from gestao_lab.apresentacao.paginas_estoque import painel
from gestao_lab.dominio.usuarios import ChefeLaboratorio


conexao = Mock()
repositorio = EstoquePostgres(conexao)

# Teste 1 — Avaliação de alertas.
conexao.execute.return_value.fetchone.return_value = {
    "total": 2
}

total = repositorio.avaliar_alertas(1)

assert total == 2
assert "avaliar_alertas_estoque" in (
    conexao.execute.call_args.args[0]
)
assert conexao.execute.call_args.args[1] == (1,)

# Teste 2 — Consultar notificações.
alerta = {
    "id": 10,
    "tipo": "ESTOQUE_BAIXO",
    "mensagem": "Estoque baixo: Alcool 70%",
    "criado_em": datetime.now(timezone.utc),
    "lida_em": None
}

conexao.execute.return_value.fetchall.return_value = [alerta]

alertas = repositorio.listar_alertas(1, 1)

assert len(alertas) == 1
assert alertas[0]["tipo"] == "ESTOQUE_BAIXO"

# Teste 3 — Verificar geração da interface.
chefe = ChefeLaboratorio(
    id=1,
    laboratorio_id=1,
    nome="Chefe Teste",
    email="chefe@example.org",
    senha_hash="hash_teste",
    programa_pos="Computacao"
)

html = painel(
    chefe,
    "csrf-teste",
    itens=[],
    movimentacoes=[],
    alertas=alertas
)

assert "Alertas de estoque" in html
assert "Estoque baixo: Alcool 70%" in html

# Teste 4 — Classes concretas.
assert EstoquePostgres.__abstractmethods__ == frozenset()

print("Todos os 4 testes da Etapa 5E passaram!")
