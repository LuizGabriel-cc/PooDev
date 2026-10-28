
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from gestao_lab.infraestrutura.postgres import (
    ReservasPostgres,
    UnidadeTrabalhoPostgres
)


# Simula uma conexão com o PostgreSQL.
conexao = Mock()

# Simula o ID devolvido pelo banco após criar uma reserva.
conexao.execute.return_value.fetchone.return_value = {
    "id": 42
}

repositorio = ReservasPostgres(conexao)

inicio = datetime(
    2026, 11, 1, 10, 0, tzinfo=timezone.utc
)
fim = inicio + timedelta(hours=1)


# TESTE 1 - Criação da reserva.
reserva_id = repositorio.criar(
    usuario_id=1,
    recurso_id=3,
    inicio=inicio,
    fim=fim
)

assert reserva_id == 42

primeira_chamada = conexao.execute.call_args_list[0]

assert "gestao_lab.criar_reserva" in primeira_chamada.args[0]
assert primeira_chamada.args[1] == (1, 3, inicio, fim)


# TESTE 2 - Cancelamento da reserva.
repositorio.cancelar(
    ator_id=1,
    reserva_id=42,
    motivo="Cancelamento de teste"
)

segunda_chamada = conexao.execute.call_args_list[1]

assert "gestao_lab.cancelar_reserva" in segunda_chamada.args[0]
assert segunda_chamada.args[1] == (
    1,
    42,
    "Cancelamento de teste"
)


# TESTE 3 - Verifica a implementação abstrata.
assert ReservasPostgres.__abstractmethods__ == frozenset()

# Verifica que a Unidade de Trabalho continua concreta.
assert UnidadeTrabalhoPostgres.__abstractmethods__ == frozenset()


print("Todos os testes do repositório de reservas passaram!")
