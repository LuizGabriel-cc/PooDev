
from dataclasses import dataclass, replace
from datetime import timedelta

from .erros import DadosInvalidos
from .usuarios import texto_obrigatorio


@dataclass(frozen=True, kw_only=True)
class Laboratorio:
    nome: str
    localizacao: str
    chefe_usuario_id: int
    id: int | None = None
    ativo: bool = True
    duracao_maxima_reserva: timedelta | None = None
    max_reservas_simultaneas: int | None = None
    dias_alerta_validade: int = 30

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "nome",
            texto_obrigatorio(self.nome, "Nome")
        )

        object.__setattr__(
            self, "localizacao",
            texto_obrigatorio(self.localizacao, "Localização", 200)
        )

        if self.id is not None and self.id <= 0:
            raise DadosInvalidos(
                "Identificador do laboratório inválido."
            )

        if self.chefe_usuario_id <= 0:
            raise DadosInvalidos(
                "Informe um Chefe de Laboratório válido."
            )

        if (self.duracao_maxima_reserva is not None
                and self.duracao_maxima_reserva <= timedelta(0)):
            raise DadosInvalidos(
                "A duração máxima da reserva deve ser positiva."
            )

        if (self.max_reservas_simultaneas is not None
                and self.max_reservas_simultaneas <= 0):
            raise DadosInvalidos(
                "O limite de reservas simultâneas deve ser positivo."
            )

        if self.dias_alerta_validade < 0:
            raise DadosInvalidos(
                "Os dias de alerta não podem ser negativos."
            )



    
    def configurar_limites(
        self,
        duracao: timedelta | None,
        quantidade: int | None
    ) -> "Laboratorio":
        """Retorna um laboratório com novos limites."""

        if duracao is not None and (
            not isinstance(duracao, timedelta)
            or duracao <= timedelta(0)
        ):
            raise DadosInvalidos(
                "A duração máxima deve ser positiva."
            )

        if quantidade is not None and (
            type(quantidade) is not int
            or quantidade <= 0
        ):
            raise DadosInvalidos(
                "A quantidade máxima deve ser positiva."
            )

        return replace(
            self,
            duracao_maxima_reserva=duracao,
            max_reservas_simultaneas=quantidade
        )
