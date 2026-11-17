from html import escape

from .formatacao import horario
from .paginas import aviso, layout, oculto
from ..aplicacao.operacoes import ESTADOS_MANUTENCAO, TIPOS_OCORRENCIA
from ..dominio.usuarios import Aluno, ChefeLaboratorio


def _form(rota, csrf, acao, campos, botao):
    return (f'<form method="post" action="{rota}">{oculto(csrf)}'
            f'<input type="hidden" name="acao" value="{acao}">{campos}<button>{botao}</button></form>')


def _selecao(nome, rotulo, opcoes, *, obrigatorio=True, atual=None):
    inicio = '<option value="">Selecione</option>' if obrigatorio else '<option value="">Sem vínculo</option>'
    itens = ''.join(
        f'<option value="{escape(str(valor), quote=True)}"{" selected" if valor == atual else ""}>'
        f'{escape(rotulo_opcao)}</option>' for valor, rotulo_opcao in opcoes
    )
    return f'<label>{rotulo}<select name="{nome}"{" required" if obrigatorio else ""}>{inicio}{itens}</select></label>'


def _texto(campo, rotulo):
    return f'<label>{rotulo}<textarea name="{campo}" maxlength="500" rows="3" required></textarea></label>'


def _equipamento(equipamento):
    return f'{equipamento["nome"]} ({equipamento["numero_patrimonio"]})'


def restricoes(usuario, csrf, dados, mensagem, erro, fuso):
    proibicoes, pedidos, alunos, equipamentos = dados
    chefe = isinstance(usuario, ChefeLaboratorio)
    corpo = aviso(mensagem, erro)
    if chefe:
        campos = (
            _selecao("aluno", "Aluno", ((a["id"], a["nome"]) for a in alunos))
            + _selecao("equipamento", "Equipamento", ((e["id"], _equipamento(e)) for e in equipamentos))
            + _texto("motivo", "Motivo")
        )
        corpo += '<section class="cartao"><h2>Restringir equipamento</h2>'
        corpo += '<p>A restrição cancela as reservas afetadas do aluno.</p>'
        corpo += _form("/restricoes", csrf, "proibir", campos, "Aplicar restrição") + '</section>'
    corpo += '<section><h2>Restrições registradas</h2>'
    if not proibicoes:
        corpo += '<p>Nenhuma restrição encontrada.</p>'
    for registro in proibicoes:
        estado = 'Encerrada' if registro["encerrada_em"] else 'Ativa'
        corpo += (f'<article class="cartao"><h3>{escape(registro["equipamento"])} '
                  f'({escape(registro["numero_patrimonio"])})</h3>'
                  f'<p>{escape(registro["aluno"])} · {estado} · {horario(registro["criada_em"], fuso)}</p>'
                  f'<p>{escape(registro["motivo"])}</p>')
        if isinstance(usuario, Aluno) and not registro["encerrada_em"] and not registro["pedido_pendente"]:
            campos = f'<input type="hidden" name="proibicao" value="{registro["id"]}">' + _texto("justificativa", "Justificativa")
            corpo += _form("/restricoes", csrf, "solicitar", campos, "Solicitar reativação")
        corpo += '</article>'
    corpo += '</section><section><h2>Pedidos de reativação</h2>'
    if not pedidos:
        corpo += '<p>Nenhum pedido registrado.</p>'
    estados = {"PENDENTE": "Pendente", "APROVADA": "Aprovado", "NEGADA": "Negado"}
    for pedido in pedidos:
        corpo += (f'<article class="cartao"><h3>{escape(pedido["equipamento"])}</h3>'
                  f'<p>{escape(pedido["aluno"])} · {estados[pedido["estado"]]} · {horario(pedido["solicitada_em"], fuso)}</p>'
                  f'<p>Justificativa: {escape(pedido["justificativa"])}</p>')
        if pedido["resposta"]:
            corpo += f'<p>Resposta: {escape(pedido["resposta"])}</p>'
        if chefe and pedido["estado"] == "PENDENTE":
            campos = (f'<input type="hidden" name="pedido" value="{pedido["id"]}">'
                      + _selecao("decisao", "Decisão", (("aprovar", "Aprovar"), ("negar", "Negar")))
                      + _texto("resposta", "Resposta"))
            corpo += _form("/restricoes", csrf, "responder", campos, "Registrar decisão")
        corpo += '</article>'
    return layout("Restrições e reativação", corpo + '</section>', usuario, csrf)


