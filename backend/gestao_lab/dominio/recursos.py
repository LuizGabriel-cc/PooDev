
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from enum import StrEnum

from .erros import DadosInvalidos
from .usuarios import texto_obrigatorio


class EstadoRecurso(StrEnum):
    DISPONIVEL = "DISPONIVEL"
    MANUTENCAO = "MANUTENCAO"
    DANIFICADO = "DANIFICADO"
    DESATIVADO = "DESATIVADO"


@dataclass(frozen=True, kw_only=True)
class Recurso(ABC):
    nome: str
    localizacao: str
    laboratorio_id: int
    responsavel_usuario_id: int
    id: int | None = None
    estado: EstadoRecurso = EstadoRecurso.DISPONIVEL
    observacao: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "nome",
            texto_obrigatorio(self.nome, "Nome")
        )

        object.__setattr__(
            self, "localizacao",
            texto_obrigatorio(self.localizacao, "Localização", 200)
        )

        if (
            self.laboratorio_id <= 0
            or self.responsavel_usuario_id <= 0
            or (self.id is not None and self.id <= 0)
        ):
            raise DadosInvalidos(
                "Identificador de recurso, laboratório "
                "ou responsável inválido."
            )

        try:
            object.__setattr__(
                self, "estado",
                EstadoRecurso(self.estado)
            )
        except ValueError as erro:
            raise DadosInvalidos(
                "Estado do recurso inválido."
            ) from erro

        if self.observacao is not None:
            object.__setattr__(
                self, "observacao",
                self.observacao.strip() or None
            )

    def esta_disponivel(self) -> bool:
        return self.estado == EstadoRecurso.DISPONIVEL

    def atualizar_status(
        self, novo_estado: EstadoRecurso
    ) -> "Recurso":
        try:
            estado = EstadoRecurso(novo_estado)
        except ValueError as erro:
            raise DadosInvalidos(
                "Estado do recurso inválido."
            ) from erro

        return replace(self, estado=estado)

    @abstractmethod
    def recursos_afetados(self) -> tuple["Recurso", ...]:
        """Retorna este recurso e seus componentes."""
