"""Gera certificados e PDFs de teste locais. Não usa documentos ou dados pessoais."""
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest

from gestao_lab.dominio.assinaturas_pdf import EstadoAssinatura
from gestao_lab.infraestrutura.verificador_assinatura_pdf import (
    POLITICA_PDF, VerificadorAssinaturaPDF,
)

pytest.importorskip("pyhanko.sign")

from asn1crypto import keys, x509 as asn1_x509
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.writer import PageObject, PdfFileWriter
from pyhanko.sign.signers import PdfSignatureMetadata, PdfTimeStamper, SimpleSigner, sign_pdf
from pyhanko.sign.timestamps import DummyTimeStamper
from pyhanko_certvalidator.registry import SimpleCertificateStore


def _certificado(nome, chave, agora):
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nome)])
    return (
        x509.CertificateBuilder().subject_name(nome).public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - timedelta(days=1)).not_valid_after(agora + timedelta(days=1))
    )


def _uso_chave(*, autoridade=False):
    return x509.KeyUsage(
        digital_signature=not autoridade, content_commitment=False, key_encipherment=False,
        data_encipherment=False, key_agreement=False, key_cert_sign=autoridade,
        crl_sign=autoridade, encipher_only=False, decipher_only=False
    )


def _credenciais(certificado, chave):
    return (
        asn1_x509.Certificate.load(certificado.public_bytes(serialization.Encoding.DER)),
        keys.PrivateKeyInfo.load(chave.private_bytes(
            serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()
        )),
    )


@pytest.fixture
def cadeia(tmp_path):
    agora = datetime.now(timezone.utc)
    chave_raiz = ec.generate_private_key(ec.SECP256R1())
    nome_raiz = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Raiz fictícia PooDev")])
    raiz = (
        _certificado("Raiz fictícia PooDev", chave_raiz, agora).issuer_name(nome_raiz)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(_uso_chave(autoridade=True), critical=True)
        .sign(chave_raiz, hashes.SHA256())
    )
    caminho_raiz = tmp_path / "raiz.pem"
    caminho_raiz.write_bytes(raiz.public_bytes(serialization.Encoding.PEM))

    chave_autor = ec.generate_private_key(ec.SECP256R1())
    autor = (
        _certificado("Autor Fictício", chave_autor, agora).issuer_name(raiz.subject)
        .add_extension(_uso_chave(), critical=True)
        .add_extension(x509.CRLDistributionPoints([
            x509.DistributionPoint(
                full_name=[x509.UniformResourceIdentifier("http://example.invalid/revogacao")],
                relative_name=None, reasons=None, crl_issuer=None
            )
        ]), critical=False)
        .sign(chave_raiz, hashes.SHA256())
    )
    chave_tsa = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tsa = (
        _certificado("Carimbo Fictício", chave_tsa, agora).issuer_name(raiz.subject)
        .add_extension(_uso_chave(), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.TIME_STAMPING]), critical=True)
        .sign(chave_raiz, hashes.SHA256())
    )
    return caminho_raiz, raiz, chave_raiz, autor, chave_autor, tsa, chave_tsa, agora


def test_assinatura_real_e_carimbo_com_revogacao_offline(cadeia, tmp_path):
    caminho_raiz, raiz, chave_raiz, autor, chave_autor, tsa, chave_tsa, agora = cadeia
    certificado, chave = _credenciais(autor, chave_autor)
    autor_pdf = SimpleSigner(certificado, chave, SimpleCertificateStore())
    arquivo = PdfFileWriter()
    arquivo.insert_page(PageObject([], [0, 0, 100, 100]))
    assinado = sign_pdf(arquivo, PdfSignatureMetadata(field_name="Assinatura1"), autor_pdf).getvalue()

    verificador_sem_lcr = VerificadorAssinaturaPDF([caminho_raiz])
    assert verificador_sem_lcr.verificar(assinado).estado == EstadoAssinatura.INDETERMINADA

    base_lcr = (
        x509.CertificateRevocationListBuilder().issuer_name(raiz.subject)
        .last_update(agora - timedelta(minutes=1)).next_update(agora + timedelta(hours=1))
    )
    caminho_lcr = tmp_path / "lista.pem"
    caminho_lcr.write_bytes(base_lcr.sign(chave_raiz, hashes.SHA256()).public_bytes(serialization.Encoding.PEM))
    verificador = VerificadorAssinaturaPDF([caminho_raiz], caminhos_crls=[caminho_lcr])
    resultado = verificador.verificar(assinado)
    assert resultado.estado == EstadoAssinatura.VALIDA
    assert resultado.politica == POLITICA_PDF

    adulterado = bytearray(assinado)
    adulterado[7] = ord("6") if adulterado[7] != ord("6") else ord("5")
    assert verificador.verificar(bytes(adulterado)).estado == EstadoAssinatura.INVALIDA

    tsa_cert, tsa_key = _credenciais(tsa, chave_tsa)
    carimbador = PdfTimeStamper(DummyTimeStamper(tsa_cert, tsa_key))
    carimbado = carimbador.timestamp_pdf(
        IncrementalPdfFileWriter(BytesIO(assinado)), "sha256"
    ).getvalue()
    assert verificador.verificar(carimbado).estado == EstadoAssinatura.VALIDA

    revogado = x509.RevokedCertificateBuilder().serial_number(autor.serial_number).revocation_date(
        agora - timedelta(seconds=30)
    ).build()
    caminho_lcr.write_bytes(
        base_lcr.add_revoked_certificate(revogado).sign(chave_raiz, hashes.SHA256())
        .public_bytes(serialization.Encoding.PEM)
    )
    assert verificador.verificar(assinado).estado == EstadoAssinatura.INVALIDA
