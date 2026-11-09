
from datetime import timedelta, timezone
from html import escape

from .paginas import (
    layout, aviso, oculto, campo, _selecao_recurso
)


def painel(ator, csrf, itens, movimentacoes,
           mensagem="", erro=False, dados=None,
           alertas=()):
    dados = dados or {}
    fuso = timezone(timedelta(hours=-3))
    corpo = aviso(mensagem, erro)


    
    # Alertas atuais do laboratório.
    corpo += (
        '<section class="cartao" id="alertas">'
        '<h2>🔔 Alertas de estoque</h2>'
    )

    if alertas:
        corpo += '<ul>'

        for alerta in alertas:
            tipo = (
                "Estoque baixo"
                if alerta["tipo"] == "ESTOQUE_BAIXO"
                else "Validade próxima ou vencida"
            )

            data = alerta["criado_em"].astimezone(
                fuso
            ).strftime("%d/%m/%Y %H:%M")

            corpo += (
                '<li>'
                f'<strong>{escape(tipo)}</strong> — '
                f'{escape(alerta["mensagem"])} '
                f'({escape(data)})'
                '</li>'
            )

        corpo += '</ul>'

    else:
        corpo += '<p>Nenhum alerta ativo.</p>'

    corpo += '</section>'

    
    
    
    # Formulário de cadastro.
    campos = (
        campo("nome", "Nome", dados.get("nome", ""))
        + campo("unidade", "Unidade (L, kg, un...)",
                dados.get("unidade", ""))
        + campo("lote", "Lote",
                dados.get("lote", "SEM_LOTE"))
        + campo("validade", "Validade",
                dados.get("validade", ""),
                tipo="date", obrigatorio=False)
    )

    for nome, rotulo, padrao in (
        ("quantidade", "Quantidade inicial", "0"),
        ("limite_estoque_baixo", "Limite de estoque baixo", "0")
    ):
        valor = escape(
            str(dados.get(nome, padrao)), quote=True
        )
        campos += (
            f'<label>{escape(rotulo)}'
            f'<input type="number" name="{nome}" '
            f'step="0.0001" min="0" required '
            f'value="{valor}"></label>'
        )

    corpo += (
        '<section class="cartao">'
        '<h2>Cadastrar item</h2>'
        '<form method="post" action="/estoque">'
        + oculto(csrf)
        + '<input type="hidden" name="acao" value="cadastrar">'
        + f'<div class="campos">{campos}</div>'
        + '<button type="submit">Cadastrar item</button>'
        '</form></section>'
    )

    # Formulário de movimentação.
    ativos = [item for item in itens if item.ativo]

    corpo += (
        '<section class="cartao">'
        '<h2>Entrada e saída de estoque</h2>'
        '<p>Use valor positivo para entrada '
        'e negativo para saída.</p>'
    )

    if ativos:
        opcoes = [
            (item.id, f"{item.nome} — lote {item.lote}")
            for item in ativos
        ]

        selecao = _selecao_recurso(
            "item_id", "Item", opcoes,
            dados.get("item_id", "")
        )

        variacao = escape(
            str(dados.get("variacao", "")), quote=True
        )

        corpo += (
            '<form method="post" action="/estoque">'
            + oculto(csrf)
            + '<input type="hidden" name="acao" '
            'value="movimentar">'
            + '<div class="campos">'
            + selecao
            + '<label>Variação (+ entrada / - saída)'
            f'<input type="number" name="variacao" '
            f'step="0.0001" required value="{variacao}">'
            '</label>'
            + campo(
                "motivo", "Motivo",
                dados.get("motivo", ""), limite=500
            )
            + '</div>'
            '<button type="submit">Registrar movimentação</button>'
            '</form>'
        )
    else:
        corpo += '<p>Cadastre um item ativo primeiro.</p>'

    corpo += '</section>'

    # Tabela de itens.
    linhas = []

    for item in itens:
        situacao = (
            "Estoque baixo" if item.estoque_baixo()
            else "Normal"
        )

        if not item.ativo:
            situacao = "Inativo"

        validade = (
            item.validade.strftime("%d/%m/%Y")
            if item.validade else "—"
        )

        valores = (
            item.id, item.nome, item.lote, item.unidade,
            item.quantidade, item.limite_estoque_baixo,
            validade, situacao
        )

        linhas.append(
            "<tr>" +
            "".join(
                f"<td>{escape(str(valor))}</td>"
                for valor in valores
            ) +
            "</tr>"
        )

    corpo += (
        '<section class="cartao"><h2>Itens cadastrados</h2>'
        '<div class="tabela"><table>'
        '<thead><tr>'
        '<th>ID</th><th>Nome</th><th>Lote</th>'
        '<th>Unidade</th><th>Quantidade</th>'
        '<th>Limite</th><th>Validade</th>'
        '<th>Situação</th>'
        '</tr></thead><tbody>'
        + "".join(linhas)
        + '</tbody></table></div></section>'
    )

    # Histórico de movimentações.
    linhas = []

    for movimento in movimentacoes:
        data = movimento.criado_em.astimezone(fuso)
        valores = (
            data.strftime("%d/%m/%Y %H:%M"),
            movimento.item_id,
            movimento.variacao,
            movimento.quantidade_anterior,
            movimento.quantidade_posterior,
            movimento.motivo
        )

        linhas.append(
            "<tr>" +
            "".join(
                f"<td>{escape(str(valor))}</td>"
                for valor in valores
            ) +
            "</tr>"
        )

    corpo += (
        '<section class="cartao">'
        '<h2>Últimas movimentações</h2>'
        '<div class="tabela"><table>'
        '<thead><tr>'
        '<th>Data</th><th>Item</th><th>Variação</th>'
        '<th>Anterior</th><th>Posterior</th><th>Motivo</th>'
        '</tr></thead><tbody>'
        + "".join(linhas)
        + '</tbody></table></div></section>'
    )

    return layout("Gestão de Estoque", corpo, ator, csrf)
