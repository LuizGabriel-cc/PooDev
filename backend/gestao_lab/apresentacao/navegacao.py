from contextvars import ContextVar

from ..dominio.usuarios import Aluno, ChefeLaboratorio


rota_atual = ContextVar("rota_atual", default="")


def icone(nome):
    return f'<span class="icone-menu icone-{nome}" aria-hidden="true"></span>'


def _link(rota, rotulo, simbolo="", *, prefixos=()):
    atual = rota_atual.get()
    exato = atual == rota
    ativo = exato or (rota != "/" and atual.startswith(rota + "/")) or atual in prefixos
    classe = ' class="menu-link menu-ativo"' if ativo else ' class="menu-link"'
    corrente = ' aria-current="page"' if exato else ''
    return f'<a href="{rota}"{classe}{corrente}>{icone(simbolo) if simbolo else ""}{rotulo}</a>'


def lateral(usuario):
    atual = rota_atual.get()
    aberto = ' open class="menu-ativo"' if atual.startswith(("/reservas", "/chaves")) else ""
    reservas = (
        f'<details{aberto}><summary>{icone("calendario")}Reservas e chaves</summary>'
        f'<div class="submenu-lateral">{_link("/reservas", "Reservas")}'
        f'{_link("/chaves", "Chaves")}</div></details>'
    )
    laboratorio = (
        reservas
        + _link("/recursos", "Recursos", "recursos",
                prefixos=("/cadastros/sala", "/cadastros/bancada", "/cadastros/equipamento"))
        + _link("/protocolos", "Protocolos", "documento")
        + _link("/historico", "Histórico", "historico")
        + _link("/ocorrencias", "Ocorrências", "ocorrencia")
    )
    if isinstance(usuario, Aluno):
        laboratorio += _link("/restricoes", "Restrições", "restricao")

    itens = (_link("/", "Meu perfil", "perfil")
             + '<p class="legenda-menu">Laboratório</p>' + laboratorio)
    if isinstance(usuario, ChefeLaboratorio):
        itens += (
            '<p class="legenda-menu">Administração</p>'
            + _link("/usuarios", "Usuários", "usuarios", prefixos=("/cadastros/aluno", "/cadastros/professor"))
            + _link("/estoque", "Estoque", "estoque")
            + _link("/agente-estoque", "Agente de estoque", "estoque")
            + _link("/configuracoes", "Configurações", "configuracoes",
                    prefixos=("/manutencao", "/restricoes", "/limites-reserva"))
        )
    return f'''
    <aside class="barra-lateral">
        <a class="marca-lateral" href="/">
            <img src="/pwa/icone-192.png" width="40" height="40" alt="">
            <span>Gestão de Laboratório</span>
        </a>
        <nav class="menu-lateral menu-desktop" aria-label="Menu principal">{itens}</nav>
        <details class="menu-compacto">
            <summary>Menu</summary>
            <nav class="menu-lateral" aria-label="Menu principal">{itens}</nav>
        </details>
    </aside>'''


def atalhos(itens):
    links = "".join(
        f'<li><a class="atalho-perfil" href="{rota}">'
        f'<span class="icone-atalho tom-{simbolo}">{icone(simbolo)}</span>'
        f'<span class="texto-atalho"><strong>{titulo}</strong><small>{descricao}</small></span>'
        '<span class="seta-atalho" aria-hidden="true">→</span></a></li>'
        for rota, simbolo, titulo, descricao in itens
    )
    return f'<ul class="lista-atalhos">{links}</ul>'


def lateral_publica():
    itens = _link("/entrar", "Entrar", "perfil") + _link("/ajuda", "Ajuda", "ajuda")
    return f'''
        <aside class="barra-lateral barra-publica">
            <a class="marca-lateral" href="/entrar">
                <img src="/pwa/icone-192.png" width="40" height="40" alt="">
                <span>Gestão de Laboratório</span>
            </a>
            <nav class="menu-lateral menu-desktop" aria-label="Acesso e ajuda">{itens}</nav>
            <details class="menu-compacto">
                <summary>Menu</summary>
                <nav class="menu-lateral" aria-label="Acesso e ajuda">{itens}</nav>
            </details>
            <p class="identificacao-publica">Sistema de Gestão de Laboratório de Pesquisa</p>
        </aside>'''
