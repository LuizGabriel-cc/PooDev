
from datetime import datetime, timezone

from gestao_lab.dominio.historico import (
    HistoricoUso,
    AcaoHistorico
)
from gestao_lab.dominio.erros import DadosInvalidos


agora = datetime.now(timezone.utc)

# TESTE 1 - Registro de criação de reserva.
criacao = HistoricoUso(
    id=1,
    laboratorio_id=1,
    tabela="reserva",
    registro_id="7",
    acao="INSERT",
    registrado_em=agora,
    ator_id=1,
    depois={"estado": "CONFIRMADA"}
)

assert criacao.acao == AcaoHistorico.INSERT
assert not criacao.eh_cancelamento()


# TESTE 2 - Identificar cancelamento.
cancelamento = HistoricoUso(
    id=2,
    laboratorio_id=1,
    tabela="reserva",
    registro_id="7",
    acao="UPDATE",
    registrado_em=agora,
    ator_id=1,
    motivo="Não precisarei usar o equipamento",
    antes={"estado": "CONFIRMADA"},
    depois={"estado": "CANCELADA"}
)

assert cancelamento.eh_cancelamento()


# TESTE 3 - Recurso incluído na reserva em bloco.
recurso_do_bloco = HistoricoUso(
    id=3,
    laboratorio_id=1,
    tabela="reserva_recurso",
    registro_id="7:3",
    acao="INSERT",
    registrado_em=agora,
    depois={
        "reserva_id": 7,
        "recurso_id": 3
    }
)

assert recurso_do_bloco.registro_id == "7:3"
assert not recurso_do_bloco.eh_cancelamento()


# TESTE 4 - Rejeitar identificador inválido.
try:
    HistoricoUso(
        id=-1,
        laboratorio_id=1,
        tabela="reserva",
        registro_id="7",
        acao="INSERT",
        registrado_em=agora
    )
except DadosInvalidos:
    pass
else:
    raise AssertionError(
        "Identificador inválido deveria ser rejeitado."
    )


# TESTE 5 - Rejeitar ação inválida.
try:
    HistoricoUso(
        id=4,
        laboratorio_id=1,
        tabela="reserva",
        registro_id="7",
        acao="INVALIDA",
        registrado_em=agora
    )
except DadosInvalidos:
    pass
else:
    raise AssertionError(
        "Ação inválida deveria ser rejeitada."
    )


print("Todos os 5 testes do histórico passaram!")
