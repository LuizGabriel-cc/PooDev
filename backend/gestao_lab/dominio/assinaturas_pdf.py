"""Resultado de verificação de assinaturas digitais associadas aos protocolos."""
from dataclasses import dataclass
from enum import Enum


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
