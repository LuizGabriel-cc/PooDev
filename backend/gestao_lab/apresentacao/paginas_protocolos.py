from html import escape

from . import paginas
from ..dominio.usuarios import ChefeLaboratorio


def _data(instante):
    return instante.strftime("%d/%m/%Y %H:%M") if instante else "—"


def _situacao(protocolo):
    if not protocolo.pdf_verificado:
        return "Validado no fluxo anterior" if protocolo.validado else "Sem verificação digital registrada"
    return "Validado pelo Chefe" if protocolo.validado else "Aguardando conferência do Chefe"


def lista(usuario, csrf, protocolos, mensagem=""):
    linhas = []
    for protocolo in protocolos:
        estado = _situacao(protocolo)
        linhas.append(
            f'<tr><td><a href="/protocolos/detalhe?id={protocolo.id}">'
            f'{escape(protocolo.titulo)}</a></td>'
            f'<td>{escape(protocolo.autor_nome)}</td><td>{escape(estado)}</td>'
            f'<td>{_data(protocolo.criado_em)}</td>'
            f'<td><a href="/protocolos/download?id={protocolo.id}">Baixar PDF</a></td></tr>'
        )
    corpo = paginas.aviso(mensagem) + '''
        <p>Os protocolos são compartilhados entre os usuários do mesmo laboratório.
        O autor assina o PDF no gov.br antes do envio. O sistema verifica a assinatura. O Chefe realiza a validação administrativa.</p>
        <div class="acoes"><a class="botao" href="/protocolos/novo">Adicionar protocolo</a></div>
        <div class="tabela"><table><thead><tr>
            <th>Título</th><th>Autor</th><th>Situação</th><th>Cadastro</th><th>Arquivo</th>
        </tr></thead><tbody>''' + (
            "".join(linhas) if linhas else '<tr><td colspan="5">Nenhum protocolo cadastrado.</td></tr>'
        ) + "</tbody></table></div>"
    return paginas.layout("Protocolos", corpo, usuario, csrf)


def novo(usuario, csrf, mensagem="", titulo=""):
    corpo = paginas.aviso(mensagem, True) + f'''
        <section class="cartao">
            <p>Assine primeiro o PDF no gov.br e envie o arquivo assinado (até 5 MB). O sistema verificará sua assinatura, sem modificar o arquivo. A assinatura só será aceita com uma autoridade confiável configurada.</p>
            <form method="post" action="/protocolos/novo" enctype="multipart/form-data">
                {paginas.oculto(csrf)}
                {paginas.campo("titulo", "Título", titulo, limite=180)}
                <label>Arquivo PDF
                    <input type="file" name="arquivo" accept=".pdf,application/pdf" required>
                </label>
                <div class="acoes"><button>Enviar PDF assinado</button>
                <a href="/protocolos">Cancelar</a></div>
            </form>
        </section>'''
    return paginas.layout("Adicionar protocolo", corpo, usuario, csrf)


def detalhe(usuario, csrf, protocolo, equipamentos, mensagem="", verificacao=None):
    linhas = [
        ("Autor", protocolo.autor_nome),
        ("Arquivo", protocolo.nome_arquivo),
        ("Cadastro", _data(protocolo.criado_em)),
        ("Validação pelo Chefe", _data(protocolo.validado_em)),
        ("Situação", _situacao(protocolo)),
    ]
    if protocolo.pdf_verificado:
        linhas.append(("Verificação digital registrada em", _data(protocolo.assinado_em)))
    elif protocolo.assinado:
        linhas.append(("Assinatura registrada no fluxo anterior", _data(protocolo.assinado_em)))
    if verificacao is not None:
        linhas.append(("Verificação técnica atual", verificacao.estado.value))
        if verificacao.signatarios:
            linhas.append(("Nomes nos certificados", ", ".join(verificacao.signatarios)))
        linhas.append(("Resultado técnico", verificacao.detalhe))
    detalhes = "".join(
        f"<dt>{escape(nome)}</dt><dd>{escape(str(valor))}</dd>"
        for nome, valor in linhas
    )
    corpo = paginas.aviso(mensagem) + f'''
        <section class="cartao">
            <h2>{escape(protocolo.titulo)}</h2>
            <dl>{detalhes}</dl>
            <div class="acoes"><a class="botao secundario"
                href="/protocolos/download?id={protocolo.id}">Baixar PDF original</a>
                <a href="/protocolos">Voltar</a></div>
        </section>'''
    if not protocolo.pdf_verificado:
        corpo += '''
        <p>Para seguir pelo fluxo atual, o autor deve baixar este PDF, assiná-lo no gov.br
        e <a href="/protocolos/novo">enviá-lo como um novo protocolo</a>.</p>'''
    if (
        isinstance(usuario, ChefeLaboratorio) and protocolo.pdf_verificado
        and not protocolo.validado and verificacao is not None and verificacao.valida
    ):
        corpo += f'''<section class="cartao">
            <p>Revise o PDF e confira quem assinou. A comparação de nomes pode coincidir entre homônimos.</p>
            <form method="post" action="/protocolos/validar">
                {paginas.oculto(csrf)}
                <input type="hidden" name="protocolo_id" value="{protocolo.id}">
                <label><input type="checkbox" name="identidade_conferida" value="sim" required>
                    Conferi que o signatário é o autor deste protocolo.</label>
                <button>Validar protocolo</button>
            </form>
        </section>'''
    vinculos = "".join(
        f"<li>{escape(v.nome)} ({escape(v.patrimonio)})</li>"
        for v in protocolo.vinculos
    ) or "<li>Nenhum equipamento vinculado.</li>"
    corpo += f'<section class="cartao"><h2>Equipamentos vinculados</h2><ul>{vinculos}</ul>'
    if isinstance(usuario, ChefeLaboratorio) and protocolo.validado and protocolo.pdf_verificado:
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
    return paginas.layout("Detalhes do protocolo", corpo, usuario, csrf)
