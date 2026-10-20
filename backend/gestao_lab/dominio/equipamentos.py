
from dataclasses import dataclass

from .erros import DadosInvalidos
from .recursos import Recurso
from .usuarios import texto_obrigatorio


@dataclass(frozen=True, kw_only=True)
class Equipamento(Recurso):
    numero_patrimonio: str
    complemento_local: str
    bancada_id: int | None = None
    sala_direta_id: int | None = None
    foto_uri: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()

        object.__setattr__(
            self,
            "numero_patrimonio",
            texto_obrigatorio(
                self.numero_patrimonio,
                "Número de patrimônio",
                80
            )
        )

        object.__setattr__(
            self,
            "complemento_local",
            texto_obrigatorio(
                self.complemento_local,
                "Complemento do local",
                200
            )
        )

        # O equipamento deve estar em uma bancada
        # OU diretamente em uma sala.
        if (
            (self.bancada_id is None)
            == (self.sala_direta_id is None)
        ):
            raise DadosInvalidos(
                "Informe uma bancada ou uma sala "
                "para o equipamento, mas não ambas."
            )

        if self.bancada_id is not None:
            if type(self.bancada_id) is not int or self.bancada_id <= 0:
                raise DadosInvalidos(
                    "Identificador da bancada inválido."
                )

        if self.sala_direta_id is not None:
            if (
                type(self.sala_direta_id) is not int
                or self.sala_direta_id <= 0
            ):
                raise DadosInvalidos(
                    "Identificador da sala inválido."
                )

        if self.foto_uri is not None:
            object.__setattr__(
                self,
                "foto_uri",
                texto_obrigatorio(
                    self.foto_uri,
                    "Endereço da foto",
                    500
                )
            )

    def recursos_afetados(self) -> tuple[Recurso, ...]:
        return (self,)
