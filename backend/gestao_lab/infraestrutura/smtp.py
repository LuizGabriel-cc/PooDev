from contextlib import suppress
from dataclasses import dataclass, field
from email.errors import HeaderParseError
from email.headerregistry import Address
from email.message import EmailMessage
import os
import smtplib
import ssl

from ..dominio.erros import DadosInvalidos
from ..dominio.usuarios import normalizar_email


def _endereco_unico(valor):
    try:
        return Address(addr_spec=valor)
    except (ValueError, HeaderParseError) as erro:
        raise ValueError("Endereço SMTP inválido.") from erro


@dataclass(frozen=True)
class ConfiguracaoSMTP:
    host: str
    porta: int
    seguranca: str
    remetente: str
    usuario: str = ""
    senha: str = field(default="", repr=False)

    @classmethod
    def do_ambiente(cls):
        host = os.getenv("SMTP_HOST", "").strip()
        if not host:
            return None
        seguranca = os.getenv("SMTP_SEGURANCA", "starttls").strip().lower()
        if seguranca not in {"starttls", "tls"}:
            raise DadosInvalidos("SMTP_SEGURANCA deve ser starttls ou tls.")
        try:
            porta = int(os.getenv("SMTP_PORT", "").strip() or (465 if seguranca == "tls" else 587))
        except ValueError as erro:
            raise DadosInvalidos("SMTP_PORT deve ser um número inteiro.") from erro
        if not 1 <= porta <= 65535:
            raise DadosInvalidos("SMTP_PORT fora do intervalo permitido.")
        remetente = normalizar_email(os.getenv("SMTP_REMETENTE", ""))
        try:
            _endereco_unico(remetente)
        except ValueError as erro:
            raise DadosInvalidos("Informe um SMTP_REMETENTE válido.") from erro
        usuario = os.getenv("SMTP_USUARIO", "").strip()
        senha = os.getenv("SMTP_SENHA", "")
        if bool(usuario) != bool(senha):
            raise DadosInvalidos("Configure SMTP_USUARIO e SMTP_SENHA juntos.")
        return cls(host, porta, seguranca, remetente, usuario, senha)


class TransportadorSMTP:
    def __init__(self, config):
        self._config = config
        self._contexto = ssl.create_default_context()

    def enviar(self, destinatario):
        config = self._config
        mensagem = EmailMessage()
        mensagem["From"] = _endereco_unico(config.remetente)
        mensagem["To"] = _endereco_unico(destinatario)
        mensagem["Subject"] = "Nova notificação no PooDev"
        mensagem.set_content("Você recebeu uma notificação do laboratório. Entre no PooDev e abra Notificações para consultar os detalhes.")

        if config.seguranca == "tls":
            smtp = smtplib.SMTP_SSL(config.host, config.porta, timeout=10, context=self._contexto)
        else:
            smtp = smtplib.SMTP(config.host, config.porta, timeout=10)
        try:
            if config.seguranca == "starttls":
                smtp.starttls(context=self._contexto)
            if config.usuario:
                smtp.login(config.usuario, config.senha)
            smtp.send_message(mensagem, from_addr=config.remetente, to_addrs=[destinatario])
        finally:
            with suppress(OSError):
                smtp.close()
