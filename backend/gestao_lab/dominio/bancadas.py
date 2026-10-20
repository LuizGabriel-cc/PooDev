
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .erros import DadosInvalidos
from .recursos import Recurso
from .usuarios import texto_obrigatorio


if TYPE_CHECKING:
    from .equipamentos import Equipamento


@dataclass(frozen=True, kw_only=True)
class Bancada(Recurso):
    numero_identificacao: str
    sala_id: int
    equipamentos: tuple["Equipamento", ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()

        object.__setattr__(
            self,
            "numero_identificacao",
            texto_obrigatorio(
                self.numero_identificacao,
                "Identificação da bancada",
                80
            )
        )

        if type(self.sala_id) is not int or self.sala_id <= 0:
            raise DadosInvalidos(
                "Informe uma sala válida para a bancada."
            )

        if not isinstance(self.equipamentos, tuple):
            raise DadosInvalidos(
                "Os equipamentos devem ser informados em uma tupla."
            )

    def recursos_afetados(self) -> tuple[Recurso, ...]:
        afetados: list[Recurso] = [self]

        for equipamento in self.equipamentos:
            afetados.extend(equipamento.recursos_afetados())

        return tuple(afetados)
