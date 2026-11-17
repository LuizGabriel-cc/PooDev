from contextlib import nullcontext
import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from gestao_lab import __main__ as entrada


@pytest.fixture
def ambiente_cli(monkeypatch):
    config = SimpleNamespace(
        database_url="postgresql://localhost/poodev_teste_cli",
        porta=8000,
        horas_sessao=8,
        segredo_csrf=b"segredo-exclusivo-do-teste-de-cli",
    )
    monkeypatch.setattr(entrada.Configuracao, "do_ambiente", lambda: config)
    monkeypatch.setattr(entrada, "pedir_senha", lambda: "SenhaDeTeste2026!")
    monkeypatch.setattr("builtins.input", lambda _mensagem: "valor_teste")
    return monkeypatch


@pytest.mark.parametrize("comando", ["criar-chefe", "definir-senha"])
def test_comandos_administrativos_nao_iniciam_servidor(ambiente_cli, comando):
    ambiente_cli.setattr("sys.argv", ["gestao_lab", comando])
    configuracao = Mock()
    configuracao.criar_chefe.return_value = SimpleNamespace(
        nome="Chefe de teste", laboratorio_id=1
    )
    ambiente_cli.setattr(
        entrada, "ServicoConfiguracaoInicial", Mock(return_value=configuracao)
    )
    iniciar_monitoramento = Mock(side_effect=AssertionError("Monitoramento indevido"))
    iniciar_servidor = Mock(side_effect=AssertionError("Servidor indevido"))
    ambiente_cli.setattr(entrada, "iniciar_monitoramento_estoque", iniciar_monitoramento)
    ambiente_cli.setattr(entrada, "make_server", iniciar_servidor)

    entrada.main()

    iniciar_monitoramento.assert_not_called()
    iniciar_servidor.assert_not_called()
    if comando == "criar-chefe":
        configuracao.criar_chefe.assert_called_once()
    else:
        configuracao.definir_senha.assert_called_once()


def test_comando_servir_encerra_monitoramento(ambiente_cli):
    ambiente_cli.setattr("sys.argv", ["gestao_lab", "servir"])
    conexao = Mock()
    verificar_schema = Mock()
    ambiente_cli.setattr(entrada.psycopg, "connect", Mock(return_value=nullcontext(conexao)))
    ambiente_cli.setattr(entrada, "validar_versao_schema", verificar_schema)
    ambiente_cli.delenv("PDF_RAIZES_CONFIAVEIS", raising=False)
    ambiente_cli.delenv("PDF_CERTIFICADOS_INTERMEDIARIOS", raising=False)
    ambiente_cli.setenv("PDF_LISTAS_REVOGACAO", f" lista a.crl {os.pathsep} lista b.der ")
    criar_verificador = Mock()
    ambiente_cli.setattr(entrada, "VerificadorAssinaturaPDF", criar_verificador)
    parada = Mock()
    servidor = Mock()
    monitoramento = Mock(return_value=parada)
    iniciar_servidor = Mock(return_value=nullcontext(servidor))
    ambiente_cli.setattr(entrada, "iniciar_monitoramento_estoque", monitoramento)
    ambiente_cli.setattr(entrada, "make_server", iniciar_servidor)

    entrada.main()

    verificar_schema.assert_called_once_with(conexao)
    criar_verificador.assert_called_once_with([], [], caminhos_crls=["lista a.crl", "lista b.der"])
    monitoramento.assert_called_once()
    iniciar_servidor.assert_called_once()
    servidor.serve_forever.assert_called_once()
    parada.set.assert_called_once()


@pytest.mark.parametrize("falha", ["schema", "porta"])
def test_comando_servir_so_inicia_monitor_com_schema_e_porta(ambiente_cli, falha):
    ambiente_cli.setattr("sys.argv", ["gestao_lab", "servir"])
    ambiente_cli.setattr(entrada.psycopg, "connect", Mock(return_value=nullcontext(Mock())))
    verificar_schema = Mock(
        side_effect=entrada.DadosInvalidos("Banco desatualizado") if falha == "schema" else None
    )
    iniciar_servidor = Mock(side_effect=OSError("Porta ocupada"))
    monitoramento = Mock()
    ambiente_cli.setattr(entrada, "validar_versao_schema", verificar_schema)
    ambiente_cli.setattr(entrada, "make_server", iniciar_servidor)
    ambiente_cli.setattr(entrada, "iniciar_monitoramento_estoque", monitoramento)

    with pytest.raises(SystemExit) as saida:
        entrada.main()

    assert saida.value.code == 1
    assert iniciar_servidor.call_count == (falha == "porta")
    monitoramento.assert_not_called()
