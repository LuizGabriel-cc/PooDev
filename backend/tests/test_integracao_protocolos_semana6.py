"""Fluxo RSA com PostgreSQL descartável, identidade e evidências persistidas."""
import pytest
import psycopg
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from queue import Queue
from threading import Barrier
from time import monotonic, sleep

from gestao_lab.aplicacao.protocolos import ServicoProtocolos
from gestao_lab.dominio.assinaturas_pdf import EstadoAssinatura
from gestao_lab.dominio.erros import AcessoNegado, DadosInvalidos
from gestao_lab.infraestrutura.postgres import UsuariosPostgres


pytestmark = pytest.mark.integracao


def test_protocolos_autoria_assinatura_rsa_validacao_e_vinculo_persistidos(sistema, recursos, portador):
    autor, token_autor = portador
    servico = ServicoProtocolos(sistema.transacao, sistema.auth)
    conteudo = b"%PDF-1.4\n%Documento para teste\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"
    protocolo_id = servico.cadastrar(token_autor, titulo="Manual de utilização", nome_arquivo="manual.pdf",
                                      pdf_original=conteudo)
    protocolo, _ = servico.consultar(token_autor, protocolo_id)
    assert not protocolo.assinado and not protocolo.validado
    assert protocolo.autor_id == autor.id
    assert servico.verificar_assinatura(token_autor, protocolo_id).estado == EstadoAssinatura.SEM_ASSINATURA
    assert [p.id for p in servico.listar(sistema.token, situacao="revisao")] == [protocolo_id]
    with pytest.raises(DadosInvalidos):
        servico.listar(sistema.token, situacao="anteriores")
    with pytest.raises(DadosInvalidos):
        servico.validar(sistema.token, protocolo_id, identidade_conferida=True)
    with pytest.raises(AcessoNegado):
        servico.assinar(sistema.token, protocolo_id)
    servico.assinar(token_autor, protocolo_id)
    assert servico.verificar_assinatura(token_autor, protocolo_id).estado == EstadoAssinatura.VALIDA
    with pytest.raises(DadosInvalidos):
        servico.assinar(token_autor, protocolo_id)
    with pytest.raises(AcessoNegado):
        servico.validar(token_autor, protocolo_id, identidade_conferida=True)
    servico.validar(sistema.token, protocolo_id, identidade_conferida=True)
    servico.vincular(sistema.token, protocolo_id, recursos[2].id)
    servico.vincular(sistema.token, protocolo_id, recursos[2].id)
    atual, _ = servico.consultar(sistema.token, protocolo_id)
    assert atual.validado and atual.assinado and atual.pdf_verificado
    assert servico.listar(sistema.token, situacao="revisao") == []
    assert [p.id for p in servico.listar(sistema.token, situacao="validados")] == [protocolo_id]
    assert [v.equipamento_id for v in atual.vinculos] == [recursos[2].id]
    assert servico.baixar(token_autor, protocolo_id) == ("manual.pdf", conteudo)
    with sistema.transacao() as tx:
        linha = tx._conexao.execute("""
            SELECT assinado_por, validado_por, estado::text AS estado, pdf_original,
                   pdf_politica_verificacao, pdf_sha256, assinatura_rsa, rsa_resumo
            FROM gestao_lab.protocolo WHERE id=%s
        """, (protocolo_id,)).fetchone()
        assert linha["assinado_por"] == autor.id
        assert linha["validado_por"] == sistema.chefe.id
        assert linha["estado"] == "VALIDADO"
        assert bytes(linha["pdf_original"]) == conteudo
        assert linha["pdf_politica_verificacao"] == "rsa-sha256-v1"
        assert bytes(linha["pdf_sha256"]) == sha256(conteudo).digest()
        assert bytes(linha["rsa_resumo"]) == sha256(conteudo).digest()
        assert len(linha["assinatura_rsa"]) == 256
        primeira_chave = tx.protocolos.chave_autor(autor.id, autor.laboratorio_id)
        assert primeira_chave is not None

    outro_protocolo = servico.cadastrar(token_autor, titulo="Segundo manual", nome_arquivo="segundo.pdf",
                                        pdf_original=conteudo)
    servico.assinar(token_autor, outro_protocolo)
    with sistema.transacao() as tx:
        assert tx.protocolos.chave_autor(autor.id, autor.laboratorio_id) == primeira_chave
        assert tx.protocolos.evidencia_assinatura(outro_protocolo, autor.laboratorio_id)["modulo"] == primeira_chave[0]
    for coluna in ("assinatura_rsa", "rsa_resumo"):
        with pytest.raises(DadosInvalidos), sistema.transacao() as tx:
            tx._conexao.execute(f"UPDATE gestao_lab.protocolo SET {coluna}=decode('00','hex') WHERE id=%s", (protocolo_id,))


