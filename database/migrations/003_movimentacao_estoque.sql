BEGIN;
SET LOCAL search_path = gestao_lab, public;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_versao WHERE versao = 2) THEN
        RAISE EXCEPTION 'A migração 002 deve ser aplicada antes da 003.';
    END IF;
    IF EXISTS (SELECT 1 FROM schema_versao WHERE versao = 3) THEN
        RAISE EXCEPTION 'Migração 003 já aplicada.';
    END IF;
END $$;

-- Preserva o motivo original. Nos registros anteriores não há finalidade estruturada.
ALTER TABLE movimentacao_estoque ADD COLUMN finalidade text
    CHECK (finalidade IS NULL OR (variacao < 0 AND finalidade IN ('USO', 'DESCARTE')));

CREATE FUNCTION data_local_estoque(p_instante timestamptz DEFAULT clock_timestamp()) RETURNS date
LANGUAGE sql STABLE AS $$
    SELECT (p_instante AT TIME ZONE 'America/Sao_Paulo')::date;
$$;

CREATE OR REPLACE FUNCTION tg_movimentar_estoque() RETURNS trigger
LANGUAGE plpgsql SET search_path = gestao_lab, public AS $$
DECLARE
    v_ator bigint;
    v_motivo text;
    v_anterior numeric;
    v_variacao numeric;
    v_finalidade text;
BEGIN
    v_anterior := CASE WHEN TG_OP = 'INSERT' THEN 0 ELSE OLD.quantidade END;
    v_variacao := NEW.quantidade - v_anterior;
    IF v_variacao = 0 THEN
        RETURN NEW;
    END IF;

    v_ator := nullif(current_setting('app.usuario_id', true), '')::bigint;
    v_motivo := nullif(btrim(current_setting('app.motivo', true)), '');
    PERFORM exigir_chefe(v_ator, NEW.laboratorio_id);
    IF v_motivo IS NULL OR char_length(v_motivo) > 500 THEN
        RAISE EXCEPTION 'Motivo: informe entre 1 e 500 caracteres.' USING ERRCODE = '23514';
    END IF;
    IF NOT NEW.ativo THEN
        RAISE EXCEPTION 'Item inexistente ou inativo.' USING ERRCODE = '23514';
    END IF;

    IF v_variacao < 0 THEN
        v_finalidade := coalesce(nullif(current_setting('app.finalidade_estoque', true), ''), 'USO');
        IF v_finalidade NOT IN ('USO', 'DESCARTE') THEN
            RAISE EXCEPTION 'Finalidade da movimentação inválida.' USING ERRCODE = '23514';
        END IF;
        IF v_finalidade = 'USO' AND NEW.validade < data_local_estoque() THEN
            RAISE EXCEPTION 'Produto vencido: somente descarte é permitido.' USING ERRCODE = '23514';
        END IF;
    END IF;

    INSERT INTO movimentacao_estoque(
        laboratorio_id, item_id, registrado_por, variacao,
        quantidade_anterior, quantidade_posterior, motivo, finalidade
    ) VALUES (
        NEW.laboratorio_id, NEW.id, v_ator, v_variacao,
        v_anterior, NEW.quantidade, v_motivo, v_finalidade
    );
    RETURN NEW;
END $$;

CREATE FUNCTION movimentar_estoque(
    p_chefe bigint, p_item bigint, p_variacao numeric, p_motivo text, p_finalidade text
) RETURNS numeric
LANGUAGE plpgsql SET search_path = gestao_lab, public AS $$
DECLARE
    v_item item_estoque%ROWTYPE;
    v_saldo numeric;
    v_finalidade_anterior text := coalesce(current_setting('app.finalidade_estoque', true), '');
BEGIN
    IF p_finalidade IS NULL OR p_finalidade NOT IN ('USO', 'DESCARTE') THEN
        RAISE EXCEPTION 'Finalidade da movimentação inválida.' USING ERRCODE = '23514';
    END IF;
    IF p_variacao IS NULL OR p_variacao = 0 OR abs(p_variacao) >= 10000000000
       OR p_variacao <> round(p_variacao, 4) THEN
        RAISE EXCEPTION 'Variação de estoque inválida.' USING ERRCODE = '23514';
    END IF;
    IF p_variacao > 0 AND p_finalidade = 'DESCARTE' THEN
        RAISE EXCEPTION 'Descarte exige uma saída do estoque.' USING ERRCODE = '23514';
    END IF;

    SELECT * INTO v_item FROM item_estoque WHERE id = p_item FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Item inexistente ou inativo.' USING ERRCODE = '23514';
    END IF;
    PERFORM exigir_chefe(p_chefe, v_item.laboratorio_id);
    IF NOT v_item.ativo THEN
        RAISE EXCEPTION 'Item inexistente ou inativo.' USING ERRCODE = '23514';
    END IF;
    v_saldo := v_item.quantidade + p_variacao;
    IF v_saldo < 0 THEN
        RAISE EXCEPTION 'Estoque insuficiente para esta saída.' USING ERRCODE = '23514';
    END IF;
    IF v_saldo >= 10000000000 THEN
        RAISE EXCEPTION 'Saldo excede o limite permitido.' USING ERRCODE = '23514';
    END IF;

    PERFORM contexto_operacao(p_chefe, p_motivo);
    PERFORM set_config('app.finalidade_estoque', p_finalidade, true);
    UPDATE item_estoque SET quantidade = v_saldo WHERE id = p_item;
    PERFORM set_config('app.finalidade_estoque', v_finalidade_anterior, true);
    RETURN v_saldo;
