"""Painel de consulta e revisão humana das previsões do agente (RF26/RF29)."""
from datetime import timedelta, timezone
from html import escape

from .paginas import layout, aviso, oculto

FUSO = timezone(timedelta(hours=-3))
ROTULOS = {
    "INCONCLUSIVA": "Dados insuficientes",
    "MINIMO_ATINGIDO": "Mínimo já atingido (RF08)",
    "NORMAL": "Sem risco no horizonte",
    "REPOSICAO_SUGERIDA": "Avaliar reposição",
}
DECISOES = {"PENDENTE": "Pendente", "ACEITA": "Aceita", "DESCARTADA": "Descartada"}


def _txt(valor):
    return escape(str(valor))


def painel(chefe, csrf, analises, recomendacoes, mensagem=""):
    corpo = aviso(mensagem)
    corpo += (
        '<section class="cartao"><h2>Agente especialista de controle preventivo</h2>'
        '<p>Protótipo explicável de análise estatística e regras de decisão. '
        'O agente não compra materiais, não modifica o estoque e não substitui o Chefe. '
        'Parâmetros provisórios: últimos 30 dias, pelo menos 7 dias de histórico e '
        'consumo em 3 dias distintos. Alerta preventivo: 7 dias.</p>'
        '<p>A análise automática é executada periodicamente enquanto o servidor local '
        'estiver ligado. Novas recomendações aparecem aqui e na área de '
        '<a href="/notificacoes">Notificações</a>.</p>'
        '<p>A classificação considera apenas saídas por <strong>USO</strong>; '
        'descartes e entradas não são consumo. Movimentações sem finalidade '
        'classificada tornam o resultado inconclusivo.</p>'
        '<form method="post" action="/agente-estoque/analisar">'
        + oculto(csrf)
        + '<button type="submit">Analisar estoque e registrar novas recomendações</button>'
        '</form></section>'
    )
    corpo += (
        '<section class="cartao"><h2>Projeções atuais por lote</h2>'
        '<p>As projeções abaixo são consultivas. O botão acima ou o monitor automático podem registrar recomendações de risco.</p>'
        '<div class="tabela"><table><thead><tr>'
        '<th>Item / lote</th><th>Saldo / mínimo</th><th>Histórico</th>'
        '<th>Consumo médio</th><th>Previsão</th><th>Conclusão</th>'
        '</tr></thead><tbody>'
    )
    for a in analises:
        media = f"{a.consumo_diario:.4f} {a.unidade}/dia" if a.consumo_diario is not None else "—"
        prazo = f"{a.previsao_dias} dias" if a.previsao_dias is not None else "Inconclusiva"
        hist = f"{a.dias_observados} dias; consumo em {a.dias_com_consumo} dias"
        campos = (
            f"{a.nome} / {a.lote}", f"{a.saldo} / {a.limite_minimo} {a.unidade}",
            hist, media, prazo,
        )
        corpo += '<tr>' + ''.join(f'<td>{_txt(c)}</td>' for c in campos)
        corpo += (f'<td><strong>{_txt(ROTULOS.get(a.situacao, a.situacao))}</strong>'
                  f'<p>Regra aplicada: {_txt(a.regra_aplicada)}</p>'
                  f'<p>{_txt(a.justificativa)}</p>'
                  + (f'<p>MAE retrospectivo (7 dias): {_txt(a.mae)} {_txt(a.unidade)}/dia</p>'
                     if a.mae is not None else '')
                  + (f'<p>MAE de referência: {_txt(a.mae_referencia)} {_txt(a.unidade)}/dia; '
                     f'estabilidade retrospectiva: {_txt(a.qualidade)}</p>'
                     if a.mae_referencia is not None else '<p>Validação retrospectiva indisponível.</p>')
                  + '</td></tr>')
    if not analises:
        corpo += '<tr><td colspan="6">Não há lotes ativos para analisar.</td></tr>'
    corpo += '</tbody></table></div></section>'

    corpo += (
        '<section class="cartao"><h2>Recomendações e decisões registradas</h2>'
        '<p>O aceite significa concordar em avaliar a reposição, não criar uma compra. '
        'Cada decisão é identificada, datada e preservada no banco.</p>'
        '<div class="tabela"><table><thead><tr>'
        '<th>Item / lote</th><th>Quando / previsão</th><th>Justificativa</th>'
        '<th>Situação e decisão</th></tr></thead><tbody>'
    )
    for r in recomendacoes:
        instante = r["analisado_em"].astimezone(FUSO).strftime("%d/%m/%Y %H:%M")
        contexto = f'{instante}; {r["previsao_dias"]} dias até o mínimo'
        revisao = DECISOES.get(r["situacao"], r["situacao"])
        if r["decidido_em"] is not None:
            quando = r["decidido_em"].astimezone(FUSO).strftime("%d/%m/%Y %H:%M")
            revisao += f' — por {r["decidido_por_nome"] or "usuário"}, em {quando}'
        corpo += (
            '<tr>'
            + f'<td>{_txt(r["nome"])} / {_txt(r["lote"])}</td>'
            + f'<td>{_txt(contexto)}</td>'
            + f'<td>{_txt(r["justificativa"])}</td>'
            + f'<td><strong>{_txt(revisao)}</strong>'
        )
        if r["situacao"] == "PENDENTE":
            for acao, rotulo in (("ACEITA", "Aceitar avaliação"), ("DESCARTADA", "Descartar")):
                corpo += (
                    '<form method="post" action="/agente-estoque/decidir">'
                    + oculto(csrf)
                    + f'<input type="hidden" name="recomendacao_id" value="{int(r["id"])}">'
                    + f'<input type="hidden" name="decisao" value="{acao}">'
                    + f'<button type="submit" class="secundario">{rotulo}</button></form>'
                )
        corpo += '</td></tr>'
    if not recomendacoes:
        corpo += '<tr><td colspan="4">Nenhuma recomendação registrada.</td></tr>'
    corpo += '</tbody></table></div></section>'
    return layout("Agente de Estoque", corpo, chefe, csrf)
