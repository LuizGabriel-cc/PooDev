from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Barrier, Event
from time import monotonic, sleep

from types import SimpleNamespace
import psycopg
import pytest

from gestao_lab.aplicacao.servicos import DadosCadastro
from gestao_lab.dominio.erros import CredenciaisInvalidas, DadosInvalidos
from gestao_lab.dominio.usuarios import Aluno, Perfil
from gestao_lab.infraestrutura.postgres import SessoesPostgres, UsuariosPostgres

pytestmark = [pytest.mark.integracao, pytest.mark.concorrencia]


@pytest.fixture(autouse=True)
def exigir_postgresql_nativo(sistema):
    with psycopg.connect(sistema.url) as conn:
        versao = conn.execute("SELECT version()").fetchone()[0]
    if "PGlite" in versao or "emscripten" in versao:
        pytest.skip("Concorrência exige PostgreSQL nativo; PGlite serializa conexões na instância WASM.")


def criar(sistema, token, recurso_id, inicio, fim):
    return SimpleNamespace(id=sistema.reservas.reservar(token, recurso_id=recurso_id, inicio=inicio, fim=fim))


def competir(primeira, segunda, mensagem):
    barreira = Barrier(2)

    def executar(operacao):
        barreira.wait(timeout=15)
        try:
            return True, operacao()
        except DadosInvalidos as erro:
            return False, str(erro)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futuros = [pool.submit(executar, operacao) for operacao in (primeira, segunda)]
        resultados = [f.result(timeout=30) for f in futuros]
    assert sum(sucesso for sucesso, _ in resultados) == 1, resultados
    assert mensagem in next(valor for sucesso, valor in resultados if not sucesso)


@pytest.mark.parametrize("indice", [0, 2])
def test_reservas_simultaneas_de_sala_ou_mesmo_equipamento_nao_se_sobrepoem(sistema, recursos, portador, periodo, indice):
    _, token = portador
    competir(lambda: criar(sistema, sistema.token, recursos[2].id, *periodo),
             lambda: criar(sistema, token, recursos[indice].id, *periodo), "já está reservado")
    assert len(sistema.reservas.listar(sistema.token)) == 1


def test_limite_por_usuario_resiste_a_confirmacoes_simultaneas(sistema, recursos, periodo):
    sistema.limites.configurar(sistema.token, duracao_minutos=None, quantidade=1)
    competir(lambda: criar(sistema, sistema.token, recursos[2].id, *periodo),
             lambda: criar(sistema, sistema.token, recursos[3].id, *periodo), "simultâneas")
    assert len(sistema.reservas.listar(sistema.token)) == 1


def test_mesma_copia_nao_e_entregue_a_dois_portadores_simultaneamente(sistema, recursos, portador, periodo):
    _, token = portador
    chave = sistema.chaves.cadastrar(sistema.token, codigo_copia=f'CONC-{sistema.chave}', destino_id=recursos[0].id)
    a = criar(sistema, sistema.token, recursos[2].id, *periodo)
    b = criar(sistema, token, recursos[3].id, *periodo)
    competir(lambda: sistema.chaves.retirar(sistema.token, chave.id, a.id),
             lambda: sistema.chaves.retirar(sistema.token, chave.id, b.id), "retirada em aberto")
    assert len(sistema.chaves.painel(sistema.token)[2]) == 1


def aguardar_bloqueio(conn, pid, operacao):
    limite = monotonic() + 10
    while monotonic() < limite and not operacao.done():
        aguardando = conn.execute("""
            SELECT EXISTS (
                SELECT 1 FROM pg_locks
                WHERE NOT granted AND %s = ANY(pg_blocking_pids(pid))
            )
        """, (pid,)).fetchone()[0]
        if aguardando:
            return
        sleep(0.02)
    pytest.fail("A operação deveria aguardar o bloqueio de outra transação.")


