from html import escape

from ..dominio.usuarios import Aluno, ChefeLaboratorio, Perfil, Professor, TipoAluno

ROTULOS = {Perfil.ALUNO: "Aluno", Perfil.PROFESSOR: "Professor", Perfil.CHEFE: "Chefe de Laboratório"}
CATEGORIAS = {TipoAluno.GRADUACAO: "Graduação", TipoAluno.MESTRADO: "Mestrado",
              TipoAluno.DOUTORADO: "Doutorado", TipoAluno.POS: "Pós"}


def oculto(csrf):
    return f'<input type="hidden" name="csrf" value="{escape(csrf, quote=True)}">'


def layout(titulo, conteudo, usuario=None, csrf=""):
    nav = ''
    if usuario:
        links = '<a href="/">Meu perfil</a>'
      
        if isinstance(usuario, ChefeLaboratorio):
            links += (
                '<a href="/usuarios">Usuários</a>'
                '<a href="/recursos">Recursos</a>'
                '<a href="/cadastros/aluno">Cadastrar aluno</a>'
                '<a href="/cadastros/professor">Cadastrar professor</a>'
            )

        nav = f'<nav>{links}<form method="post" action="/sair">{oculto(csrf)}<button class="secundario">Sair</button></form></nav>'
    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(titulo)} · Gestão de Laboratório</title><link rel="stylesheet" href="/estilo.css"></head>
<body><header><a class="marca" href="/">Gestão de Laboratório</a>{nav}</header>
<main><h1>{escape(titulo)}</h1>{conteudo}</main></body></html>'''


def aviso(mensagem, erro=False):
    return f'<p class="aviso {"erro" if erro else "sucesso"}" role="alert">{escape(mensagem)}</p>' if mensagem else ''


def campo(nome, rotulo, valor="", tipo="text", obrigatorio=True, limite=120, autocomplete=None):
    obrigacao = " required" if obrigatorio else ""
    completar = f' autocomplete="{autocomplete}"' if autocomplete else ''
    minimo = ' minlength="12"' if tipo == "password" and autocomplete == "new-password" else ''
    return f'<label>{escape(rotulo)}<input name="{nome}" type="{tipo}" value="{escape(str(valor), quote=True)}" maxlength="{limite}"{obrigacao}{completar}{minimo}></label>'


def login(csrf, mensagem="", email=""):
    conteudo = aviso(mensagem, True) + f'''<section class="cartao estreito"><p>Entre com sua conta para acessar o laboratório.</p>