@pytest.mark.concorrencia
def test_duas_assinaturas_simultaneas_preservam_uma_evidencia(sistema, portador):
    autor, token = portador
    servico = ServicoProtocolos(sistema.transacao, sistema.auth)
    protocolo_id = servico.cadastrar(token, titulo="Assinatura concorrente", nome_arquivo="manual.pdf",
                                      pdf_original=b"%PDF-1.4\nDocumento concorrente\n%%EOF")
    barreira = Barrier(2)

    def assinar():
        barreira.wait(timeout=10)
        try:
            servico.assinar(token, protocolo_id)
            return True
        except DadosInvalidos:
            return False

    with ThreadPoolExecutor(2) as executor:
        futuros = [executor.submit(assinar) for _ in range(2)]
        resultados = [futuro.result(timeout=30) for futuro in futuros]
    assert resultados.count(True) == 1
    assert servico.verificar_assinatura(token, protocolo_id).estado == EstadoAssinatura.VALIDA
    with sistema.transacao() as tx:
        quantidade = tx._conexao.execute(
            "SELECT count(*) AS total FROM gestao_lab.chave_assinatura_usuario WHERE usuario_id=%s",
            (autor.id,),
        ).fetchone()
        assert quantidade["total"] == 1


@pytest.mark.concorrencia
def test_assinar_aguarda_usuario_sem_bloquear_laboratorio(sistema, portador, monkeypatch):
    """Preserva a ordem usuário → laboratório usada também pelo cadastro/remoção."""
    autor, token = portador
    servico = ServicoProtocolos(sistema.transacao, sistema.auth)
    protocolo_id = servico.cadastrar(
        token, titulo="Ordem de bloqueios", nome_arquivo="manual.pdf",
        pdf_original=b"%PDF-1.4\nDocumento para assinatura\n%%EOF",
    )
    conexoes_assinando = Queue()
    buscar_original = UsuariosPostgres.buscar_por_id

    def buscar_com_aviso(repositorio, usuario_id, *, bloquear=False):
        if bloquear and usuario_id == autor.id:
            conexoes_assinando.put(repositorio._conexao.info.backend_pid)
        return buscar_original(repositorio, usuario_id, bloquear=bloquear)

    monkeypatch.setattr(UsuariosPostgres, "buscar_por_id", buscar_com_aviso)
    with ThreadPoolExecutor(max_workers=1) as executor:
        # Liberar esta conexão antes de esperar o executor também garante limpeza
        # quando a regressão causa falha no NOWAIT abaixo.
        with psycopg.connect(sistema.url) as bloqueadora:
            bloqueadora.execute(
                "SELECT id FROM gestao_lab.usuario WHERE id=%s FOR NO KEY UPDATE",
                (autor.id,),
            )
            futuro = executor.submit(servico.assinar, token, protocolo_id)
            pid_assinando = conexoes_assinando.get(timeout=5)
            limite = monotonic() + 4
            while True:
                aguardando_usuario = bloqueadora.execute(
                    "SELECT %s = ANY(pg_blocking_pids(%s))",
                    (bloqueadora.info.backend_pid, pid_assinando),
                ).fetchone()[0]
                if aguardando_usuario:
                    break
                if futuro.done():
                    futuro.result()
                    pytest.fail("A assinatura terminou sem aguardar o bloqueio do usuário.")
                if monotonic() >= limite:
                    pytest.fail("Não foi observada a assinatura aguardando o usuário.")
                sleep(0.02)

            # A espera no usuário foi confirmada no PostgreSQL. A antiga ordem
            # laboratório → usuário já teria bloqueado esta linha e falharia aqui.
            bloqueadora.execute(
                "SELECT id FROM gestao_lab.laboratorio WHERE id=%s FOR UPDATE NOWAIT",
                (autor.laboratorio_id,),
            )
        futuro.result(timeout=30)
    assert servico.verificar_assinatura(token, protocolo_id).estado == EstadoAssinatura.VALIDA
