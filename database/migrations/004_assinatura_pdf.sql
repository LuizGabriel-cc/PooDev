-- Executar no banco do PooDev após a migração 003.
BEGIN;
SET LOCAL search_path = gestao_lab, public;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_versao WHERE versao = 3) THEN
        RAISE EXCEPTION 'Aplique a migração 003 antes da 004.';
    END IF;
    IF EXISTS (SELECT 1 FROM schema_versao WHERE versao = 4) THEN
        RAISE EXCEPTION 'A migração 004 já foi registrada.';
    END IF;
END $$;

ALTER TABLE protocolo
    ADD COLUMN pdf_politica_verificacao text,
    ADD COLUMN pdf_sha256 bytea,
    ADD CONSTRAINT protocolo_evidencia_pdf_coerente CHECK (
        (pdf_politica_verificacao IS NULL AND pdf_sha256 IS NULL)
        OR (
            assinado_em IS NOT NULL
            AND pdf_politica_verificacao IS NOT NULL AND btrim(pdf_politica_verificacao) <> ''
            AND pdf_sha256 IS NOT NULL AND pdf_sha256 = sha256(pdf_original)
        )
    );

CREATE FUNCTION tg_preservar_verificacao_pdf() RETURNS trigger
LANGUAGE plpgsql SET search_path = gestao_lab, public AS $$
BEGIN
    IF OLD.assinado_em IS NOT NULL
        AND (OLD.pdf_politica_verificacao, OLD.pdf_sha256)
            IS DISTINCT FROM (NEW.pdf_politica_verificacao, NEW.pdf_sha256) THEN
        RAISE EXCEPTION 'A evidência da assinatura registrada é imutável' USING ERRCODE = '23514';
    END IF;
    IF NEW.estado = 'VALIDADO' AND OLD.estado IS DISTINCT FROM NEW.estado
        AND NEW.pdf_politica_verificacao IS NULL THEN
        RAISE EXCEPTION 'O protocolo precisa de assinatura digital verificada' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER preservar_verificacao_pdf BEFORE UPDATE OF estado, pdf_politica_verificacao, pdf_sha256
    ON protocolo FOR EACH ROW EXECUTE FUNCTION tg_preservar_verificacao_pdf();

-- A aplicação chama esta função somente após conferir os mesmos bytes do PDF.
-- assinar_protocolo permanece para clientes legados e não produz evidência digital.
CREATE FUNCTION registrar_assinatura_pdf_verificada(
    p_autor bigint, p_protocolo bigint, p_politica text
) RETURNS void
LANGUAGE plpgsql SET search_path = gestao_lab, public AS $$
BEGIN
    IF p_politica IS NULL OR btrim(p_politica) = '' THEN
        RAISE EXCEPTION 'Informe a política de verificação do PDF' USING ERRCODE = '23514';
    END IF;

    PERFORM contexto_operacao(p_autor, 'Verificação técnica de assinatura no PDF');
    UPDATE protocolo
       SET assinado_em = clock_timestamp(),
           assinado_por = p_autor,
           pdf_politica_verificacao = p_politica,
           pdf_sha256 = sha256(pdf_original)
     WHERE id = p_protocolo AND autor_id = p_autor AND assinado_em IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'O autor pode registrar a verificação de um protocolo ainda não assinado'
            USING ERRCODE = '42501';
    END IF;
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
    IF v_politica IS NULL THEN
        RAISE EXCEPTION 'O protocolo precisa de assinatura digital verificada' USING ERRCODE = '23514';
    END IF;
    PERFORM contexto_operacao(p_chefe, 'Validação administrativa do protocolo pelo Chefe');
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
          AND pdf_politica_verificacao IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'O vínculo exige protocolo validado com assinatura digital verificada'
            USING ERRCODE = '23514';
    END IF;
    PERFORM exigir_chefe(NEW.vinculado_por, NEW.laboratorio_id);
    RETURN NEW;
END $$;

INSERT INTO schema_versao(versao, descricao)
VALUES (4, 'Evidência de verificação de assinatura digital em protocolos');

COMMIT;
