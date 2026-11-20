"""RSA e SHA-256 em Python para o exercício de assinatura de protocolos.

O mecanismo segue Kurose e Ross, 6ª ed., pp. 505 e 512–513. A assinatura
usa a codificação RSASSA-PKCS1-v1_5 do RFC 8017, com SHA-256, blinding
durante a operação privada e conferência da assinatura antes de devolvê-la.
As operações em inteiros Python não oferecem execução em tempo constante.
"""
import secrets


POLITICA_ASSINATURA = "rsa-sha256-v1"
_BITS_MINIMOS = 2048
_BITS_MAXIMOS = 4096
_EXPOENTE_PUBLICO = 65537
_MASCARA_32 = 0xFFFFFFFF
_PREFIXO_SHA256 = bytes.fromhex("3031300d060960864801650304020105000420")
_ESTADO_SHA256 = (
    0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A,
    0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19,
)
_CONSTANTES_SHA256 = (
    0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5,
    0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5,
    0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3,
    0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174,
    0xE49B69C1, 0xEFBE4786, 0x0FC19DC6, 0x240CA1CC,
    0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
    0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7,
    0xC6E00BF3, 0xD5A79147, 0x06CA6351, 0x14292967,
    0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13,
    0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85,
    0xA2BFE8A1, 0xA81A664B, 0xC24B8B70, 0xC76C51A3,
    0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
    0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5,
    0x391C0CB3, 0x4ED8AA4A, 0x5B9CCA4F, 0x682E6FF3,
    0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208,
    0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2,
)
_PRIMOS_PEQUENOS = (
    3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59,
    61, 67, 71, 73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127,
    131, 137, 139, 149, 151, 157, 163, 167, 173, 179, 181, 191, 193,
    197, 199, 211, 223, 227, 229, 233, 239, 241, 251,
)


def _rotacionar_direita(numero, quantidade):
    return ((numero >> quantidade) | (numero << (32 - quantidade))) & _MASCARA_32


def _comprimir_sha256(bloco, estado):
    palavras = [int.from_bytes(bloco[inicio:inicio + 4], "big") for inicio in range(0, 64, 4)]
    for indice in range(16, 64):
        anterior_15 = palavras[indice - 15]
        anterior_2 = palavras[indice - 2]
        sigma_0 = (_rotacionar_direita(anterior_15, 7)
                   ^ _rotacionar_direita(anterior_15, 18) ^ (anterior_15 >> 3))
        sigma_1 = (_rotacionar_direita(anterior_2, 17)
                   ^ _rotacionar_direita(anterior_2, 19) ^ (anterior_2 >> 10))
        palavras.append((palavras[indice - 16] + sigma_0 + palavras[indice - 7] + sigma_1) & _MASCARA_32)

    a, b, c, d, e, f, g, h = estado
    for indice, constante in enumerate(_CONSTANTES_SHA256):
        soma_1 = _rotacionar_direita(e, 6) ^ _rotacionar_direita(e, 11) ^ _rotacionar_direita(e, 25)
        escolha = (e & f) ^ (~e & g)
        temporario_1 = (h + soma_1 + escolha + constante + palavras[indice]) & _MASCARA_32
        soma_0 = _rotacionar_direita(a, 2) ^ _rotacionar_direita(a, 13) ^ _rotacionar_direita(a, 22)
        maioria = (a & b) ^ (a & c) ^ (b & c)
        temporario_2 = (soma_0 + maioria) & _MASCARA_32
        h, g, f, e = g, f, e, (d + temporario_1) & _MASCARA_32
        d, c, b, a = c, b, a, (temporario_1 + temporario_2) & _MASCARA_32
    for indice, valor in enumerate((a, b, c, d, e, f, g, h)):
        estado[indice] = (estado[indice] + valor) & _MASCARA_32


def resumo_sha256(dados: bytes) -> bytes:
    """Calcula o SHA-256 em blocos, preservando exatamente os bytes recebidos."""
    if not isinstance(dados, bytes):
        raise TypeError("O documento deve ser informado em bytes.")
    estado = list(_ESTADO_SHA256)
    limite = len(dados) - len(dados) % 64
    vista = memoryview(dados)
    for inicio in range(0, limite, 64):
        _comprimir_sha256(vista[inicio:inicio + 64], estado)
    fim = dados[limite:] + b"\x80"
    fim += b"\x00" * ((56 - len(fim)) % 64)
    fim += (len(dados) * 8).to_bytes(8, "big")
    for inicio in range(0, len(fim), 64):
        _comprimir_sha256(fim[inicio:inicio + 64], estado)
    return b"".join(numero.to_bytes(4, "big") for numero in estado)


def _mdc(primeiro, segundo):
    while segundo:
        primeiro, segundo = segundo, primeiro % segundo
    return primeiro


def _potencia_modular(base, expoente, modulo):
    resultado = 1
    base %= modulo
    while expoente:
        if expoente & 1:
            resultado = resultado * base % modulo
        base = base * base % modulo
        expoente >>= 1
    return resultado


