-- Assinatura de protocolos no sistema, com chave RSA própria de cada autor.
BEGIN;
SET LOCAL search_path = gestao_lab, public;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_versao WHERE versao = 4) THEN
        RAISE EXCEPTION 'Aplique a migração 004 antes da 005.';
    END IF;
    IF EXISTS (SELECT 1 FROM schema_versao WHERE versao = 5) THEN
        RAISE EXCEPTION 'A migração 005 já foi registrada.';
    END IF;
END $$;

CREATE TABLE chave_assinatura_usuario (
    usuario_id bigint PRIMARY KEY,
    laboratorio_id bigint NOT NULL,
    modulo text NOT NULL CHECK (modulo ~ '^[1-9][0-9]*$' AND length(modulo) BETWEEN 617 AND 1234),
    expoente_publico text NOT NULL CHECK (expoente_publico = '65537'),
    expoente_privado text NOT NULL CHECK (expoente_privado ~ '^[1-9][0-9]*$'
        AND length(expoente_privado) <= 1234),
    criado_em timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (usuario_id, laboratorio_id) REFERENCES usuario(id, laboratorio_id)
);
REVOKE ALL ON chave_assinatura_usuario FROM PUBLIC;
-- O expoente privado fica somente na tabela de chaves. Ela não usa o gatilho
-- genérico de auditoria, pois ele copia os valores completos de uma linha.
CREATE TRIGGER chave_assinatura_imutavel BEFORE UPDATE OR DELETE ON chave_assinatura_usuario
    FOR EACH ROW EXECUTE FUNCTION tg_historico_imutavel();
CREATE TRIGGER chave_assinatura_sem_truncate BEFORE TRUNCATE ON chave_assinatura_usuario
    FOR EACH STATEMENT EXECUTE FUNCTION tg_historico_imutavel();

ALTER TABLE protocolo
    ADD COLUMN assinatura_rsa bytea,
    ADD COLUMN rsa_resumo bytea,
    ADD COLUMN rsa_modulo text,
    ADD COLUMN rsa_expoente_publico text,
    ADD CONSTRAINT protocolo_evidencia_rsa_coerente CHECK (
        (assinatura_rsa IS NULL AND rsa_resumo IS NULL
            AND rsa_modulo IS NULL AND rsa_expoente_publico IS NULL
            AND pdf_politica_verificacao IS DISTINCT FROM 'rsa-sha256-v1')
        OR (
            assinatura_rsa IS NOT NULL AND octet_length(assinatura_rsa) BETWEEN 256 AND 512
            AND rsa_resumo IS NOT NULL AND octet_length(rsa_resumo) = 32
            AND rsa_resumo = pdf_sha256
            AND rsa_modulo IS NOT NULL AND rsa_modulo ~ '^[1-9][0-9]*$'
            AND length(rsa_modulo) BETWEEN 617 AND 1234
            AND rsa_expoente_publico IS NOT NULL AND rsa_expoente_publico = '65537'
            AND pdf_politica_verificacao IS NOT NULL AND pdf_politica_verificacao = 'rsa-sha256-v1'
            AND assinado_em IS NOT NULL
        )
    );

CREATE OR REPLACE FUNCTION tg_preservar_verificacao_pdf() RETURNS trigger
LANGUAGE plpgsql SET search_path = gestao_lab, public AS $$
BEGIN
    IF OLD.assinado_em IS NOT NULL
        AND (OLD.pdf_politica_verificacao, OLD.pdf_sha256, OLD.assinatura_rsa,
             OLD.rsa_resumo, OLD.rsa_modulo, OLD.rsa_expoente_publico)
        IS DISTINCT FROM
            (NEW.pdf_politica_verificacao, NEW.pdf_sha256, NEW.assinatura_rsa,
             NEW.rsa_resumo, NEW.rsa_modulo, NEW.rsa_expoente_publico) THEN
        RAISE EXCEPTION 'A evidência da assinatura registrada é imutável' USING ERRCODE = '23514';
    END IF;
    IF NEW.estado = 'VALIDADO' AND OLD.estado IS DISTINCT FROM NEW.estado
        AND NEW.pdf_politica_verificacao IS DISTINCT FROM 'rsa-sha256-v1' THEN
        RAISE EXCEPTION 'O protocolo precisa de assinatura RSA do sistema' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER preservar_verificacao_pdf ON protocolo;
