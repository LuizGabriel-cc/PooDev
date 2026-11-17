"""Resultado de verificação de assinaturas digitais incorporadas em PDFs."""
from dataclasses import dataclass
from enum import Enum
import re
import unicodedata


class EstadoAssinatura(str, Enum):
    VALIDA = "VALIDA"
    INVALIDA = "INVALIDA"
    SEM_ASSINATURA = "SEM_ASSINATURA"
    AUTORIA_DIVERGENTE = "AUTORIA_DIVERGENTE"
    INDETERMINADA = "INDETERMINADA"


@dataclass(frozen=True)
class ResultadoAssinatura:
    estado: EstadoAssinatura
    signatarios: tuple[str, ...] = ()
    detalhe: str = ""
    politica: str | None = None

    @property
    def valida(self) -> bool:
        return self.estado == EstadoAssinatura.VALIDA


def nomes_compativeis(nome_cadastrado: str, nome_certificado: str) -> bool:
    """Comparação conservadora de nomes, não substitui identificação civil."""
    def normalizar(texto: str) -> str:
        texto = texto.split(":", 1)[0]  # alguns certificados têm identificador após ':'
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(c for c in texto if not unicodedata.combining(c))
        return re.sub(r"\s+", " ", re.sub(r"[^A-Z ]", " ", texto.upper())).strip()
    a, b = normalizar(nome_cadastrado), normalizar(nome_certificado)
    return bool(a and b and len(a.split()) >= 2 and a == b)
