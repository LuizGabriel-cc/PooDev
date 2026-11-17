from unittest.mock import Mock

import pytest

from gestao_lab.dominio.erros import DadosInvalidos
from gestao_lab.infraestrutura import smtp


@pytest.mark.parametrize("seguranca, porta", [("starttls", 587), ("tls", 465)])
def test_configuracao_e_transporte_smtp_criptografado(monkeypatch, seguranca, porta):
    for nome, valor in {
        "SMTP_HOST": "smtp.example.org", "SMTP_PORT": "", "SMTP_SEGURANCA": seguranca,
        "SMTP_REMETENTE": "aviso@example.org", "SMTP_USUARIO": "usuario", "SMTP_SENHA": "senha-teste",
    }.items():
        monkeypatch.setenv(nome, valor)
    config = smtp.ConfiguracaoSMTP.do_ambiente()
    assert config.porta == porta and "senha-teste" not in repr(config)
    servidor = Mock()
    conectar_starttls, conectar_tls = Mock(return_value=servidor), Mock(return_value=servidor)
    monkeypatch.setattr(smtp.smtplib, "SMTP", conectar_starttls)
    monkeypatch.setattr(smtp.smtplib, "SMTP_SSL", conectar_tls)
    transporte = smtp.TransportadorSMTP(config)
    transporte.enviar("destinatario@example.org")
    if seguranca == "starttls":
        conectar_starttls.assert_called_once_with(config.host, porta, timeout=10)
        conectar_tls.assert_not_called()
        assert servidor.method_calls[0][0] == "starttls"
    else:
        conectar_tls.assert_called_once_with(config.host, porta, timeout=10, context=transporte._contexto)
        conectar_starttls.assert_not_called()
        servidor.starttls.assert_not_called()
    servidor.login.assert_called_once_with(config.usuario, config.senha)
    chamada = servidor.send_message.call_args
    assert chamada.kwargs == {"from_addr": "aviso@example.org", "to_addrs": ["destinatario@example.org"]}
    assert "notificação do laboratório" in chamada.args[0].get_content()
    servidor.close.assert_called_once_with()


def test_smtp_desativado_sem_host_e_recusa_configuracao_insegura(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert smtp.ConfiguracaoSMTP.do_ambiente() is None
    monkeypatch.setenv("SMTP_HOST", "smtp.example.org")
    monkeypatch.setenv("SMTP_SEGURANCA", "sem-tls")
    with pytest.raises(DadosInvalidos, match="starttls ou tls"):
        smtp.ConfiguracaoSMTP.do_ambiente()
