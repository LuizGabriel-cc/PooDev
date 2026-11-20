from html import escape

from . import paginas
from ..dominio.usuarios import ChefeLaboratorio


_FILTROS = {
    "validados": "Validados",
    "revisao": "Aguardando validação",
}


def _data(instante):
    return instante.strftime("%d/%m/%Y %H:%M") if instante else "—"


def _situacao(protocolo):
    if not protocolo.assinado:
        return "Aguardando assinatura do autor"
    return "Validado pelo Chefe" if protocolo.validado else "Aguardando validação do Chefe"


def lista(usuario, csrf, protocolos, mensagem="", *, situacao="validados"):
    filtros = []
    for chave, rotulo in _FILTROS.items():
        classe, atual = ("botao", ' aria-current="page"') if chave == situacao else ("botao secundario", "")
        filtros.append(f'<a class="{classe}" href="/protocolos?situacao={chave}"{atual}>{rotulo}</a>')
    linhas = []
    for protocolo in protocolos:
        estado = _situacao(protocolo)
        linhas.append(
            f'<tr><td><a href="/protocolos/detalhe?id={protocolo.id}">'
            f'{escape(protocolo.titulo)}</a></td>'
            f'<td>{escape(protocolo.autor_nome)}</td><td>{escape(estado)}</td>'
            f'<td>{_data(protocolo.criado_em)}</td>'
            f'<td><a href="/protocolos/detalhe?id={protocolo.id}&amp;pagina=1#previa-pdf">Visualizar PDF</a></td></tr>'
        )
    corpo = paginas.aviso(mensagem) + f'''
        <p>Os protocolos são compartilhados entre os usuários do mesmo laboratório.
        Envie o PDF e assine nos detalhes do documento. O Chefe confere o conteúdo e valida o protocolo.</p>
        <div class="acoes"><a class="botao" href="/protocolos/novo">Adicionar protocolo</a></div>
        <nav class="acoes" aria-label="Situação dos protocolos">{"".join(filtros)}</nav>
    '''
    corpo += '''
        <div class="tabela"><table><thead><tr>
            <th>Título</th><th>Autor</th><th>Situação</th><th>Cadastro</th><th>Arquivo</th>
        </tr></thead><tbody>''' + (
            "".join(linhas) if linhas else '<tr><td colspan="5">Nenhum protocolo nesta situação.</td></tr>'
        ) + "</tbody></table></div>"
    return paginas.layout("Protocolos", corpo, usuario, csrf)


def novo(usuario, csrf, mensagem="", titulo=""):
    corpo = paginas.aviso(mensagem, True) + f'''
        <section class="cartao">
            <p>Envie o protocolo em PDF (até 5 MB). Depois de revisar o documento, você poderá assiná-lo no sistema.</p>
            <form method="post" action="/protocolos/novo" enctype="multipart/form-data">
                {paginas.oculto(csrf)}
                {paginas.campo("titulo", "Título", titulo, limite=180)}
                <label>Arquivo PDF
                    <input type="file" name="arquivo" accept=".pdf,application/pdf" required>
                </label>
                <div class="acoes"><button>Enviar PDF</button>
                <a href="/protocolos">Cancelar</a></div>
            </form>
        </section>'''
    return paginas.layout("Adicionar protocolo", corpo, usuario, csrf)


