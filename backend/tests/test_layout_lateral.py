import re
from types import SimpleNamespace

import pytest

from gestao_lab.apresentacao.web import AplicacaoWeb
from gestao_lab.dominio.usuarios import Aluno, ChefeLaboratorio, Professor, TipoAluno
from gestao_lab.infraestrutura.configuracao import Configuracao
from test_web import ClienteWSGI


TOKEN = "a" * 43


@pytest.fixture
def usuarios():
    comuns = {"laboratorio_id": 1, "senha_hash": "hash de teste"}
    return {
        "chefe": ChefeLaboratorio(
            **comuns, id=1, nome="Ágata <script>alert(1)</script> Lima",
            email="chefe@example.org", programa_pos="Biologia", ramal="2100",
        ),
        "professor": Professor(
            **comuns, id=2, nome="Ivo Martins Braga", email="professor@example.org",
            programa_pos="Química",
        ),
        "aluno": Aluno(
            **comuns, id=3, nome="Érica de Sá", email="aluno@example.org",
            matricula="1010", tipo=TipoAluno.MESTRADO, orientador_id=2,
        ),
    }


@pytest.fixture
def cliente_layout(usuarios):
    def preparar(perfil=None):
        sessoes = {} if perfil is None else {TOKEN: usuarios[perfil]}
        autenticacao = SimpleNamespace(identificar=sessoes.get, sair=sessoes.pop)

        def listar(token):
            sessoes[token].exigir_permissao_cadastro()
            return usuarios.values()

        config = Configuracao("postgresql://localhost/banco_nao_utilizado", b"a" * 32)
        cliente = ClienteWSGI(AplicacaoWeb(autenticacao, SimpleNamespace(listar=listar), config))
        if perfil is not None:
            cliente.cookies["lab_sessao"] = TOKEN
        return cliente

    return preparar


def destinos(html):
    return set(re.findall(r'href="([^"]*)"', html))


@pytest.mark.parametrize("perfil,iniciais", [("chefe", "ÁL"), ("professor", "IB"), ("aluno", "ÉS")])
def test_perfil_e_navegacao_mostram_as_acoes_do_usuario(cliente_layout, perfil, iniciais):
    pagina = cliente_layout(perfil).requisitar("/")
    assert pagina.status == 200
    assert 'class="com-menu-lateral"' in pagina.body
    assert 'class="barra-lateral"' in pagina.body
    assert re.search(r'class="avatar-perfil"[^>]*>\s*' + iniciais + r"\s*</", pagina.body)

    links = destinos(pagina.body)
    cabecalhos = re.findall(r"<header\b[^>]*>(.*?)</header>", pagina.body, flags=re.DOTALL)
    assert any({"/notificacoes", "/ajuda"} <= destinos(cabecalho) for cabecalho in cabecalhos)
    assert "Reservas e chaves" in pagina.body
    assert {"/", "/reservas", "/chaves", "/recursos", "/protocolos", "/historico",
            "/ocorrencias", "/notificacoes", "/ajuda"} <= links
    assert {"/cadastros/aluno", "/cadastros/professor", "/manutencao", "/limites-reserva"}.isdisjoint(links)
    assert ("/restricoes" in links) == (perfil == "aluno")

    administracao = {"/usuarios", "/estoque", "/configuracoes"}
    atalhos = re.search(r'class="[^"]*\bperfil-atalhos\b[^"]*"', pagina.body)
    if perfil == "chefe":
        assert "Administração" in pagina.body
        assert atalhos
        assert administracao <= links
    else:
        assert "Administração" not in pagina.body
        assert not atalhos
        assert administracao.isdisjoint(links)


def test_chefe_acessa_cadastros_a_partir_da_lista_e_nome_permanece_escapado(cliente_layout):
    cliente = cliente_layout("chefe")
    pagina = cliente.requisitar("/")
    assert "<script>alert(1)</script>" not in pagina.body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in pagina.body

    usuarios = cliente.requisitar("/usuarios")
    assert usuarios.status == 200
    assert {"/cadastros/aluno", "/cadastros/professor"} <= destinos(usuarios.body)


@pytest.mark.parametrize("perfil,status", [("chefe", 200), ("professor", 403), ("aluno", 403), (None, 303)])
def test_configuracoes_so_fica_disponivel_ao_chefe(cliente_layout, perfil, status):
    cliente = cliente_layout(perfil)
    pagina = cliente.requisitar("/configuracoes")
    assert pagina.status == status
    if perfil == "chefe":
        assert {"/manutencao", "/restricoes", "/limites-reserva"} <= destinos(pagina.body)
        assert cliente.requisitar("/configuracoes", {"csrf": cliente.csrf(pagina)}).status == 405
    elif perfil is None:
        assert ("Location", "/entrar") in pagina.headers


def test_logout_no_layout_continua_exigindo_post_com_csrf(cliente_layout):
    cliente = cliente_layout("chefe")
    perfil = cliente.requisitar("/")
    assert re.search(r'<form\b(?=[^>]*method="post")(?=[^>]*action="/sair")', perfil.body)
    assert cliente.requisitar("/sair").status == 405
    assert cliente.requisitar("/sair", {"csrf": "inválido"}).status == 403

    resposta = cliente.requisitar("/sair", {"csrf": cliente.csrf(perfil)})
    assert resposta.status == 303
    assert "lab_sessao" not in cliente.cookies
    assert cliente.requisitar("/").status == 303


@pytest.mark.parametrize("rota", ["/entrar", "/ajuda", "/offline"])
def test_paginas_publicas_mantem_cabecalho_sem_menu_autenticado(cliente_layout, rota):
    pagina = cliente_layout().requisitar(rota)
    assert pagina.status == 200
    assert "Gestão de Laboratório" in pagina.body
    assert 'class="barra-lateral barra-publica"' in pagina.body
    assert 'pagina-publica' in pagina.body
    assert {"/entrar", "/ajuda"} <= destinos(pagina.body)
    assert "/notificacoes" not in destinos(pagina.body)
    assert 'action="/sair"' not in pagina.body