def _inverso_modular(numero, modulo):
    resto_anterior, resto = modulo, numero % modulo
    coeficiente_anterior, coeficiente = 0, 1
    while resto:
        quociente = resto_anterior // resto
        resto_anterior, resto = resto, resto_anterior - quociente * resto
        coeficiente_anterior, coeficiente = coeficiente, coeficiente_anterior - quociente * coeficiente
    if resto_anterior != 1:
        raise ValueError("O número não possui inverso para o módulo informado.")
    return coeficiente_anterior % modulo


def _primo_provavel(numero):
    """Miller–Rabin com 64 bases aleatórias após divisão por primos pequenos."""
    if numero < 2 or numero % 2 == 0:
        return numero == 2
    for primo in _PRIMOS_PEQUENOS:
        if numero % primo == 0:
            return numero == primo
    impar = numero - 1
    potencias_de_dois = 0
    while impar % 2 == 0:
        impar //= 2
        potencias_de_dois += 1
    for _ in range(64):
        base = secrets.randbelow(numero - 3) + 2
        valor = _potencia_modular(base, impar, numero)
        if valor in (1, numero - 1):
            continue
        for _ in range(potencias_de_dois - 1):
            valor = valor * valor % numero
            if valor == numero - 1:
                break
        else:
            return False
    return True


def _gerar_primo(bits):
    while True:
        candidato = secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if (candidato - 1) % _EXPOENTE_PUBLICO != 0 and _primo_provavel(candidato):
            return candidato


def gerar_chave(bits=2048) -> tuple[int, int, int]:
    """Devolve n, e e d. O módulo usa entre 2048 e 4096 bits."""
    if type(bits) is not int or not _BITS_MINIMOS <= bits <= _BITS_MAXIMOS or bits % 2:
        raise ValueError("A chave RSA deve ter um tamanho par entre 2048 e 4096 bits.")
    while True:
        p = _gerar_primo(bits // 2)
        q = _gerar_primo(bits // 2)
        modulo = p * q
        if p == q or modulo.bit_length() != bits:
            continue
        privado = _inverso_modular(_EXPOENTE_PUBLICO, (p - 1) * (q - 1))
        return modulo, _EXPOENTE_PUBLICO, privado


def _validar_chave_publica(n, e):
    if (type(n) is not int or type(e) is not int
            or not _BITS_MINIMOS <= n.bit_length() <= _BITS_MAXIMOS
            or n % 2 == 0 or e % 2 == 0 or not 3 <= e < n):
        raise ValueError("A chave pública RSA é inválida.")


def _codificar_resumo(resumo, tamanho):
    if not isinstance(resumo, bytes) or len(resumo) != 32:
        raise ValueError("O resumo SHA-256 deve conter exatamente 32 bytes.")
    identificacao_e_resumo = _PREFIXO_SHA256 + resumo
    preenchimento = tamanho - len(identificacao_e_resumo) - 3
    if preenchimento < 8:
        raise ValueError("A chave é pequena para a assinatura SHA-256.")
    return b"\x00\x01" + b"\xff" * preenchimento + b"\x00" + identificacao_e_resumo


def assinar(dados: bytes, n: int, e: int, d: int) -> bytes:
    """Calcula o SHA-256 dos bytes e assina o resumo com a chave do autor."""
    return assinar_resumo(resumo_sha256(dados), n, e, d)


def assinar_resumo(resumo: bytes, n: int, e: int, d: int) -> bytes:
    """Assina SHA-256 já calculado usando RSASSA-PKCS1-v1_5 e blinding."""
    _validar_chave_publica(n, e)
    if type(d) is not int or not 1 < d < n:
        raise ValueError("A chave privada RSA é inválida.")
    tamanho = (n.bit_length() + 7) // 8
    mensagem = int.from_bytes(_codificar_resumo(resumo, tamanho), "big")
    while True:
        mascara = secrets.randbelow(n - 3) + 2
        if _mdc(mascara, n) == 1:
            break
    mascarada = mensagem * _potencia_modular(mascara, e, n) % n
    assinatura = _potencia_modular(mascarada, d, n) * _inverso_modular(mascara, n) % n
    if _potencia_modular(assinatura, e, n) != mensagem:
        raise ValueError("Não foi possível conferir a assinatura com as chaves informadas.")
    return assinatura.to_bytes(tamanho, "big")


def verificar(dados: bytes, assinatura: bytes, n: int, e: int) -> bool:
    """Calcula o SHA-256 do documento e confere a assinatura sobre esse resumo."""
    try:
        return verificar_resumo(resumo_sha256(dados), assinatura, n, e)
    except (TypeError, ValueError, OverflowError):
        return False


def verificar_resumo(resumo: bytes, assinatura: bytes, n: int, e: int) -> bool:
    """Confere tamanho, representante RSA e a codificação completa de SHA-256."""
    try:
        _validar_chave_publica(n, e)
        tamanho = (n.bit_length() + 7) // 8
        if not isinstance(assinatura, bytes) or len(assinatura) != tamanho:
            return False
        representante = int.from_bytes(assinatura, "big")
        if representante >= n:
            return False
        esperado = _codificar_resumo(resumo, tamanho)
        recuperado = _potencia_modular(representante, e, n).to_bytes(tamanho, "big")
        return secrets.compare_digest(recuperado, esperado)
    except (TypeError, ValueError, OverflowError):
        return False