def detalhe(usuario, csrf, protocolo, equipamentos, mensagem="", verificacao=None, *,
            pagina_previa=None, total_paginas=None, erro_previa=""):
    linhas = [
        ("Autor", protocolo.autor_nome),
        ("Arquivo", protocolo.nome_arquivo),
        ("Cadastro", _data(protocolo.criado_em)),
        ("Validação pelo Chefe", _data(protocolo.validado_em)),
        ("Situação", _situacao(protocolo)),
    ]
    linhas.append(("Assinado pelo autor em", _data(protocolo.assinado_em)))
    if verificacao is not None:
        linhas.append(("Verificação técnica atual", verificacao.estado.value))
        if verificacao.signatarios:
            linhas.append(("Autor da assinatura", ", ".join(verificacao.signatarios)))
        linhas.append(("Resultado técnico", verificacao.detalhe))
    detalhes = "".join(
        f"<dt>{escape(nome)}</dt><dd>{escape(str(valor))}</dd>"
        for nome, valor in linhas
    )
    corpo = paginas.aviso(mensagem) + f'''
        <section class="cartao">
            <h2>{escape(protocolo.titulo)}</h2>
            <dl>{detalhes}</dl>
            <div class="acoes"><a href="/protocolos">Voltar aos protocolos</a></div>
        </section>'''
    if usuario.id == protocolo.autor_id and not protocolo.assinado:
        corpo += f'''<section class="cartao">
            <h2>Assinar protocolo</h2>
            <p>Revise o PDF antes de assinar. A assinatura será registrada na sua conta
            e permitirá conferir a integridade do documento.</p>
            <form method="post" action="/protocolos/assinar">
                {paginas.oculto(csrf)}
                <input type="hidden" name="protocolo_id" value="{protocolo.id}">
                <button>Assinar protocolo</button>
            </form>
        </section>'''
    if (
        isinstance(usuario, ChefeLaboratorio) and protocolo.pdf_verificado
        and not protocolo.validado and verificacao is not None and verificacao.valida
    ):
        corpo += f'''<section class="cartao">
            <p>Revise o conteúdo e confira o autor antes de aprovar este protocolo.</p>
            <form method="post" action="/protocolos/validar">
                {paginas.oculto(csrf)}
                <input type="hidden" name="protocolo_id" value="{protocolo.id}">
                <label><input type="checkbox" name="identidade_conferida" value="sim" required>
                    Conferi o conteúdo e a autoria deste protocolo.</label>
                <button>Validar protocolo</button>
            </form>
        </section>'''
    vinculos = "".join(
        f"<li>{escape(v.nome)} ({escape(v.patrimonio)})</li>"
        for v in protocolo.vinculos
    ) or "<li>Nenhum equipamento vinculado.</li>"
    corpo += f'<section id="previa-pdf" class="cartao"><h2>Equipamentos vinculados</h2><ul>{vinculos}</ul>'
    if (isinstance(usuario, ChefeLaboratorio) and protocolo.validado
            and verificacao is not None and verificacao.valida):
        vinculados = {v.equipamento_id for v in protocolo.vinculos}
        opcoes = "".join(
            f'<option value="{e.id}">{escape(e.nome)}'
            f' ({escape(e.numero_patrimonio)})</option>'
            for e in equipamentos if e.id not in vinculados
        )
        if opcoes:
            corpo += f'''<form method="post" action="/protocolos/vincular">
                {paginas.oculto(csrf)}
                <input type="hidden" name="protocolo_id" value="{protocolo.id}">
                <label>Vincular a outro equipamento
                    <select name="equipamento_id" required>
                        <option value="">Selecione um equipamento</option>{opcoes}
                    </select>
                </label>
                <button>Vincular equipamento</button>
            </form>'''
    corpo += "</section>"
    corpo += _previa(protocolo.id, pagina_previa, total_paginas, erro_previa)
    return paginas.layout("Detalhes do protocolo", corpo, usuario, csrf)


def _previa(protocolo_id, pagina, total, erro):
    detalhe = f"/protocolos/detalhe?id={protocolo_id}"
    corpo = '<section class="cartao"><h2>Prévia do PDF</h2>'
    if erro:
        corpo += paginas.aviso(erro, True)
    elif pagina is None or total is None:
        corpo += f'<a class="botao secundario" href="{detalhe}&amp;pagina=1#previa-pdf">Visualizar PDF</a>'
    else:
        links = []
        if pagina > 1:
            links.append(f'<a href="{detalhe}&amp;pagina={pagina - 1}#previa-pdf">Página anterior</a>')
        if pagina < total:
            links.append(f'<a href="{detalhe}&amp;pagina={pagina + 1}#previa-pdf">Próxima página</a>')
        corpo += f'''
            <div class="acoes">
                <span>Página {pagina} de {total}</span>
                {"".join(links)}
            </div>
            <img class="previa-pdf" src="/protocolos/previa?id={protocolo_id}&amp;pagina={pagina}"
                 alt="Prévia da página {pagina} de {total} do protocolo">
        '''
    corpo += f'<p><a href="/protocolos/download?id={protocolo_id}">Baixar PDF original</a></p>'
    return corpo + "</section>"
