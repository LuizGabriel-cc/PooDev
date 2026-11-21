from unittest.mock import Mock

import pytest

from gestao_lab.aplicacao.notificacoes import ServicoEnvioEmail
from gestao_lab.aplicacao.operacoes import ServicoOperacoes
from gestao_lab.aplicacao.servicos import DadosCadastro
from gestao_lab.apresentacao.web import AplicacaoWeb
from gestao_lab.dominio.erros import AcessoNegado, DadosInvalidos
from gestao_lab.dominio.usuarios import Perfil
from gestao_lab.infraestrutura.configuracao import Configuracao
from test_web import ClienteWSGI


pytestmark = pytest.mark.integracao


@pytest.fixture
def operacoes(sistema):
    return ServicoOperacoes(sistema.transacao, sistema.auth)


def cliente(sistema, operacoes, token):
    app = AplicacaoWeb(sistema.auth, sistema.cadastro,
                      Configuracao(sistema.url, b"chave-de-teste-da-etapa-7"), operacoes=operacoes)
    navegador = ClienteWSGI(app)
    navegador.cookies["lab_sessao"] = token
    return navegador


def enviar(navegador, rota, **dados):
    pagina = navegador.requisitar(rota)
    return navegador.requisitar(rota, dados | {"csrf": navegador.csrf(pagina)})


def marcar_reserva(sistema, usuario, recurso, periodo):
    return sistema.reservas.reservar(usuario, recurso_id=recurso.id, inicio=periodo[0], fim=periodo[1])


def test_restricao_e_reativacao_pelos_formularios(sistema, operacoes, recursos, portador, periodo):
    _, bancada, equipamento, _ = recursos
    aluno, token = portador
    chefe = cliente(sistema, operacoes, sistema.token)
    estudante = cliente(sistema, operacoes, token)
    reserva = marcar_reserva(sistema, token, bancada, periodo)
    dados = {"acao": "proibir", "aluno": aluno.id, "equipamento": equipamento.id, "motivo": "Motivo <privado>"}

    assert chefe.requisitar("/restricoes", dados).status == 403
    assert enviar(estudante, "/restricoes", **dados).status == 403
    assert enviar(chefe, "/restricoes", **dados).status == 303
    assert enviar(chefe, "/restricoes", **dados).status == 400
    restricoes, *_ = operacoes.listar_restricoes(token)
    assert "&lt;privado&gt;" in estudante.requisitar("/restricoes").body
    assert any(a["tipo"] == "PROIBICAO_APLICADA" for a in operacoes.listar_avisos(token))
    assert any(r["id"] == reserva and r["estado"] == "CANCELADA" for r in sistema.reservas.listar(token))
    with pytest.raises((AcessoNegado, DadosInvalidos)):
        marcar_reserva(sistema, token, bancada, periodo)

    tentativa = {"acao": "solicitar", "proibicao": restricoes[0]["id"], "justificativa": "Treinamento concluído"}
    assert enviar(estudante, "/restricoes", **tentativa).status == 303
    assert enviar(estudante, "/restricoes", **tentativa).status == 400
    pedido = operacoes.listar_restricoes(sistema.token)[1][0]
    assert enviar(chefe, "/restricoes", acao="responder", pedido=pedido["id"], decisao="negar", resposta="Revise o roteiro").status == 303
    assert operacoes.listar_restricoes(token)[0][0]["encerrada_em"] is None
    assert enviar(estudante, "/restricoes", **tentativa).status == 303
    pedido = operacoes.listar_restricoes(sistema.token)[1][0]
    assert enviar(chefe, "/restricoes", acao="responder", pedido=pedido["id"], decisao="aprovar", resposta="Treinamento confirmado").status == 303
    assert "Treinamento confirmado" in estudante.requisitar("/notificacoes").body
    assert marcar_reserva(sistema, token, bancada, periodo)


def test_manutencao_bloqueia_reserva_e_respeita_perfil(sistema, operacoes, recursos, portador, periodo):
    _, _, equipamento, outro = recursos
    _, token = portador
    chefe = cliente(sistema, operacoes, sistema.token)
    estudante = cliente(sistema, operacoes, token)
    marcar_reserva(sistema, token, equipamento, periodo)
    reserva_intacta = marcar_reserva(sistema, token, outro, periodo)
    assert estudante.requisitar("/manutencao").status == 403
    assert enviar(chefe, "/manutencao", acao="alterar", equipamento=equipamento.id,
                 estado="MANUTENCAO", motivo="Reparo programado").status == 303
    assert "Em manutenção" in chefe.requisitar("/manutencao").body
    assert any(r["id"] == reserva_intacta and r["estado"] == "CONFIRMADA" for r in sistema.reservas.listar(token))
    with pytest.raises(DadosInvalidos):
        marcar_reserva(sistema, token, equipamento, periodo)
    operacoes.mudar_estado(sistema.token, equipamento=equipamento.id, estado="DISPONIVEL", motivo="Reparo concluído")
    assert marcar_reserva(sistema, token, equipamento, periodo)