def test_login_com_senha_anterior_aguarda_redefinicao(sistema, monkeypatch):
    pid_bloqueador = Queue()
    liberar = Event()
    revogar = SessoesPostgres.revogar_do_usuario

    def revogar_e_aguardar(repo, usuario_id):
        revogar(repo, usuario_id)
        pid_bloqueador.put(repo._conexao.info.backend_pid)
        assert liberar.wait(timeout=20)

    monkeypatch.setattr(SessoesPostgres, "revogar_do_usuario", revogar_e_aguardar)
    nova_senha = "OutraSenhaFicticia2026!"
    with ThreadPoolExecutor(max_workers=2) as pool, psycopg.connect(sistema.url) as conn:
        redefinicao = pool.submit(sistema.inicial.definir_senha, sistema.chefe.email, nova_senha)
        try:
            pid = pid_bloqueador.get(timeout=10)
            login = pool.submit(sistema.auth.entrar, sistema.chefe.email, sistema.senha)
            aguardar_bloqueio(conn, pid, login)
        finally:
            liberar.set()
        redefinicao.result(timeout=10)
        with pytest.raises(CredenciaisInvalidas):
            login.result(timeout=10)

    assert sistema.auth.identificar(sistema.token) is None
    novo_token = sistema.auth.entrar(sistema.chefe.email, nova_senha)
    assert sistema.auth.identificar(novo_token).id == sistema.chefe.id


def test_professor_nao_pode_ser_desativado_durante_cadastro_de_orientando(sistema, dados_professor,
                                                                       monkeypatch):
    professor = sistema.cadastro.cadastrar(sistema.token, Perfil.PROFESSOR, dados_professor)
    dados = DadosCadastro(nome="Orientando de teste", email=f"aluno.{sistema.chave}@example.org",
                          senha=sistema.senha, matricula=sistema.chave, orientador_id=professor.id)
    pid_bloqueador = Queue()
    liberar = Event()
    salvar = UsuariosPostgres.salvar

    def salvar_e_aguardar(repo, usuario):
        if isinstance(usuario, Aluno):
            pid_bloqueador.put(repo._conexao.info.backend_pid)
            assert liberar.wait(timeout=20)
        return salvar(repo, usuario)

    monkeypatch.setattr(UsuariosPostgres, "salvar", salvar_e_aguardar)
    with ThreadPoolExecutor(max_workers=2) as pool, psycopg.connect(sistema.url) as conn:
        cadastro = pool.submit(sistema.cadastro.cadastrar, sistema.token, Perfil.ALUNO, dados)
        try:
            pid = pid_bloqueador.get(timeout=10)
            remocao = pool.submit(sistema.cadastro.remover, sistema.token, professor.id)
            aguardar_bloqueio(conn, pid, remocao)
        finally:
            liberar.set()
        assert cadastro.result(timeout=10).orientador_id == professor.id
        with pytest.raises(DadosInvalidos, match="orienta alunos ativos"):
            remocao.result(timeout=10)


def test_designacao_aguarda_laboratorio_sem_bloquear_copia(sistema, recursos, portador):
    usuario, _ = portador
    chave = sistema.chaves.cadastrar(sistema.token, codigo_copia=f"DES-{sistema.chave}",
                                     destino_id=recursos[0].id)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with psycopg.connect(sistema.url) as conn:
            conn.execute("SELECT id FROM gestao_lab.laboratorio WHERE id=%s FOR UPDATE",
                         (sistema.chefe.laboratorio_id,))
            designacao = pool.submit(sistema.chaves.designar, sistema.token, chave.id, usuario.id)
            aguardar_bloqueio(conn, conn.info.backend_pid, designacao)
            # É a próxima trava que uma retirada de chave obteria após travar o laboratório.
            conn.execute("SELECT id FROM gestao_lab.chave WHERE id=%s FOR UPDATE NOWAIT", (chave.id,))
        designacao.result(timeout=10)

    assert sistema.chaves.consultar_gestao(sistema.token, chave.id)[0].designada_para == usuario.id
