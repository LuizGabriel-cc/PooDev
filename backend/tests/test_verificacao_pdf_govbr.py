"""Testes unitários do resultado técnico; não substituem PDFs reais assinados no gov.br."""
import unittest

from gestao_lab.dominio.assinaturas_pdf import (
    EstadoAssinatura, ResultadoAssinatura, nomes_compativeis,
)
from gestao_lab.infraestrutura.verificador_assinatura_pdf import VerificadorAssinaturaPDF


class TesteVerificacaoGovBr(unittest.TestCase):
    def test_identidade_nome_com_acentos(self):
        self.assertTrue(nomes_compativeis("João Silva", "JOAO SILVA:12345678901"))
        self.assertFalse(nomes_compativeis("João Silva", "Maria Silva"))
        self.assertFalse(nomes_compativeis("João Silva", "João"))

    def test_ausencia_de_raiz_nao_gera_aprovacao(self):
        resultado = VerificadorAssinaturaPDF().verificar(b"%PDF-1.4\n")
        self.assertNotEqual(resultado.estado, EstadoAssinatura.VALIDA)

    def test_estado_inconclusivo_nunca_eh_validado(self):
        self.assertFalse(ResultadoAssinatura(EstadoAssinatura.INDETERMINADA).valida)
        self.assertFalse(ResultadoAssinatura(EstadoAssinatura.SEM_ASSINATURA).valida)
        self.assertFalse(ResultadoAssinatura(EstadoAssinatura.INVALIDA).valida)
        self.assertFalse(ResultadoAssinatura(EstadoAssinatura.AUTORIA_DIVERGENTE).valida)
        self.assertTrue(ResultadoAssinatura(EstadoAssinatura.VALIDA).valida)


if __name__ == "__main__":
    unittest.main()
