
from gestao_lab.dominio.salas import Sala
from gestao_lab.dominio.bancadas import Bancada
from gestao_lab.dominio.equipamentos import Equipamento
from gestao_lab.dominio.erros import DadosInvalidos


dados = {
    "laboratorio_id": 1,
    "responsavel_usuario_id": 1,
    "localizacao": "Bloco A"
}


# Sala já cadastrada.
sala = Sala(
    id=10,
    nome="Sala 1",
    identificacao="S1",
    capacidade=15,
    **dados
)


# Bancada pertencente à Sala 1.
bancada = Bancada(
    id=20,
    nome="Bancada 1",
    numero_identificacao="B1",
    sala_id=10,
    **dados
)


# Equipamento inicialmente localizado diretamente na sala.
equipamento = Equipamento(
    id=30,
    nome="Paquimetro",
    numero_patrimonio="213",
    complemento_local="Armario",
    sala_direta_id=10,
    **dados
)


# TESTE 1 — Vincular equipamento à bancada.
vinculado = equipamento.vincular_a_bancada(
    bancada,
    complemento_local="Bancada 1"
)

assert vinculado.bancada_id == 20
assert vinculado.sala_direta_id is None
assert vinculado.complemento_local == "Bancada 1"

print("Teste 1: equipamento vinculado com sucesso.")


# TESTE 2 — Conferir imutabilidade.
assert equipamento.bancada_id is None
assert equipamento.sala_direta_id == 10

print("Teste 2: objeto original preservado.")


# TESTE 3 — Desvincular equipamento.
desvinculado = vinculado.desvincular_da_bancada(
    bancada,
    sala,
    complemento_local="Armario"
)

assert desvinculado.bancada_id is None
assert desvinculado.sala_direta_id == 10
assert desvinculado.complemento_local == "Armario"

print("Teste 3: equipamento desvinculado com sucesso.")


# Função auxiliar para validar erros esperados.
def exigir_erro(operacao):
    try:
        operacao()
    except DadosInvalidos:
        return

    raise AssertionError(
        "Era esperado um erro de validação."
    )


# TESTE 4 — Impedir vínculo com outro laboratório.
bancada_outro_lab = Bancada(
    id=50,
    nome="Bancada de outro laboratorio",
    numero_identificacao="BX",
    sala_id=40,
    laboratorio_id=2,
    responsavel_usuario_id=2,
    localizacao="Bloco B"
)

exigir_erro(
    lambda: equipamento.vincular_a_bancada(
        bancada_outro_lab
    )
)

print("Teste 4: outro laboratório bloqueado.")


# TESTE 5 — Impedir desvincular para sala incorreta.
sala_incorreta = Sala(
    id=11,
    nome="Sala 2",
    identificacao="S2",
    capacidade=10,
    **dados
)

exigir_erro(
    lambda: vinculado.desvincular_da_bancada(
        bancada,
        sala_incorreta
    )
)

print("Teste 5: sala incorreta bloqueada.")


# TESTE 6 — Impedir repetir o mesmo vínculo.
exigir_erro(
    lambda: vinculado.vincular_a_bancada(
        bancada
    )
)

print("Teste 6: vínculo duplicado bloqueado.")


# TESTE 7 — Impedir complemento de local vazio.
exigir_erro(
    lambda: equipamento.vincular_a_bancada(
        bancada,
        complemento_local="   "
    )
)

print("Teste 7: complemento inválido bloqueado.")

print("Todos os 7 testes de vínculos passaram!")