END $$;

CREATE OR REPLACE FUNCTION movimentar_estoque(
    p_chefe bigint, p_item bigint, p_variacao numeric, p_motivo text
) RETURNS numeric
LANGUAGE sql SET search_path = gestao_lab, public AS $$
    SELECT movimentar_estoque(p_chefe, p_item, p_variacao, p_motivo, 'USO');
$$;

CREATE OR REPLACE VIEW vw_pendencias_estoque AS
WITH referencia AS MATERIALIZED (SELECT data_local_estoque() AS hoje)
SELECT i.id AS item_id, i.laboratorio_id, i.nome, i.lote, i.unidade, i.quantidade,
       i.limite_estoque_baixo, i.validade,
       (i.quantidade <= i.limite_estoque_baixo) AS estoque_baixo,
       (i.quantidade > 0 AND i.validade IS NOT NULL AND i.validade < r.hoje) AS vencido,
       (i.quantidade > 0 AND i.validade IS NOT NULL
        AND i.validade BETWEEN r.hoje AND r.hoje + l.dias_alerta_validade) AS validade_proxima
FROM item_estoque i
JOIN laboratorio l ON l.id = i.laboratorio_id
CROSS JOIN referencia r
WHERE i.ativo AND l.ativo AND (
    i.quantidade <= i.limite_estoque_baixo
    OR (i.quantidade > 0 AND i.validade <= r.hoje + l.dias_alerta_validade)
);

CREATE FUNCTION avaliar_alertas_item_estoque(p_item bigint) RETURNS integer
LANGUAGE plpgsql SET search_path = gestao_lab, public AS $$
DECLARE
    v record;
    v_id bigint;
    v_total integer := 0;
    v_chave_baixo text := 'estoque_baixo:' || p_item;
    v_chave_validade text := 'validade:' || p_item;
BEGIN
    -- Adquire o mesmo bloqueio da movimentação antes de consultar a pendência.
    PERFORM 1 FROM item_estoque WHERE id = p_item FOR UPDATE;
    IF NOT FOUND THEN
        RETURN 0;
    END IF;
    SELECT i.laboratorio_id, l.chefe_usuario_id, i.nome, i.quantidade, i.validade,
           coalesce(p.estoque_baixo, false) AS estoque_baixo,
           coalesce(p.vencido OR p.validade_proxima, false) AS alerta_validade
    INTO v
    FROM item_estoque i
    JOIN laboratorio l ON l.id = i.laboratorio_id
    LEFT JOIN vw_pendencias_estoque p ON p.item_id = i.id
    WHERE i.id = p_item;

    UPDATE notificacao SET chave_deduplicacao = NULL, resolvida_em = clock_timestamp()
    WHERE laboratorio_id = v.laboratorio_id AND destinatario_id = v.chefe_usuario_id
      AND resolvida_em IS NULL AND (
          (chave_deduplicacao = v_chave_baixo AND NOT v.estoque_baixo)
          OR (chave_deduplicacao = v_chave_validade AND NOT v.alerta_validade)
      );

    IF v.estoque_baixo THEN
        v_id := notificar(
            v.laboratorio_id, v.chefe_usuario_id, 'ESTOQUE_BAIXO', 'Estoque baixo: ' || v.nome,
            jsonb_build_object('item_id', p_item, 'quantidade', v.quantidade), v_chave_baixo
        );
        IF v_id IS NOT NULL THEN
            v_total := v_total + 1;
        END IF;
    END IF;
    IF v.alerta_validade THEN
        v_id := notificar(
            v.laboratorio_id, v.chefe_usuario_id, 'VALIDADE', 'Validade próxima ou vencida: ' || v.nome,
            jsonb_build_object('item_id', p_item, 'validade', v.validade), v_chave_validade
        );
        IF v_id IS NOT NULL THEN
            v_total := v_total + 1;
        END IF;
    END IF;
    RETURN v_total;
END $$;

CREATE OR REPLACE FUNCTION avaliar_alertas_estoque(p_laboratorio bigint DEFAULT NULL) RETURNS integer
LANGUAGE plpgsql SET search_path = gestao_lab, public AS $$
DECLARE
    v_item bigint;
    v_total integer := 0;
BEGIN
    FOR v_item IN
        SELECT id FROM item_estoque
        WHERE p_laboratorio IS NULL OR laboratorio_id = p_laboratorio
        ORDER BY id
    LOOP
        v_total := v_total + avaliar_alertas_item_estoque(v_item);
    END LOOP;
    RETURN v_total;
END $$;

INSERT INTO schema_versao(versao, descricao)
VALUES (3, 'Finalidade e validação atômica de movimentações de estoque');
COMMIT;
