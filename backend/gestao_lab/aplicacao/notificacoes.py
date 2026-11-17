import logging
from threading import Event, Thread


LOG = logging.getLogger(__name__)
MAX_TENTATIVAS = 5


class ServicoEnvioEmail:
    def __init__(self, transacao, transporte):
        self._transacao = transacao
        self._transporte = transporte

    def processar_proximo(self):
        # O lock do registro impede que dois processos enviem a mesma notificação ao mesmo tempo.
        with self._transacao() as tx:
            fila = tx.operacoes
            mensagem = fila.proximo_email()
            if mensagem is None:
                return "vazio"
            identificador = mensagem["id"]
            try:
                self._transporte.enviar(mensagem["email"])
            except (OSError, ValueError) as erro:
                tentativa = mensagem["tentativas"] + 1
                descricao = type(erro).__name__
                atraso = 60 * 2 ** (min(tentativa, MAX_TENTATIVAS) - 1)
                fila.registrar_falha_envio(identificador, descricao, atraso, tentativa >= MAX_TENTATIVAS)
                LOG.warning("Falha SMTP no envio %s (%s), tentativa %s.", identificador, descricao, tentativa)
                return "falhou"
            fila.confirmar_envio(identificador)
            return "enviado"


def iniciar_envio_email(servico):
    parada = Event()

    def executar():
        while not parada.is_set():
            try:
                resultado = servico.processar_proximo()
            except Exception as erro:
                LOG.warning("Falha ao consultar a fila SMTP (%s).", type(erro).__name__)
                resultado = "falhou"
            if resultado != "enviado":
                parada.wait(60 if resultado == "falhou" else 30)

    Thread(target=executar, name="envio-email", daemon=True).start()
    return parada