def test_ocorrencia_e_leitura_isoladas_por_usuario_e_laboratorio(sistema, operacoes, recursos, portador):
    _, _, equipamento, _ = recursos
    _, token = portador
    externo = sistema.inicial.criar_chefe(f"Outro lab {sistema.chave}", "Bloco B", DadosCadastro(
        nome="Chefe externo", email=f"externo.{sistema.chave}@example.org", senha=sistema.senha, programa_pos="Teste",
    ))
    token_externo = sistema.auth.entrar(externo.email, sistema.senha)
    chefe = cliente(sistema, operacoes, sistema.token)
    estudante = cliente(sistema, operacoes, token)
    outro_lab = cliente(sistema, operacoes, token_externo)
    dados = {"acao": "registrar", "tipo": "DANO", "recurso": equipamento.id, "descricao": "Lente danificada <teste>"}
    assert enviar(outro_lab, "/ocorrencias", **dados).status == 400
    assert enviar(estudante, "/ocorrencias", **dados).status == 303
    ocorrencia = operacoes.listar_ocorrencias(sistema.token)[0][0]
    aviso = operacoes.listar_avisos(sistema.token)[0]
    assert "Lente danificada &lt;teste&gt;" in chefe.requisitar("/notificacoes").body
    assert "Lente danificada" not in outro_lab.requisitar("/ocorrencias").body
    assert "Lente danificada" not in estudante.requisitar("/notificacoes").body
    assert enviar(estudante, "/notificacoes", acao="ler", notificacao=aviso["id"]).status == 403
    assert enviar(chefe, "/notificacoes", acao="ler", notificacao=aviso["id"]).status == 303
    assert operacoes.listar_avisos(sistema.token)[0]["lida_em"] is not None
    assert enviar(outro_lab, "/ocorrencias", acao="encerrar", ocorrencia=ocorrencia["id"]).status == 400
    assert enviar(chefe, "/ocorrencias", acao="encerrar", ocorrencia=ocorrencia["id"]).status == 303
    assert "Resolvida" in estudante.requisitar("/ocorrencias").body


def test_fila_bloqueia_envio_concorrente_e_registra_falha(sistema, operacoes):
    operacoes.registrar_ocorrencia(sistema.token, tipo="OUTRO", descricao="Gerar aviso de teste")
    aviso = operacoes.listar_avisos(sistema.token)[0]
    with sistema.transacao() as tx:
        envio = tx._conexao.execute("""
            UPDATE gestao_lab.envio_email SET proxima_tentativa_em = '2000-01-01'
            WHERE notificacao_id = %s RETURNING id
        """, (aviso["id"],)).fetchone()["id"]
    with sistema.transacao() as primeira, sistema.transacao() as segunda:
        assert primeira.operacoes.proximo_email()["id"] == envio
        outro = segunda.operacoes.proximo_email()
        assert outro is None or outro["id"] != envio

    transporte = Mock()
    processamento = ServicoEnvioEmail(sistema.transacao, transporte)
    transporte.enviar.side_effect = ConnectionError("detalhe privado")
    assert processamento.processar_proximo() == "falhou"
    with sistema.transacao() as tx:
        registro = tx._conexao.execute("""
            SELECT estado, tentativas, ultimo_erro, proxima_tentativa_em > clock_timestamp() AS reagendado
            FROM gestao_lab.envio_email WHERE id = %s
        """, (envio,)).fetchone()
        assert registro == {"estado": "PENDENTE", "tentativas": 1, "ultimo_erro": "ConnectionError", "reagendado": True}
        tx._conexao.execute("UPDATE gestao_lab.envio_email SET proxima_tentativa_em = '2000-01-01' WHERE id = %s", (envio,))

    transporte.enviar.side_effect = None
    assert processamento.processar_proximo() == "enviado"
    transporte.enviar.assert_called_with(sistema.chefe.email)
    assert operacoes.listar_avisos(sistema.token)[0]["id"] == aviso["id"]
    with sistema.transacao() as tx:
        linha = tx._conexao.execute("SELECT estado, tentativas, enviado_em FROM gestao_lab.envio_email WHERE id = %s", (envio,)).fetchone()
        assert linha["estado"] == "ENVIADO" and linha["tentativas"] == 2 and linha["enviado_em"]

    operacoes.registrar_ocorrencia(sistema.token, tipo="OUTRO", descricao="Tentativas esgotadas")
    alerta = operacoes.listar_avisos(sistema.token)[0]
    with sistema.transacao() as tx:
        terminal = tx._conexao.execute("""
            UPDATE gestao_lab.envio_email SET tentativas = 4, proxima_tentativa_em = '2000-01-01'
            WHERE notificacao_id = %s RETURNING id
        """, (alerta["id"],)).fetchone()["id"]
    transporte.enviar.side_effect = ConnectionError()
    assert processamento.processar_proximo() == "falhou"
    with sistema.transacao() as tx:
        linha = tx._conexao.execute("SELECT estado, tentativas FROM gestao_lab.envio_email WHERE id = %s", (terminal,)).fetchone()
        assert linha == {"estado": "FALHOU", "tentativas": 5}
