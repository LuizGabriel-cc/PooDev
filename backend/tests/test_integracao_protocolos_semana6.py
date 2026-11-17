"""Fluxo com PostgreSQL real: necessita TEST_DATABASE_URL, como os demais testes."""
import pytest

from hashlib import sha256

from gestao_lab.aplicacao.protocolos import ServicoProtocolos
from gestao_lab.dominio.assinaturas_pdf import EstadoAssinatura, ResultadoAssinatura
from gestao_lab.dominio.erros import AcessoNegado, DadosInvalidos

pytestmark = pytest.mark.integracao


def test_protocolos_autoria_validacao_e_vinculo_persistidos(sistema, recursos, portador):
    autor, token_autor = portador
    class VerificadorSimulado:
        def verificar(self, conteudo):
            # A integração com BD é testada separadamente da criptografia.
            return ResultadoAssinatura(
                EstadoAssinatura.VALIDA, (autor.nome,), "Simulado", politica="politica-de-teste"
            )

    servico = ServicoProtocolos(sistema.transacao, sistema.auth, VerificadorSimulado())
    conteudo = b"%PDF-1.4\n%Documento para teste\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"
    protocolo_id = servico.cadastrar(
        token_autor, titulo="Manual de utilização", nome_arquivo="manual.pdf",
        pdf_original=conteudo
    )
    protocolo, _ = servico.consultar(token_autor, protocolo_id)
    assert protocolo.pdf_verificado and not protocolo.validado
    assert protocolo.autor_id == autor.id
    with pytest.raises(DadosInvalidos):
        servico.assinar(token_autor, protocolo_id)
    with pytest.raises(AcessoNegado):
        servico.validar(token_autor, protocolo_id)
    servico.validar(sistema.token, protocolo_id, identidade_conferida=True)
    servico.vincular(sistema.token, protocolo_id, recursos[2].id)
    servico.vincular(sistema.token, protocolo_id, recursos[2].id)
    atual, _ = servico.consultar(sistema.token, protocolo_id)
    assert atual.validado and atual.assinado
    assert [v.equipamento_id for v in atual.vinculos] == [recursos[2].id]
    assert servico.baixar(token_autor, protocolo_id) == ("manual.pdf", conteudo)
    with sistema.transacao() as tx:
        linha = tx._conexao.execute("""
            SELECT assinado_por, validado_por, estado::text AS estado, pdf_original,
                   pdf_politica_verificacao, pdf_sha256
            FROM gestao_lab.protocolo WHERE id=%s
        """, (protocolo_id,)).fetchone()
        assert linha["assinado_por"] == autor.id
        assert linha["validado_por"] == sistema.chefe.id
        assert linha["estado"] == "VALIDADO"
        assert bytes(linha["pdf_original"]) == conteudo
        assert linha["pdf_politica_verificacao"] == "politica-de-teste"
        assert bytes(linha["pdf_sha256"]) == sha256(conteudo).digest()
