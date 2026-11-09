
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from .erros import DadosInvalidos
from .usuarios import texto_obrigatorio


def _quantidade(valor, campo, permitir_negativo=False):
    if isinstance(valor, bool) or not isinstance(
        valor, (Decimal, int, str)
    ):
        raise DadosInvalidos(
            f"{campo}: informe um número válido."
        )

    try:
        numero = Decimal(str(valor))

        if (
            not numero.is_finite()
            or abs(numero) >= Decimal("10000000000")
            or numero != numero.quantize(Decimal("0.0001"))
        ):
            raise DadosInvalidos(
                f"{campo}: valor fora do limite de 4 casas decimais."
            )

    except (InvalidOperation, ValueError) as erro:
        raise DadosInvalidos(
            f"{campo}: número inválido."
        ) from erro

    if not permitir_negativo and numero < 0:
        raise DadosInvalidos(
            f"{campo} não pode ser negativo."
        )

    return numero


def _id(valor, campo):
    if type(valor) is not int or valor <= 0:
        raise DadosInvalidos(f"{campo} inválido.")


@dataclass(frozen=True, kw_only=True)
class ItemEstoque:
    laboratorio_id: int
    nome: str
    unidade: str
    lote: str = "SEM_LOTE"
    quantidade: Decimal = Decimal("0")
    limite_estoque_baixo: Decimal = Decimal("0")
    validade: date | None = None
    ativo: bool = True
    id: int | None = None

    def __post_init__(self):
        _id(self.laboratorio_id, "Laboratório")

        if self.id is not None:
            _id(self.id, "Item")

        for atributo, rotulo in (
            ("nome", "Nome"),
            ("unidade", "Unidade"),
            ("lote", "Lote")
        ):
            valor = getattr(self, atributo)

            if not isinstance(valor, str):
                raise DadosInvalidos(
                    f"{rotulo} deve ser texto."
                )

            object.__setattr__(
                self,
                atributo,
                texto_obrigatorio(valor, rotulo)
            )

        for atributo, rotulo in (
            ("quantidade", "Quantidade"),
            ("limite_estoque_baixo", "Limite de estoque baixo")
        ):
            object.__setattr__(
                self,
                atributo,
                _quantidade(getattr(self, atributo), rotulo)
            )

        if (
            self.validade is not None
            and type(self.validade) is not date
        ):
            raise DadosInvalidos(
                "Validade deve ser uma data."
            )

    def estoque_baixo(self) -> bool:
        return (
            self.ativo
            and self.quantidade <= self.limite_estoque_baixo
        )

    def validade_proxima(
        self,
        dias: int,
        hoje: date | None = None
    ) -> bool:
        if type(dias) is not int or dias < 0:
            raise DadosInvalidos(
                "Dias de alerta inválidos."
            )

        if hoje is not None and type(hoje) is not date:
            raise DadosInvalidos(
                "Data de referência inválida."
            )

        return (
            self.ativo
            and self.validade is not None
            and self.validade
            <= (hoje or date.today()) + timedelta(days=dias)
        )


@dataclass(frozen=True, kw_only=True)
class MovimentacaoEstoque:
    laboratorio_id: int
    item_id: int
    registrado_por: int
    variacao: Decimal
    quantidade_anterior: Decimal
    quantidade_posterior: Decimal
    motivo: str
    criado_em: datetime
    id: int | None = None

    def __post_init__(self):
        for atributo in (
            "laboratorio_id",
            "item_id",
            "registrado_por"
        ):
            _id(getattr(self, atributo), atributo)

        if self.id is not None:
            _id(self.id, "Movimentação")

        if not isinstance(self.motivo, str):
            raise DadosInvalidos(
                "Motivo deve ser texto."
            )

        object.__setattr__(
            self,
            "motivo",
            texto_obrigatorio(self.motivo, "Motivo", 500)
        )

        for atributo in (
            "variacao",
            "quantidade_anterior",
            "quantidade_posterior"
        ):
            object.__setattr__(
                self,
                atributo,
                _quantidade(
                    getattr(self, atributo),
                    atributo,
                    permitir_negativo=(atributo == "variacao")
                )
            )

        if (
            self.variacao == 0
            or self.quantidade_anterior + self.variacao
            != self.quantidade_posterior
        ):
            raise DadosInvalidos(
                "Movimentação inconsistente com o saldo "
                "anterior e posterior."
            )

        if (
            not isinstance(self.criado_em, datetime)
            or self.criado_em.tzinfo is None
            or self.criado_em.utcoffset() is None
        ):
            raise DadosInvalidos(
                "Informe data e hora com fuso horário."
            )
