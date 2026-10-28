
from dataclasses import dataclass, replace

from .erros import DadosInvalidos
from .recursos import Recurso
from .usuarios import texto_obrigatorio
from .bancadas import Bancada
from .salas import Sala

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


    
    def vincular_a_bancada(
        self,
        bancada: Bancada,
        complemento_local: str | None = None
    ) -> "Equipamento":
        """Vincula o equipamento a uma bancada."""

        # O equipamento precisa existir no sistema.
        if self.id is None:
            raise DadosInvalidos(
                "O equipamento precisa estar cadastrado."
            )

        # A bancada precisa estar cadastrada.
        if (
            not isinstance(bancada, Bancada)
            or bancada.id is None
        ):
            raise DadosInvalidos(
                "Selecione uma bancada cadastrada."
            )

        # Não permitimos vínculos entre laboratórios distintos.
        if bancada.laboratorio_id != self.laboratorio_id:
            raise DadosInvalidos(
                "A bancada deve pertencer ao "
                "mesmo laboratório."
            )

        # Impede repetir o mesmo vínculo.
        if self.bancada_id == bancada.id:
            raise DadosInvalidos(
                "O equipamento já está nessa bancada."
            )

        # Retorna um novo objeto com a localização atualizada.
        return replace(
            self,
            bancada_id=bancada.id,
            sala_direta_id=None,
            localizacao=bancada.localizacao,
            complemento_local=(
                self.complemento_local
                if complemento_local is None
                else complemento_local
            )
        )



    def desvincular_da_bancada(
        self,
        bancada_atual: Bancada,
        sala: Sala,
        complemento_local: str | None = None
    ) -> "Equipamento":
        """Retira o equipamento da bancada e o mantém na sala."""

        # Confere se o equipamento está vinculado.
        if self.id is None or self.bancada_id is None:
            raise DadosInvalidos(
                "O equipamento não está vinculado "
                "a uma bancada."
            )

        # Confere a bancada atual.
        if (
            not isinstance(bancada_atual, Bancada)
            or bancada_atual.id != self.bancada_id
            or bancada_atual.laboratorio_id != self.laboratorio_id
        ):
            raise DadosInvalidos(
                "A bancada atual do equipamento é inválida."
            )

        # O equipamento permanece na sala da bancada.
        if (
            not isinstance(sala, Sala)
            or sala.id is None
            or sala.id != bancada_atual.sala_id
            or sala.laboratorio_id != self.laboratorio_id
        ):
            raise DadosInvalidos(
                "Selecione a sala da bancada atual."
            )

        # Remove o vínculo com a bancada.
        return replace(
            self,
            bancada_id=None,
            sala_direta_id=sala.id,
            localizacao=sala.localizacao,
            complemento_local=(
                self.complemento_local
                if complemento_local is None
                else complemento_local
            )
        )
