-- PooDev: pendências atuais e ciclo de notificações do estoque.
-- Aplicar uma única vez em banco existente na versão 1, preservando os dados.
BEGIN;
SET LOCAL search_path = gestao_lab, public;
SET LOCAL TIME ZONE 'America/Sao_Paulo';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM gestao_lab.schema_versao WHERE versao = 1) THEN
        RAISE EXCEPTION 'Versão inicial do banco não encontrada; confira schema_versao.';
    END IF;
    IF EXISTS (SELECT 1 FROM gestao_lab.schema_versao WHERE versao = 2) THEN
        RAISE EXCEPTION 'Migração 002 já aplicada.';
    END IF;
END $$;

ALTER TABLE gestao_lab.notificacao
    ADD COLUMN IF NOT EXISTS resolvida_em timestamptz;

-- Notificações já encerradas na implementação anterior não são apagadas.
UPDATE gestao_lab.notificacao
SET resolvida_em = clock_timestamp()
WHERE tipo IN ('ESTOQUE_BAIXO', 'VALIDADE')
  AND chave_deduplicacao IS NULL
  AND resolvida_em IS NULL;

-- View dinâmica: um item pode ter mais de uma pendência simultaneamente.
CREATE VIEW gestao_lab.vw_pendencias_estoque AS
SELECT
    i.id AS item_id,
    i.laboratorio_id,
    i.nome,
    i.lote,
    i.unidade,
    i.quantidade,
    i.limite_estoque_baixo,
    i.validade,
    (i.quantidade <= i.limite_estoque_baixo) AS estoque_baixo,
    (i.quantidade > 0 AND i.validade < ((CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo')::date)) AS vencido,
    (i.quantidade > 0 AND i.validade >= ((CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo')::date)
     AND i.validade <= ((CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo')::date) + l.dias_alerta_validade) AS validade_proxima
FROM gestao_lab.item_estoque AS i
JOIN gestao_lab.laboratorio AS l ON l.id = i.laboratorio_id
WHERE i.ativo AND l.ativo
  AND (
      i.quantidade <= i.limite_estoque_baixo
      OR (i.quantidade > 0
          AND i.validade <= ((CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo')::date) + l.dias_alerta_validade)
  );

-- A chave de deduplicação só é liberada quando o problema termina.
-- Assim, a mesma ocorrência gera um único aviso, mesmo com monitoramento repetido.
CREATE OR REPLACE FUNCTION gestao_lab.avaliar_alertas_estoque(
    p_laboratorio bigint DEFAULT NULL
) RETURNS integer
LANGUAGE plpgsql SET search_path = gestao_lab, public AS $$
DECLARE
    v record;
    v_chave text;
    v_id bigint;
    v_total integer := 0;
    v_ativo boolean;
BEGIN
    FOR v IN
        SELECT i.*, l.chefe_usuario_id,
               l.dias_alerta_validade,
               l.ativo AS laboratorio_ativo
        FROM item_estoque i
        JOIN laboratorio l ON l.id = i.laboratorio_id
        WHERE p_laboratorio IS NULL OR i.laboratorio_id = p_laboratorio
    LOOP
        v_ativo := v.ativo AND v.laboratorio_ativo;

        v_chave := 'estoque_baixo:' || v.id;
        IF v_ativo AND v.quantidade <= v.limite_estoque_baixo THEN
            v_id := notificar(
                v.laboratorio_id, v.chefe_usuario_id,
                'ESTOQUE_BAIXO', 'Estoque baixo: ' || v.nome,
                jsonb_build_object('item_id', v.id, 'quantidade', v.quantidade),
                v_chave
            );
            IF v_id IS NOT NULL THEN v_total := v_total + 1; END IF;
        ELSE
            UPDATE notificacao
            SET chave_deduplicacao = NULL,
                resolvida_em = clock_timestamp()
            WHERE destinatario_id = v.chefe_usuario_id
              AND chave_deduplicacao = v_chave
              AND resolvida_em IS NULL;
        END IF;

        v_chave := 'validade:' || v.id;
        IF v_ativo AND v.quantidade > 0 AND v.validade IS NOT NULL
           AND v.validade <= ((CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo')::date) + v.dias_alerta_validade THEN
            v_id := notificar(
                v.laboratorio_id, v.chefe_usuario_id,
                'VALIDADE', 'Validade próxima ou vencida: ' || v.nome,
                jsonb_build_object('item_id', v.id, 'validade', v.validade),
                v_chave
            );
            IF v_id IS NOT NULL THEN v_total := v_total + 1; END IF;
        ELSE
            UPDATE notificacao
            SET chave_deduplicacao = NULL,
                resolvida_em = clock_timestamp()
            WHERE destinatario_id = v.chefe_usuario_id
              AND chave_deduplicacao = v_chave
              AND resolvida_em IS NULL;
        END IF;
    END LOOP;
    RETURN v_total;
END $$;

INSERT INTO gestao_lab.schema_versao(versao, descricao)
VALUES (2, 'Pendências de estoque e encerramento de notificações');
COMMIT;
