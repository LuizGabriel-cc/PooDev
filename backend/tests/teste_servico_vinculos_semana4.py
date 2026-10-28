
from unittest.mock import MagicMock, Mock

from gestao_lab.dominio.salas import Sala
from gestao_lab.dominio.bancadas import Bancada
from gestao_lab.dominio.equipamentos import Equipamento
from gestao_lab.dominio.usuarios import (
    ChefeLaboratorio,
    Professor
)
from gestao_lab.dominio.erros import (
    AcessoNegado,
    DadosInvalidos
)
from gestao_lab.aplicacao.servicos import ServicoRecursos


dados = {
    "laboratorio_id": 1,
    "responsavel_usuario_id": 1,
    "localizacao": "Bloco A"
}

sala = Sala(
    id=10,
    nome="Sala 1",
    identificacao="S1",
    capacidade=15,
    **dados
)

bancada = Bancada(
    id=20,
    nome="Bancada 1",
    numero_identificacao="B1",
    sala_id=10,
    **dados
)

equipamento = Equipamento(
    id=30,
    nome="Paquimetro",
    numero_patrimonio="213",
    complemento_local="Armario",
    sala_direta_id=10,
    **dados
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

# Simula a transação e os repositórios.
tx = MagicMock()
tx.__enter__.return_value = tx

tx.recursos.listar_equipamentos.return_value = [
    equipamento
]
tx.recursos.buscar_bancada.return_value = bancada
tx.recursos.buscar_sala.return_value = sala

autenticacao = Mock()
autenticacao.identificar_na_transacao.return_value = chefe

servico = ServicoRecursos(
    lambda: tx,
    autenticacao
)


# TESTE 1 — Vincular equipamento.
vinculado = servico.vincular_equipamento(
    "token_teste",
    equipamento_id=30,
    bancada_id=20,
    complemento_local="Bancada 1"
)

assert vinculado.bancada_id == 20
assert vinculado.sala_direta_id is None

tx.recursos.alterar_local_equipamento.assert_called_once_with(
    1, vinculado
)

print("Teste 1: vínculo autorizado e persistência solicitada.")


# TESTE 2 — Desvincular equipamento.
tx.recursos.listar_equipamentos.return_value = [
    vinculado
]
tx.recursos.alterar_local_equipamento.reset_mock()

desvinculado = servico.desvincular_equipamento(
    "token_teste",
    equipamento_id=30,
    complemento_local="Armario"
)

assert desvinculado.bancada_id is None
assert desvinculado.sala_direta_id == 10

tx.recursos.alterar_local_equipamento.assert_called_once_with(
    1, desvinculado
)

print("Teste 2: desvínculo autorizado e persistência solicitada.")


# TESTE 3 — Impedir desvincular equipamento sem bancada.
tx.recursos.alterar_local_equipamento.reset_mock()
tx.recursos.listar_equipamentos.return_value = [
    equipamento
]

try:
    servico.desvincular_equipamento(
        "token_teste",
        equipamento_id=30
    )
except DadosInvalidos:
    pass
else:
    raise AssertionError(
        "Equipamento sem bancada deveria ser rejeitado."
    )

tx.recursos.alterar_local_equipamento.assert_not_called()

print("Teste 3: desvínculo inválido bloqueado.")


# TESTE 4 — Impedir vínculo com outro laboratório.
bancada_outro_lab = Bancada(
    id=90,
    nome="Bancada externa",
    numero_identificacao="B90",
    sala_id=80,
    laboratorio_id=2,
    responsavel_usuario_id=2,
    localizacao="Bloco B"
)

tx.recursos.buscar_bancada.return_value = bancada_outro_lab

try:
    servico.vincular_equipamento(
        "token_teste",
        equipamento_id=30,
        bancada_id=90
    )
except DadosInvalidos:
    pass
else:
    raise AssertionError(
        "Bancada de outro laboratório deveria ser rejeitada."
    )

tx.recursos.alterar_local_equipamento.assert_not_called()

print("Teste 4: outro laboratório bloqueado.")


# TESTE 5 — Impedir Professor de alterar vínculos.
autenticacao.identificar_na_transacao.return_value = professor

try:
    servico.vincular_equipamento(
        "token_teste",
        equipamento_id=30,
        bancada_id=20
    )
except AcessoNegado:
    pass
else:
    raise AssertionError(
        "Professor não deveria alterar vínculos."
    )

tx.recursos.alterar_local_equipamento.assert_not_called()

print("Teste 5: acesso do Professor bloqueado.")

print("Todos os 5 testes do serviço de vínculos passaram!")
