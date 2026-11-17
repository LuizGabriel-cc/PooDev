class OperacoesPostgres:
    def __init__(self, conexao):
        self._conexao = conexao

    def alunos_ativos(self, lab):
        return self._conexao.execute("""
            SELECT u.id, u.nome FROM gestao_lab.aluno a
            JOIN gestao_lab.usuario u ON u.id = a.usuario_id
            WHERE a.laboratorio_id = %s AND u.ativo ORDER BY u.nome, u.id
        """, (lab,)).fetchall()

    def equipamentos(self, lab):
        return self._conexao.execute("""
            SELECT r.id, r.nome, r.estado, e.numero_patrimonio FROM gestao_lab.equipamento e
            JOIN gestao_lab.recurso r ON r.id = e.recurso_id
            WHERE e.laboratorio_id = %s AND r.estado <> 'DESATIVADO' ORDER BY r.nome, r.id
        """, (lab,)).fetchall()

    def recursos(self, lab):
        return self._conexao.execute("""
            SELECT id, nome, tipo FROM gestao_lab.recurso
            WHERE laboratorio_id = %s AND estado <> 'DESATIVADO' ORDER BY nome, id
        """, (lab,)).fetchall()

    def itens_ativos(self, lab):
        return self._conexao.execute("""
            SELECT id, nome, lote FROM gestao_lab.item_estoque
            WHERE laboratorio_id = %s AND ativo ORDER BY nome, lote, id
        """, (lab,)).fetchall()

    def proibicoes(self, lab, aluno):
        return self._conexao.execute("""
            SELECT p.id, u.nome AS aluno, r.nome AS equipamento, e.numero_patrimonio,
                   p.motivo, p.criada_em, p.encerrada_em,
                   EXISTS (SELECT 1 FROM gestao_lab.solicitacao_reativacao s
                           WHERE s.proibicao_id = p.id AND s.estado = 'PENDENTE') AS pedido_pendente
            FROM gestao_lab.proibicao_aluno_equipamento p
            JOIN gestao_lab.usuario u ON u.id = p.aluno_id
            JOIN gestao_lab.equipamento e ON e.recurso_id = p.equipamento_id
            JOIN gestao_lab.recurso r ON r.id = e.recurso_id
            WHERE p.laboratorio_id = %s AND (%s::bigint IS NULL OR p.aluno_id = %s)
            ORDER BY (p.encerrada_em IS NULL) DESC, p.criada_em DESC, p.id DESC
            LIMIT 100
        """, (lab, aluno, aluno)).fetchall()

    def pedidos(self, lab, aluno):
        return self._conexao.execute("""
            SELECT s.id, u.nome AS aluno, r.nome AS equipamento, e.numero_patrimonio,
                   p.motivo, s.estado, s.justificativa, s.resposta, s.solicitada_em
            FROM gestao_lab.solicitacao_reativacao s
            JOIN gestao_lab.proibicao_aluno_equipamento p ON p.id = s.proibicao_id
            JOIN gestao_lab.usuario u ON u.id = s.solicitado_por
            JOIN gestao_lab.equipamento e ON e.recurso_id = p.equipamento_id
            JOIN gestao_lab.recurso r ON r.id = e.recurso_id
            WHERE s.laboratorio_id = %s AND (%s::bigint IS NULL OR s.solicitado_por = %s)
            ORDER BY (s.estado = 'PENDENTE') DESC, s.solicitada_em DESC, s.id DESC
            LIMIT 100
        """, (lab, aluno, aluno)).fetchall()

    def proibir(self, chefe, aluno, equipamento, motivo):
        linha = self._conexao.execute("""
            SELECT gestao_lab.proibir_aluno(%s, a.usuario_id, e.recurso_id, %s) AS id
            FROM gestao_lab.aluno a
            JOIN gestao_lab.usuario u ON u.id = a.usuario_id AND u.ativo
            JOIN gestao_lab.equipamento e ON e.laboratorio_id = a.laboratorio_id
            JOIN gestao_lab.recurso r ON r.id = e.recurso_id AND r.estado <> 'DESATIVADO'
            WHERE a.laboratorio_id = %s AND a.usuario_id = %s AND e.recurso_id = %s
        """, (chefe.id, motivo, chefe.laboratorio_id, aluno, equipamento)).fetchone()
        if linha is None:
            return False
        self._conexao.execute("""
            SELECT gestao_lab.notificar(%s, %s, 'PROIBICAO_APLICADA', %s,
                                        jsonb_build_object('proibicao_id', %s::bigint))
        """, (chefe.laboratorio_id, aluno, "Uma restrição de equipamento foi aplicada. Consulte Restrições.", linha["id"]))
        return True

    def solicitar(self, aluno, proibicao, justificativa):
        return self._conexao.execute("""
            SELECT gestao_lab.solicitar_reativacao(%s, id, %s)
            FROM gestao_lab.proibicao_aluno_equipamento
            WHERE id = %s AND aluno_id = %s AND laboratorio_id = %s AND encerrada_em IS NULL
        """, (aluno.id, justificativa, proibicao, aluno.id, aluno.laboratorio_id)).fetchone() is not None

    def responder(self, chefe, pedido, aprovar, resposta):
        return self._conexao.execute("""
            SELECT gestao_lab.responder_reativacao(%s, id, %s, %s)
            FROM gestao_lab.solicitacao_reativacao
            WHERE id = %s AND laboratorio_id = %s AND estado = 'PENDENTE'
        """, (chefe.id, aprovar, resposta, pedido, chefe.laboratorio_id)).fetchone() is not None

    def mudar_estado(self, chefe, equipamento, estado, motivo):
        return self._conexao.execute("""
            SELECT gestao_lab.definir_estado_recurso(%s, r.id, %s::gestao_lab.estado_recurso, %s)
            FROM gestao_lab.equipamento e JOIN gestao_lab.recurso r ON r.id = e.recurso_id
            WHERE e.recurso_id = %s AND e.laboratorio_id = %s AND r.estado <> 'DESATIVADO'
        """, (chefe.id, estado, motivo, equipamento, chefe.laboratorio_id)).fetchone() is not None

    def ocorrencias(self, lab, autor):
        return self._conexao.execute("""
            SELECT o.id, o.tipo, o.descricao, o.criado_em, o.resolvida_em, u.nome AS autor,
                   r.nome AS recurso, i.nome AS item, i.lote
            FROM gestao_lab.ocorrencia o JOIN gestao_lab.usuario u ON u.id = o.autor_id
            LEFT JOIN gestao_lab.recurso r ON r.id = o.recurso_id
            LEFT JOIN gestao_lab.item_estoque i ON i.id = o.item_estoque_id
            WHERE o.laboratorio_id = %s AND (%s::bigint IS NULL OR o.autor_id = %s)
            ORDER BY (o.resolvida_em IS NULL) DESC, o.criado_em DESC, o.id DESC LIMIT 100
        """, (lab, autor, autor)).fetchall()

    def registrar_ocorrencia(self, ator, tipo, descricao, recurso, item):
        self._conexao.execute("""
            INSERT INTO gestao_lab.ocorrencia(laboratorio_id, autor_id, tipo, descricao, recurso_id, item_estoque_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (ator.laboratorio_id, ator.id, tipo, descricao, recurso, item))

    def encerrar_ocorrencia(self, lab, ocorrencia):
        return self._conexao.execute("""
            UPDATE gestao_lab.ocorrencia SET resolvida_em = clock_timestamp()
            WHERE laboratorio_id = %s AND id = %s AND resolvida_em IS NULL
        """, (lab, ocorrencia)).rowcount == 1

    def avisos(self, ator):
        return self._conexao.execute("""
            SELECT id, tipo, mensagem, criado_em, lida_em, resolvida_em FROM gestao_lab.notificacao
            WHERE laboratorio_id = %s AND destinatario_id = %s
            ORDER BY (lida_em IS NULL AND resolvida_em IS NULL) DESC, criado_em DESC, id DESC LIMIT 100
        """, (ator.laboratorio_id, ator.id)).fetchall()

    def marcar_lida(self, ator, notificacao):
        return self._conexao.execute("""
            UPDATE gestao_lab.notificacao SET lida_em = COALESCE(lida_em, clock_timestamp())
            WHERE id = %s AND laboratorio_id = %s AND destinatario_id = %s
        """, (notificacao, ator.laboratorio_id, ator.id)).rowcount == 1

    def proximo_email(self):
        return self._conexao.execute("""
            SELECT e.id, e.tentativas, u.email FROM gestao_lab.envio_email e
            JOIN gestao_lab.notificacao n ON n.id = e.notificacao_id
            JOIN gestao_lab.usuario u ON u.id = n.destinatario_id AND u.ativo
            JOIN gestao_lab.laboratorio l ON l.id = n.laboratorio_id AND l.ativo
            WHERE e.estado = 'PENDENTE' AND e.proxima_tentativa_em <= clock_timestamp()
            ORDER BY e.proxima_tentativa_em, e.id LIMIT 1 FOR UPDATE OF e SKIP LOCKED
        """).fetchone()

    def confirmar_envio(self, identificador):
        self._conexao.execute("""
            UPDATE gestao_lab.envio_email SET estado = 'ENVIADO', enviado_em = clock_timestamp(),
                tentativas = tentativas + 1, ultimo_erro = NULL WHERE id = %s
        """, (identificador,))

    def registrar_falha_envio(self, identificador, erro, atraso, terminal):
        self._conexao.execute("""
            UPDATE gestao_lab.envio_email SET estado = %s::gestao_lab.estado_envio,
                tentativas = tentativas + 1, ultimo_erro = %s,
                proxima_tentativa_em = clock_timestamp() + make_interval(secs => %s)
            WHERE id = %s
        """, ("FALHOU" if terminal else "PENDENTE", erro, atraso, identificador))