CREATE TRIGGER preservar_verificacao_pdf BEFORE UPDATE OF
    estado, pdf_politica_verificacao, pdf_sha256, assinatura_rsa,
    rsa_resumo, rsa_modulo, rsa_expoente_publico
    ON protocolo FOR EACH ROW EXECUTE FUNCTION tg_preservar_verificacao_pdf();

CREATE FUNCTION registrar_assinatura_rsa(
    p_autor bigint, p_protocolo bigint, p_assinatura bytea, p_resumo bytea
) RETURNS void
LANGUAGE plpgsql SET search_path = gestao_lab, public AS $$
DECLARE
    v_lab bigint;
    v_chave chave_assinatura_usuario%ROWTYPE;
BEGIN
    PERFORM exigir_isolamento();
    SELECT laboratorio_id INTO v_lab FROM protocolo WHERE id = p_protocolo;
    IF v_lab IS NULL THEN
        RAISE EXCEPTION 'Protocolo não encontrado' USING ERRCODE = '23514';
    END IF;
    -- A validação e os demais fluxos também bloqueiam o laboratório antes do protocolo.
    PERFORM 1 FROM laboratorio WHERE id = v_lab FOR UPDATE;
    PERFORM exigir_usuario(p_autor, v_lab);
    SELECT * INTO v_chave FROM chave_assinatura_usuario
    WHERE usuario_id = p_autor AND laboratorio_id = v_lab;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'O autor precisa de uma chave RSA' USING ERRCODE = '23514';
    END IF;
    PERFORM contexto_operacao(p_autor, 'Assinatura RSA do protocolo pelo autor');
    UPDATE protocolo
    SET assinado_em = clock_timestamp(),
        assinado_por = p_autor,
        pdf_politica_verificacao = 'rsa-sha256-v1',
        pdf_sha256 = p_resumo,
        assinatura_rsa = p_assinatura,
        rsa_resumo = p_resumo,
        rsa_modulo = v_chave.modulo,
        rsa_expoente_publico = v_chave.expoente_publico
    WHERE id = p_protocolo AND autor_id = p_autor AND laboratorio_id = v_lab
      AND assinado_em IS NULL AND estado = 'NAO_VALIDADO';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Somente o autor pode assinar protocolo ainda não assinado'
            USING ERRCODE = '42501';
    END IF;
END $$;

CREATE OR REPLACE FUNCTION assinar_protocolo(p_autor bigint,p_protocolo bigint) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Use a assinatura RSA do sistema' USING ERRCODE = '23514';
END $$;

CREATE OR REPLACE FUNCTION registrar_assinatura_pdf_verificada(
    p_autor bigint, p_protocolo bigint, p_politica text
) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Use a assinatura RSA do sistema' USING ERRCODE = '23514';
END $$;

CREATE OR REPLACE FUNCTION validar_protocolo(p_chefe bigint, p_protocolo bigint) RETURNS void
LANGUAGE plpgsql SET search_path = gestao_lab, public AS $$
DECLARE
    v_lab bigint;
    v_politica text;
BEGIN
    SELECT laboratorio_id, pdf_politica_verificacao INTO STRICT v_lab, v_politica
    FROM protocolo WHERE id = p_protocolo;
    PERFORM exigir_chefe(p_chefe, v_lab);
    IF v_politica IS DISTINCT FROM 'rsa-sha256-v1' THEN
        RAISE EXCEPTION 'O protocolo precisa de assinatura RSA do sistema' USING ERRCODE = '23514';
    END IF;
    PERFORM contexto_operacao(p_chefe, 'Validação do protocolo com assinatura RSA pelo Chefe');
    UPDATE protocolo SET estado = 'VALIDADO', validado_em = clock_timestamp(), validado_por = p_chefe
    WHERE id = p_protocolo AND estado = 'NAO_VALIDADO';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Protocolo já validado' USING ERRCODE = '23514';
    END IF;
END $$;

CREATE OR REPLACE FUNCTION tg_vincular_protocolo() RETURNS trigger
LANGUAGE plpgsql SET search_path = gestao_lab, public AS $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM protocolo WHERE id = NEW.protocolo_id AND estado = 'VALIDADO'
          AND pdf_politica_verificacao = 'rsa-sha256-v1'
    ) THEN
        RAISE EXCEPTION 'O vínculo exige protocolo validado com assinatura RSA do sistema'
            USING ERRCODE = '23514';
    END IF;
    PERFORM exigir_chefe(NEW.vinculado_por, NEW.laboratorio_id);
    RETURN NEW;
END $$;

INSERT INTO schema_versao(versao, descricao)
VALUES (5, 'Assinatura RSA nativa de protocolos no sistema');
COMMIT;
