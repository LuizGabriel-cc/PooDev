
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from .erros import DadosInvalidos
from .recursos import Recurso
from .usuarios import texto_obrigatorio


if TYPE_CHECKING:
    from .bancadas import Bancada
    from .equipamentos import Equipamento


@dataclass(frozen=True, kw_only=True)
class Sala(Recurso):
    identificacao: str
    capacidade: int
    bancadas: tuple["Bancada", ...] = ()
    equipamentos_diretos: tuple["Equipamento", ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()

        object.__setattr__(
            self,
            "identificacao",
            texto_obrigatorio(
                self.identificacao, "Identificação", 80
            )
        )

        if type(self.capacidade) is not int or self.capacidade <= 0:
            raise DadosInvalidos(
                "A capacidade da sala deve ser "
                "um inteiro maior que zero."
            )

        if not isinstance(self.bancadas, tuple):
            raise DadosInvalidos(
                "As bancadas devem ser informadas em uma tupla."
            )

        if not isinstance(self.equipamentos_diretos, tuple):
            raise DadosInvalidos(
                "Os equipamentos diretos devem ser informados em uma tupla."
            )

    def recursos_afetados(self) -> tuple[Recurso, ...]:
        afetados: list[Recurso] = [self]

        for bancada in self.bancadas:
            afetados.extend(bancada.recursos_afetados())

        for equipamento in self.equipamentos_diretos:
            afetados.extend(equipamento.recursos_afetados())

        return tuple(afetados)

    
    def adicionar_bancada(self, bancada: "Bancada") -> "Sala":
        if self.id is None:
            raise DadosInvalidos(
                "A sala precisa ter um identificador "
                "antes de vincular uma bancada."
            )

        if (
            bancada.sala_id != self.id
            or bancada.laboratorio_id != self.laboratorio_id
        ):
            raise DadosInvalidos(
                "A bancada deve pertencer a esta sala "
                "e ao mesmo laboratório."
            )

        for existente in self.bancadas:
            if (
                existente.numero_identificacao
                == bancada.numero_identificacao
            ):
                raise DadosInvalidos(
                    "Já existe uma bancada com esta "
                    "identificação na sala."
                )

        return replace(
            self,
            bancadas=(*self.bancadas, bancada)
        )

