from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Self

from .usuarios import Usuario
from .salas import Sala
from .bancadas import Bancada
from .equipamentos import Equipamento


@dataclass(frozen=True)
class Sessao:
    usuario_id: int
    expira_em: datetime
    revogado_em: datetime | None

    def esta_valida(self, agora: datetime) -> bool:
        return self.revogado_em is None and self.expira_em > agora


class RepositorioUsuarios(ABC):
    @abstractmethod
    def buscar_por_email(self, email: str) -> Usuario | None: ...

    @abstractmethod
    def buscar_por_id(self, usuario_id: int) -> Usuario | None: ...

    @abstractmethod
    def listar(self, laboratorio_id: int) -> list[Usuario]: ...

    @abstractmethod
    def salvar(self, usuario: Usuario) -> Usuario: ...

    @abstractmethod
    def reservar_id(self) -> int: ...

    @abstractmethod
    def alterar_senha(self, usuario_id: int, senha_hash: str) -> None: ...

    @abstractmethod
    def desativar(
        self, usuario_id: int, laboratorio_id: int
    ) -> bool: ...

    @abstractmethod
    def possui_orientandos_ativos(
        self, professor_id: int
    ) -> bool: ...

class RepositorioLaboratorios(ABC):
    @abstractmethod
    def esta_ativo(self, laboratorio_id: int) -> bool: ...

    @abstractmethod
    def criar(self, nome: str, localizacao: str, chefe_id: int) -> int: ...



class RepositorioRecursos(ABC):
    """Contrato para persistência de salas, bancadas e equipamentos."""

    @abstractmethod
    def salvar_sala(self, sala: Sala) -> Sala:
        """Salva uma sala e devolve o objeto com seu ID."""
        ...

    @abstractmethod
    def salvar_bancada(self, bancada: Bancada) -> Bancada:
        """Salva uma bancada vinculada a uma sala."""
        ...

    @abstractmethod
    def salvar_equipamento(
        self, equipamento: Equipamento
    ) -> Equipamento:
        """Salva um equipamento com patrimônio único."""
        ...

    @abstractmethod
    def buscar_sala(self, sala_id: int) -> Sala | None:
        """Busca uma sala pelo identificador."""
        ...

    @abstractmethod
    def buscar_bancada(self, bancada_id: int) -> Bancada | None:
        """Busca uma bancada pelo identificador."""
        ...

    @abstractmethod
    def listar_salas(self, laboratorio_id: int) -> list[Sala]:
        """Lista as salas de um laboratório."""
        ...

    @abstractmethod
    def listar_bancadas(self, sala_id: int) -> list[Bancada]:
        """Lista as bancadas pertencentes a uma sala."""
        ...

    @abstractmethod
    def listar_equipamentos(
        self, laboratorio_id: int
    ) -> list[Equipamento]:
        """Lista os equipamentos de um laboratório."""
        ...



class RepositorioSessoes(ABC):
    @abstractmethod
    def criar(self, usuario_id: int, token_hash: bytes, expira_em: datetime) -> None: ...

    @abstractmethod
    def buscar(self, token_hash: bytes) -> Sessao | None: ...

    @abstractmethod
    def revogar(self, token_hash: bytes) -> None: ...

    @abstractmethod
    def revogar_do_usuario(self, usuario_id: int) -> None: ...


class UnidadeTrabalho(ABC):
    """Agrupa os repositórios; a operação inteira confirma ou desfaz suas gravações."""

    usuarios: RepositorioUsuarios
    laboratorios: RepositorioLaboratorios
    recursos: RepositorioRecursos
    sessoes: RepositorioSessoes

    @abstractmethod
    def contexto(self, ator_id: int | None, motivo: str) -> None: ...

    @abstractmethod
    def __enter__(self) -> Self: ...

    @abstractmethod
    def __exit__(self, tipo: type[BaseException] | None,
                 erro: BaseException | None, traceback: TracebackType | None) -> bool | None: ...