<form method="post" action="/entrar">{oculto(csrf)}
{campo("email", "E-mail", email, "email", limite=254, autocomplete="username")}
{campo("senha", "Senha", tipo="password", limite=128, autocomplete="current-password")}
<button>Entrar</button></form></section>'''
    return layout("Entrar", conteudo)


def perfil(usuario, csrf):
    dados = [("Nome", usuario.nome), ("E-mail", usuario.email), ("Perfil", ROTULOS[usuario.perfil])]
    if isinstance(usuario, Professor):
        dados += [("Programa de pós", usuario.programa_pos), ("Ramal", usuario.ramal or "Não informado")]
    if isinstance(usuario, Aluno):
        dados += [("Matrícula", usuario.matricula), ("Categoria", CATEGORIAS[usuario.tipo])]
    detalhes = ''.join(f'<dt>{escape(k)}</dt><dd>{escape(str(v))}</dd>' for k, v in dados)
    acao = '<a class="botao" href="/usuarios">Gerenciar usuários</a>' if isinstance(usuario, ChefeLaboratorio) else ''
    return layout("Meu perfil", f'<section class="cartao"><dl>{detalhes}</dl>{acao}</section>', usuario, csrf)


def usuarios(lista, ator, csrf, mensagem=""):
    linhas = []

    for u in lista:
        detalhe = (
            f'Matrícula: {u.matricula}'
            if isinstance(u, Aluno)
            else u.programa_pos
        )

        acao = (
            f'<a class="botao secundario" '
            f'href="/usuarios/remover?id={u.id}">'
            f'Remover cadastro</a>'
            if u.ativo and not isinstance(u, ChefeLaboratorio)
            else '—'
        )

        linhas.append(
            f'<tr>'
            f'<td>{escape(u.nome)}</td>'
            f'<td>{escape(u.email)}</td>'
            f'<td>{ROTULOS[u.perfil]}</td>'
            f'<td>{escape(detalhe)}</td>'
            f'<td>{"Ativo" if u.ativo else "Inativo"}</td>'
            f'<td>{acao}</td>'
            f'</tr>'
        )

    corpo = aviso(mensagem) + f'''
    <p>Contas vinculadas ao seu laboratório.
    A remoção desativa o acesso e preserva o histórico.</p>

    <div class="acoes">
        <a class="botao" href="/cadastros/aluno">
            Cadastrar aluno
        </a>
        <a class="botao secundario" href="/cadastros/professor">
            Cadastrar professor
        </a>
    </div>

    <div class="tabela">
        <table>
            <thead>
                <tr>
                    <th>Nome</th>
                    <th>E-mail</th>
                    <th>Perfil</th>
                    <th>Dados acadêmicos</th>
                    <th>Situação</th>
                    <th>Ação</th>
                </tr>
            </thead>
            <tbody>{''.join(linhas)}</tbody>
        </table>
    </div>'''

    return layout("Usuários", corpo, ator, csrf)


def cadastro(perfil_cadastro, ator, csrf, orientadores, dados=None, mensagem=""):
    dados = dados or {}
    corpo = aviso(mensagem, True) + '<section class="cartao"><p>O cadastro será vinculado ao seu laboratório.</p>'
    rota = "aluno" if perfil_cadastro == Perfil.ALUNO else "professor"
    corpo += f'<form method="post" action="/cadastros/{rota}">{oculto(csrf)}<div class="campos">'
    corpo += campo("nome", "Nome completo", dados.get("nome", ""), autocomplete="name")
    corpo += campo("email", "E-mail", dados.get("email", ""), "email", limite=254, autocomplete="email")
    if perfil_cadastro == Perfil.ALUNO:
        corpo += campo("matricula", "Matrícula", dados.get("matricula", ""), limite=64)
        opcoes = ''.join(f'<option value="{t.value}"{" selected" if dados.get("tipo", "GRADUACAO") == t.value else ""}>{CATEGORIAS[t]}</option>' for t in TipoAluno)
        corpo += f'<label>Categoria<select name="tipo" required>{opcoes}</select></label>'
        opcoes = '<option value="">Selecione um orientador</option>' + ''.join(
            f'<option value="{p.id}"{" selected" if str(dados.get("orientador_id", "")) == str(p.id) else ""}>{escape(p.nome)}</option>' for p in orientadores)
        corpo += f'<label>Orientador<select name="orientador_id" required>{opcoes}</select></label>'
    else:
        corpo += campo("programa_pos", "Programa de pós", dados.get("programa_pos", ""))
        corpo += campo("ramal", "Ramal", dados.get("ramal", ""), obrigatorio=False, limite=40)
    # Nunca devolvemos a senha em um formulário que apresentou erro.
    corpo += campo("senha", "Senha inicial (12 a 128 caracteres)", tipo="password", limite=128, autocomplete="new-password")
    corpo += campo("confirmacao", "Confirmar senha", tipo="password", limite=128, autocomplete="new-password")
    corpo += '</div><div class="acoes"><button>Cadastrar</button><a href="/usuarios">Voltar</a></div></form></section>'
    titulo = "Cadastrar aluno" if perfil_cadastro == Perfil.ALUNO else "Cadastrar professor"
    return layout(titulo, corpo, ator, csrf)


def confirmar_remocao(alvo, ator, csrf):
    nome = escape(alvo.nome)
    email = escape(alvo.email)

    conteudo = f'''
    <section class="cartao estreito">
        <p>
            Deseja remover o cadastro de
            <strong>{nome}</strong> ({email})?
        </p>

        <p>
            O acesso será desativado e as sessões abertas
            serão encerradas. Os registros históricos
            serão preservados.
        </p>

        <form method="post" action="/usuarios/remover">
            {oculto(csrf)}

            <input
                type="hidden"
                name="usuario_id"
                value="{alvo.id}"
            >

            <div class="acoes">
                <button>Confirmar remoção</button>
                <a href="/usuarios">Cancelar</a>
            </div>
        </form>
    </section>
    '''

    return layout(
        "Confirmar remoção de cadastro",
        conteudo,
        ator,
        csrf
    )


def _selecao_recurso(
    nome, rotulo, opcoes, selecionado="", obrigatorio=True
):
    itens = ['<option value="">Selecione...</option>']

    for identificador, descricao in opcoes:
        valor = str(identificador)
        marcado = (
            ' selected'
            if str(selecionado) == valor
            else ''
        )

        itens.append(
            f'<option value="{escape(valor, quote=True)}"{marcado}>'
            f'{escape(str(descricao))}</option>'
        )

    atributo = ' required' if obrigatorio else ''

    return (
        f'<label>{escape(rotulo)}'
        f'<select name="{escape(nome, quote=True)}"{atributo}>'
        f'{"".join(itens)}</select></label>'
    )



def _pagina_cadastro_recurso(
    titulo, rota, campos_html, ator, csrf,
    mensagem="", instrucao=""
):
    corpo = aviso(mensagem, True)
    corpo += '<section class="cartao">'

    corpo += (
        '<p>O recurso será vinculado ao laboratório '
        'do Chefe autenticado.</p>'
    )

    if instrucao:
        corpo += f'<p>{escape(instrucao)}</p>'

    corpo += (
        f'<form method="post" action="{rota}">'
        f'{oculto(csrf)}'
        f'<div class="campos">{campos_html}</div>'
        '<div class="acoes">'
        '<button type="submit">Cadastrar</button>'
        '<a href="/recursos">Voltar</a>'
        '</div></form></section>'
    )

    return layout(titulo, corpo, ator, csrf)



def formulario_sala(ator, csrf, dados=None, mensagem=""):
    dados = dados or {}

    campos = (
        campo(
            "nome", "Nome da sala",
            dados.get("nome", "")
        )
        + campo(
            "identificacao", "Identificação",
            dados.get("identificacao", ""), limite=80
        )
        + campo(
            "localizacao", "Localização",
            dados.get("localizacao", ""), limite=200
        )
        + campo(
            "capacidade", "Capacidade (pessoas)",
            dados.get("capacidade", ""),
            tipo="number", limite=9
        )
    )

    return _pagina_cadastro_recurso(
        "Cadastrar sala",
        "/cadastros/sala",
        campos, ator, csrf, mensagem
    )



def formulario_bancada(
    ator, csrf, salas, dados=None, mensagem=""
):
    dados = dados or {}

    opcoes = [
        (s.id, f"{s.identificacao} — {s.nome}")
        for s in salas if s.id is not None
    ]

    campos = (
        campo(
            "nome", "Nome da bancada",
            dados.get("nome", "")
        )
        + campo(
            "numero_identificacao",
            "Identificação da bancada",
            dados.get("numero_identificacao", ""),
            limite=80
        )
        + _selecao_recurso(
            "sala_id",
            "Sala",
            opcoes,
            dados.get("sala_id", "")
        )
    )

    return _pagina_cadastro_recurso(
        "Cadastrar bancada",
        "/cadastros/bancada",
        campos, ator, csrf, mensagem
    )




def formulario_equipamento(
    ator, csrf, salas, bancadas, dados=None, mensagem=""
):
    dados = dados or {}

    opcoes_salas = [
        (s.id, f"{s.identificacao} — {s.nome}")
        for s in salas if s.id is not None
    ]

    opcoes_bancadas = [
        (b.id, f"{b.numero_identificacao} — {b.nome}")
        for b in bancadas if b.id is not None
    ]

    campos = (
        campo(
            "nome", "Nome do equipamento",
            dados.get("nome", "")
        )
        + campo(
            "numero_patrimonio", "Número de patrimônio",
            dados.get("numero_patrimonio", ""), limite=80
        )
        + campo(
            "complemento_local", "Complemento do local",
            dados.get("complemento_local", ""), limite=200
        )
        + _selecao_recurso(
            "bancada_id", "Bancada (opcional)",
            opcoes_bancadas, dados.get("bancada_id", ""),
            False
        )
        + _selecao_recurso(
            "sala_direta_id", "Sala direta (opcional)",
            opcoes_salas, dados.get("sala_direta_id", ""),
            False
        )
        + campo(
            "foto_uri", "Endereço da foto (opcional)",
            dados.get("foto_uri", ""),
            obrigatorio=False, limite=500
        )
        + campo(
            "observacao", "Observação (opcional)",
            dados.get("observacao", ""),
            obrigatorio=False, limite=500
        )
    )

    return _pagina_cadastro_recurso(
        "Cadastrar equipamento",
        "/cadastros/equipamento",
        campos, ator, csrf, mensagem,
        instrucao=(
            "Selecione uma bancada OU uma sala direta, "
            "nunca ambas."
        )
    )



def _lista_visual_recursos(itens):
    if not itens:
        return "<p>Nenhum recurso cadastrado.</p>"

    linhas = "".join(
        f"<li>{escape(str(item))}</li>"
        for item in itens
    )

    return f"<ul>{linhas}</ul>"


def painel_recursos(
    ator, csrf, salas, bancadas, equipamentos, mensagem=""
):
    descricoes_salas = [
        f"{s.identificacao} — {s.nome} "
        f"(capacidade: {s.capacidade})"
        for s in salas
    ]

    descricoes_bancadas = [
        f"{b.numero_identificacao} — {b.nome}"
        for b in bancadas
    ]

    descricoes_equipamentos = [
        f"{e.numero_patrimonio} — {e.nome}"
        for e in equipamentos
    ]

    corpo = aviso(mensagem)

    corpo += '''
    <section class="cartao">
        <h2>Gerenciar recursos</h2>
        <p>Cadastre e consulte os recursos do laboratório.</p>

        <div class="acoes">
            <a class="botao" href="/cadastros/sala">
                Cadastrar sala
            </a>
            <a class="botao secundario" href="/cadastros/bancada">
                Cadastrar bancada
            </a>
            <a class="botao secundario" href="/cadastros/equipamento">
                Cadastrar equipamento
            </a>
        </div>
    </section>
    '''

    corpo += (
        '<section class="cartao"><h2>Salas</h2>'
        + _lista_visual_recursos(descricoes_salas)
        + '</section>'
    )

    corpo += (
        '<section class="cartao"><h2>Bancadas</h2>'
        + _lista_visual_recursos(descricoes_bancadas)
        + '</section>'
    )

    corpo += (
        '<section class="cartao"><h2>Equipamentos</h2>'
        + _lista_visual_recursos(descricoes_equipamentos)
        + '</section>'
    )

    return layout("Recursos do laboratório", corpo, ator, csrf)

