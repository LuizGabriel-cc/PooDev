"""Vetores de hash, compatibilidade RSA e detecção de adulterações."""
from hashlib import sha256

import pytest

from gestao_lab.dominio import assinatura_rsa as rsa


@pytest.fixture(scope="module")
def chave_rsa():
    return rsa.gerar_chave()


@pytest.mark.parametrize("mensagem, esperado", [
    (b"", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    (b"abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
    (b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
     "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"),
])
def test_sha256_vetores_conhecidos(mensagem, esperado):
    assert rsa.resumo_sha256(mensagem).hex() == esperado


@pytest.mark.parametrize("tamanho", [1, 55, 56, 63, 64, 65, 119, 120, 127, 128, 129, 8193])
def test_sha256_limites_de_bloco_e_conteudo_binario(tamanho):
    mensagem = bytes(indice % 256 for indice in range(tamanho))
    assert rsa.resumo_sha256(mensagem) == sha256(mensagem).digest()


def test_operacoes_modulares_do_exemplo_do_livro():
    # Kurose e Ross, p. 505: p=5, q=7, n=35, e=5, d=29.
    for mensagem in range(35):
        cifrada = rsa._potencia_modular(mensagem, 5, 35)
        assert rsa._potencia_modular(cifrada, 29, 35) == mensagem
        assert rsa._potencia_modular(mensagem, 29, 35) == pow(mensagem, 29, 35)
    assert rsa._inverso_modular(5, 24) == 5
    with pytest.raises(ValueError):
        rsa._inverso_modular(6, 24)


def test_teste_de_primalidade_recusa_compostos_e_carmichael():
    for numero in (2, 3, 5, 29, 65537):
        assert rsa._primo_provavel(numero)
    for numero in (0, 1, 4, 9, 15, 561, 1105, 1729, 3215031751):
        assert not rsa._primo_provavel(numero)


def test_assinatura_confere_documento_autor_e_codificacao(chave_rsa):
    n, e, d = chave_rsa
    mensagem = b"%PDF-1.4\nDocumento de teste com bytes \x00\xff\n%%EOF"
    assinatura = rsa.assinar(mensagem, n, e, d)
    assert n.bit_length() == 2048 and e == 65537
    assert len(assinatura) == 256
    assert rsa.verificar(mensagem, assinatura, n, e)
    assert rsa.assinar(mensagem, n, e, d) == assinatura
    assert not rsa.verificar(mensagem + b" ", assinatura, n, e)
    assert not rsa.verificar(mensagem, bytes([assinatura[0] ^ 1]) + assinatura[1:], n, e)
    assert not rsa.verificar(mensagem, assinatura, n, 3)
    assert not rsa.verificar(mensagem, assinatura[:-1], n, e)
    assert not rsa.verificar(mensagem, b"\x00" + assinatura, n, e)
    assert not rsa.verificar(mensagem, n.to_bytes(256, "big"), n, e)


def test_verificacao_recusa_padding_divergente(chave_rsa):
    n, e, d = chave_rsa
    mensagem = b"Documento com assinatura codificada"
    codificada = bytearray(rsa._codificar_resumo(rsa.resumo_sha256(mensagem), 256))
    codificada[8] = 0
    assinatura = rsa._potencia_modular(int.from_bytes(codificada, "big"), d, n).to_bytes(256, "big")
    assert not rsa.verificar(mensagem, assinatura, n, e)


def test_assinatura_recusa_chave_privada_incoerente(chave_rsa):
    n, e, d = chave_rsa
    with pytest.raises(ValueError, match="conferir a assinatura"):
        rsa.assinar(b"Documento", n, e, d + 2)
    for privado in (0, 1, n, True, "privado"):
        with pytest.raises(ValueError, match="privada RSA"):
            rsa.assinar(b"Documento", n, e, privado)


@pytest.mark.parametrize("bits", [False, 64, 1024, 2049, 4098, "2048"])
def test_geracao_recusa_tamanho_inadequado(bits):
    with pytest.raises(ValueError):
        rsa.gerar_chave(bits)


def test_limites_e_tipos_de_chaves_e_documentos(chave_rsa):
    n, e, d = chave_rsa
    with pytest.raises(TypeError):
        rsa.resumo_sha256("Documento")
    for modulo, expoente in ((35, 5), (n + 1, e), (True, e), (n, True), (n, 2), (n, n)):
        with pytest.raises(ValueError):
            rsa.assinar(b"Documento", modulo, expoente, d)
        assert not rsa.verificar(b"Documento", b"\x00" * 256, modulo, expoente)
    assert not rsa.verificar("Documento", b"\x00" * 256, n, e)


def test_interoperabilidade_com_verificador_independente(chave_rsa):
    # A dependência é usada somente como referência de teste, fora do núcleo.
    cryptography = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.rsa")
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    n, e, d = chave_rsa
    mensagem = b"PDF com assinatura RSA SHA-256 gerada pelo codigo proprio"
    assinatura = rsa.assinar(mensagem, n, e, d)
    chave_publica = cryptography.RSAPublicNumbers(e, n).public_key()
    chave_publica.verify(assinatura, mensagem, padding.PKCS1v15(), hashes.SHA256())


def test_assinatura_do_resumo_preserva_o_mesmo_formato_e_detecta_adulteracao(chave_rsa):
    n, e, d = chave_rsa
    mensagem = b"Documento processado em uma unica passagem de SHA-256"
    resumo = rsa.resumo_sha256(mensagem)
    assinatura = rsa.assinar_resumo(resumo, n, e, d)
    assert assinatura == rsa.assinar(mensagem, n, e, d)
    assert rsa.verificar_resumo(resumo, assinatura, n, e)
    assert rsa.verificar(mensagem, assinatura, n, e)
    adulterado = bytes([resumo[0] ^ 1]) + resumo[1:]
    assert not rsa.verificar_resumo(adulterado, assinatura, n, e)
    assert not rsa.verificar_resumo(resumo, bytes([assinatura[0] ^ 1]) + assinatura[1:], n, e)


@pytest.mark.parametrize("resumo", [None, "0" * 32, b"", b"x" * 31, b"x" * 33, bytearray(32), 32])
def test_api_de_resumo_recusa_tamanho_ou_tipo_invalido(chave_rsa, resumo):
    n, e, d = chave_rsa
    with pytest.raises(ValueError, match="exatamente 32 bytes"):
        rsa.assinar_resumo(resumo, n, e, d)
    assert not rsa.verificar_resumo(resumo, b"\x00" * 256, n, e)


def test_api_de_resumo_nao_recalcula_hash(chave_rsa, monkeypatch):
    n, e, d = chave_rsa
    resumo = bytes.fromhex("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def recusar_recalculo(dados):
        pytest.fail("A API de resumo não deve calcular novamente o hash.")

    monkeypatch.setattr(rsa, "resumo_sha256", recusar_recalculo)
    assinatura = rsa.assinar_resumo(resumo, n, e, d)
    assert rsa.verificar_resumo(resumo, assinatura, n, e)


def test_interoperabilidade_do_resumo_com_verificador_independente(chave_rsa):
    cryptography = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.rsa")
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, utils

    n, e, d = chave_rsa
    resumo = rsa.resumo_sha256(b"Resumo calculado pelo SHA-256 proprio")
    assinatura = rsa.assinar_resumo(resumo, n, e, d)
    chave_publica = cryptography.RSAPublicNumbers(e, n).public_key()
    chave_publica.verify(assinatura, resumo, padding.PKCS1v15(), utils.Prehashed(hashes.SHA256()))
