-- Consulta SOMENTE LEITURA para verificação manual do agente no pgAdmin.
-- Requer schema gestao_lab até migração 006. Não altera dados.
SELECT versao, descricao FROM gestao_lab.schema_versao
WHERE versao IN (3, 6) ORDER BY versao;

SELECT to_regclass('gestao_lab.recomendacao_estoque') AS tabela_recomendacoes,
       to_regclass('gestao_lab.movimentacao_estoque') AS tabela_movimentacoes,
       to_regprocedure('gestao_lab.notificar(bigint,bigint,text,text,jsonb,text)') AS funcao_notificar;

SELECT laboratorio_id, situacao, count(*) AS total
FROM gestao_lab.recomendacao_estoque
GROUP BY laboratorio_id, situacao
ORDER BY laboratorio_id, situacao;

SELECT laboratorio_id, destinatario_id, tipo, count(*) AS total
FROM gestao_lab.notificacao
WHERE tipo = 'AGENTE_ESTOQUE'
GROUP BY laboratorio_id, destinatario_id, tipo
ORDER BY laboratorio_id, destinatario_id;

-- Nunca deve retornar linhas (violação do índice único de pendências).
SELECT laboratorio_id, item_id, count(*) AS pendencias
FROM gestao_lab.recomendacao_estoque
WHERE situacao = 'PENDENTE'
GROUP BY laboratorio_id, item_id
HAVING count(*) > 1;
