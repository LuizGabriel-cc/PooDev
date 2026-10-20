
from unittest.mock import MagicMock

from gestao_lab.aplicacao.servicos import ServicoRecursos
from gestao_lab.dominio.usuarios import ChefeLaboratorio

chefe = ChefeLaboratorio(
    id=1,
    laboratorio_id=1,
    nome="Ana",
    email="ana@laboratorio.com",
    senha_hash="hash-de-teste",
    programa_pos="Biociencias"
)

tx = MagicMock()
tx.__enter__.return_value = tx
tx.usuarios.buscar_por_id.return_value = chefe

# Simula a gravação da sala, sem acessar o banco.
tx.recursos.salvar_sala.side_effect = lambda sala: sala

autenticacao = MagicMock()
autenticacao.identificar_na_transacao.return_value = chefe

servico = ServicoRecursos(
    transacao=lambda: tx,
    autenticacao=autenticacao
)

sala = servico.cadastrar_sala(
    "token-de-teste",
    nome="Sala de Quimica",
    identificacao="SQ-01",
    localizacao="Bloco A",
    capacidade=20
)

print("Sala cadastrada:", sala.nome)
print("Laboratorio:", sala.laboratorio_id)
print("Responsavel:", sala.responsavel_usuario_id)
print("Capacidade:", sala.capacidade)

tx.recursos.salvar_sala.assert_called_once()
print("Cadastro simulado com sucesso!")