def manutencao(usuario, csrf, equipamentos, mensagem, erro, _fuso):
    corpo = aviso(mensagem, erro)
    if not equipamentos:
        corpo += '<p>Nenhum equipamento cadastrado para manutenção.</p>'
    for equipamento in equipamentos:
        campos = (f'<input type="hidden" name="equipamento" value="{equipamento["id"]}">'
                  + _selecao("estado", "Estado", ESTADOS_MANUTENCAO.items(), atual=equipamento["estado"])
                  + _texto("motivo", "Motivo"))
        corpo += (f'<section class="cartao"><h2>{escape(_equipamento(equipamento))}</h2>'
                  + _form("/manutencao", csrf, "alterar", campos, "Atualizar estado") + '</section>')
    return layout("Manutenção de equipamentos", corpo, usuario, csrf)


def ocorrencias(usuario, csrf, dados, mensagem, erro, fuso):
    registros, recursos, itens = dados
    campos = (
        _selecao("tipo", "Tipo", TIPOS_OCORRENCIA.items())
        + _selecao("recurso", "Recurso (dano)", ((r["id"], r["nome"]) for r in recursos), obrigatorio=False)
        + _selecao("item", "Item (falta de estoque)", ((i["id"], f'{i["nome"]} ({i["lote"]})') for i in itens), obrigatorio=False)
        + _texto("descricao", "Descrição")
    )
    corpo = (aviso(mensagem, erro) + '<section class="cartao"><h2>Relatar problema</h2>'
             + _form("/ocorrencias", csrf, "registrar", campos, "Registrar ocorrência") + '</section>')
    corpo += '<section><h2>Ocorrências registradas</h2>'
    if not registros:
        corpo += '<p>Nenhuma ocorrência registrada.</p>'
    for registro in registros:
        estado = 'Resolvida' if registro["resolvida_em"] else 'Aberta'
        alvo = registro["recurso"] or registro["item"]
        corpo += (f'<article class="cartao"><h3>{TIPOS_OCORRENCIA[registro["tipo"]]}</h3>'
                  f'<p>{escape(registro["autor"])} · {estado} · {horario(registro["criado_em"], fuso)}</p>'
                  f'<p>{escape(registro["descricao"])}</p>')
        if alvo:
            corpo += f'<p>Referência: {escape(alvo)}</p>'
        if isinstance(usuario, ChefeLaboratorio) and not registro["resolvida_em"]:
            campos = f'<input type="hidden" name="ocorrencia" value="{registro["id"]}">'
            corpo += _form("/ocorrencias", csrf, "encerrar", campos, "Marcar como resolvida")
        corpo += '</article>'
    return layout("Ocorrências", corpo + '</section>', usuario, csrf)


def notificacoes(usuario, csrf, registros, mensagem, erro, fuso):
    corpo = aviso(mensagem, erro)
    if not registros:
        corpo += '<p>Você ainda não recebeu notificações.</p>'
    for registro in registros:
        estado = 'Resolvida' if registro["resolvida_em"] else 'Lida' if registro["lida_em"] else 'Nova'
        corpo += (f'<article class="cartao"><p><strong>{estado}</strong> · {horario(registro["criado_em"], fuso)}</p>'
                  f'<p>{escape(registro["mensagem"])}</p>')
        if not registro["lida_em"]:
            campos = f'<input type="hidden" name="notificacao" value="{registro["id"]}">'
            corpo += _form("/notificacoes", csrf, "ler", campos, "Marcar como lida")
        corpo += '</article>'
    return layout("Notificações", corpo, usuario, csrf)
