
from datetime import timedelta
from unittest.mock import MagicMock, Mock

from gestao_lab.dominio.laboratorios import Laboratorio
from gestao_lab.dominio.usuarios import (
    ChefeLaboratorio,
    Professor
)
from gestao_lab.dominio.erros import (
    AcessoNegado,
    DadosInvalidos
)
from gestao_lab.aplicacao.servicos import (
    ServicoLimitesReserva
)
from gestao_lab.infraestrutura.postgres import (
    LaboratoriosPostgres
)


laboratorio = Laboratorio(
    id=1,
    nome="Laboratorio Teste",
    localizacao="Bloco A",
    chefe_usuario_id=1
)

chefe = ChefeLaboratorio(
    id=1,
    laboratorio_id=1,
    nome="Chefe Teste",
    email="chefe@example.org",
    senha_hash="hash_teste",
    programa_pos="Computacao"
)

professor = Professor(
    id=2,
    laboratorio_id=1,
    nome="Professor Teste",
    email="professor@example.org",
    senha_hash="hash_teste",
    programa_pos="Computacao"
)

# Simula a transação e o repositório.
tx = MagicMock()
tx.__enter__.return_value = tx

tx.laboratorios.buscar_por_id.return_value = laboratorio

tx.laboratorios.atualizar_limites.side_effect = (
    lambda laboratorio_id, chefe_id, duracao, quantidade:
        laboratorio.configurar_limites(
            duracao, quantidade
        )
)

autenticacao = Mock()
autenticacao.identificar_na_transacao.return_value = chefe

servico = ServicoLimitesReserva(
    lambda: tx,
    autenticacao
)


# TESTE 1: consultar a configuração existente.
assert servico.consultar("token_teste") == laboratorio


# TESTE 2: definir duração de 2 horas e máximo de 3 reservas.
atualizado = servico.configurar(
    "token_teste",
    duracao_minutos=120,
    quantidade=3
)

assert atualizado.duracao_maxima_reserva == timedelta(
    hours=2
)
assert atualizado.max_reservas_simultaneas == 3

tx.laboratorios.atualizar_limites.assert_called_once_with(
    1,
    1,
    timedelta(hours=2),
    3
)

tx.contexto.assert_called_once_with(
    1,
    "Configuração dos limites de reserva"
)

# Objeto original permanece imutável.
assert laboratorio.duracao_maxima_reserva is None


# TESTE 3: impedir quantidade inválida.
try:
    servico.configurar(
        "token_teste",
        duracao_minutos=120,
        quantidade=0
    )
except DadosInvalidos:
    pass
else:
    raise AssertionError(
        "Quantidade zero deveria ser rejeitada."
    )


# TESTE 4: impedir Professor de alterar os limites.
autenticacao.identificar_na_transacao.return_value = professor

tx.laboratorios.atualizar_limites.reset_mock()

try:
    servico.configurar(
        "token_teste",
        duracao_minutos=60,
        quantidade=2
    )
except AcessoNegado:
    pass
else:
    raise AssertionError(
        "Professor não deveria configurar limites."
    )

tx.laboratorios.atualizar_limites.assert_not_called()


# TESTE 5: verificar implementação do repositório.
assert LaboratoriosPostgres.__abstractmethods__ == frozenset()

print("Todos os 5 testes de limites passaram!")
