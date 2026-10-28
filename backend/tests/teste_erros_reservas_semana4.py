
from types import SimpleNamespace

from gestao_lab.dominio.erros import (
    AcessoNegado,
    CadastroDuplicado,
    DadosInvalidos,
    FalhaPersistencia,
)

from gestao_lab.infraestrutura.postgres import traduzir_erro


def simular_erro(codigo, mensagem="", restricao=None):
    """Simula um erro recebido do PostgreSQL."""
    return SimpleNamespace(
        sqlstate=codigo,
        diag=SimpleNamespace(
            message_primary=mensagem,
            constraint_name=restricao,
        ),
    )


casos = [
    (
        "23P01",
        "",
        "reserva_recurso_sem_sobreposicao",
        DadosInvalidos,
        "reservado",
    ),
    (
        "42501",
        "Somente o dono ou Chefe pode cancelar",
        None,
        AcessoNegado,
        "titular",
    ),
    (
        "23514",
        "Duração excede o limite do laboratório",
        None,
        DadosInvalidos,
        "duração",
    ),
    (
        "23514",
        "Conjunto contém recurso ou local indisponível",
        None,
        DadosInvalidos,
        "indisponível",
    ),
    (
        "23514",
        "Reserva não está confirmada",
        None,
        DadosInvalidos,
        "confirmada",
    ),
    (
        "23505",
        "",
        "aluno_matricula_key",
        CadastroDuplicado,
        "matrícula",
    ),
    (
        "23503",
        "",
        None,
        DadosInvalidos,
        "vinculados",
    ),
    (
        "08006",
        "",
        None,
        FalhaPersistencia,
        "PostgreSQL",
    ),
]


for codigo, mensagem, restricao, classe, texto in casos:
    erro = simular_erro(codigo, mensagem, restricao)

    resultado = traduzir_erro(erro)

    assert isinstance(resultado, classe), (
        f"Tipo incorreto para SQLSTATE {codigo}"
    )

    assert texto in str(resultado), (
        f"Mensagem incorreta para SQLSTATE {codigo}"
    )

print("Todos os 8 testes de tradução de erros passaram!")
