-- Conferência de leitura para um banco que já tenha o schema inicial instalado.
-- A versão atual requer PostgreSQL >=16, registros 1 a 4 e todos os recursos verificados abaixo.
BEGIN TRANSACTION READ ONLY;

SELECT current_database() AS banco,
       current_setting('server_version') AS versao_postgresql,
       current_setting('server_version_num')::integer >= 160000 AS versao_suportada,
       current_setting('default_transaction_isolation') AS isolamento_padrao;

SELECT count(*) AS tabelas
FROM information_schema.tables
WHERE table_schema = 'gestao_lab' AND table_type = 'BASE TABLE';

SELECT coalesce(max(versao), 0) AS ultima_versao,
       count(*) FILTER (WHERE versao IN (1, 2, 3, 4)) = 4 AS versoes_obrigatorias_aplicadas
FROM gestao_lab.schema_versao;

SELECT versao, descricao, aplicada_em
FROM gestao_lab.schema_versao ORDER BY versao DESC;

SELECT extname, extversion FROM pg_extension WHERE extname = 'btree_gist';

SELECT to_regprocedure('gestao_lab.criar_reserva(bigint,bigint,timestamptz,timestamptz)') IS NOT NULL AS criar_reserva,
       to_regprocedure('gestao_lab.cancelar_reserva(bigint,bigint,text)') IS NOT NULL AS cancelar_reserva,
       to_regprocedure('gestao_lab.retirar_chave(bigint,bigint,bigint,bigint)') IS NOT NULL AS retirar_chave,
       to_regprocedure('gestao_lab.devolver_chave(bigint,bigint)') IS NOT NULL AS devolver_chave;

SELECT to_regclass('gestao_lab.vw_pendencias_estoque') IS NOT NULL AS pendencias_estoque,
       to_regprocedure('gestao_lab.avaliar_alertas_estoque(bigint)') IS NOT NULL AS avaliar_alertas_estoque,
       to_regprocedure('gestao_lab.avaliar_alertas_item_estoque(bigint)') IS NOT NULL AS avaliar_alertas_item_estoque,
       to_regprocedure('gestao_lab.movimentar_estoque(bigint,bigint,numeric,text)') IS NOT NULL AS movimentar_estoque_legado,
       to_regprocedure('gestao_lab.movimentar_estoque(bigint,bigint,numeric,text,text)') IS NOT NULL AS movimentar_estoque_com_finalidade,
       to_regprocedure('gestao_lab.registrar_assinatura_pdf_verificada(bigint,bigint,text)') IS NOT NULL AS registrar_assinatura_pdf;

SELECT count(*) FILTER (WHERE table_name = 'notificacao' AND column_name = 'resolvida_em') = 1 AS encerramento_de_alertas,
       count(*) FILTER (WHERE table_name = 'movimentacao_estoque' AND column_name = 'finalidade') = 1 AS finalidade_da_movimentacao,
       count(*) FILTER (WHERE table_name = 'protocolo' AND column_name IN ('pdf_sha256', 'pdf_politica_verificacao')) = 2 AS evidencia_pdf
FROM information_schema.columns
WHERE table_schema = 'gestao_lab';

SELECT EXISTS (
    SELECT 1 FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'gestao_lab' AND t.relname = 'reserva_recurso'
      AND c.conname = 'reserva_recurso_sem_sobreposicao' AND c.contype = 'x'
) AS exclusao_de_sobreposicao_instalada;

COMMIT;
