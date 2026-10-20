from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from ..dominio.salas import Sala
from ..dominio.bancadas import Bancada
from ..dominio.equipamentos import Equipamento
import secrets

from .seguranca import ProtecaoSenha, TokensSessao
from ..dominio.erros import AcessoNegado, CredenciaisInvalidas, DadosInvalidos
from ..dominio.repositorios import UnidadeTrabalho
from ..dominio.usuarios import Aluno, ChefeLaboratorio, Perfil, Professor, TipoAluno, Usuario, normalizar_email, texto_obrigatorio

FabricaTransacao = Callable[[], UnidadeTrabalho]


@dataclass(frozen=True, kw_only=True)
class DadosCadastro:
    nome: str
    email: str
    senha: str = field(repr=False)
    programa_pos: str = ""
    ramal: str | None = None
    matricula: str = ""
    tipo: str = "GRADUACAO"
    orientador_id: int = 0


class ServicoAutenticacao:
    def __init__(self, transacao: FabricaTransacao, senhas: ProtecaoSenha, horas_sessao: int = 8):
        self._transacao = transacao
        self._senhas = senhas
        self._duracao = timedelta(hours=horas_sessao)
        # A tentativa de um e-mail inexistente também executa uma derivação de senha.
        self._hash_ficticio = senhas.gerar_hash(secrets.token_urlsafe(32))

    def entrar(self, email: str, senha: str) -> str:
        with self._transacao() as tx:
            usuario = tx.usuarios.buscar_por_email(email.strip().lower())
            correto = self._senhas.verificar(senha, usuario.senha_hash if usuario else self._hash_ficticio)
            if not correto or usuario is None or not usuario.ativo or not tx.laboratorios.esta_ativo(usuario.laboratorio_id):
                raise CredenciaisInvalidas("E-mail ou senha inválidos.")
            token = TokensSessao.gerar()
            tx.sessoes.criar(usuario.id, TokensSessao.resumir(token), datetime.now(timezone.utc) + self._duracao)
            return token

    def identificar_na_transacao(self, tx: UnidadeTrabalho, token: str) -> Usuario | None:
        if not TokensSessao.formato_valido(token):
            return None
        sessao = tx.sessoes.buscar(TokensSessao.resumir(token))
        if sessao is None or not sessao.esta_valida(datetime.now(timezone.utc)):
            return None
        usuario = tx.usuarios.buscar_por_id(sessao.usuario_id)
        if usuario is None or not usuario.ativo or not tx.laboratorios.esta_ativo(usuario.laboratorio_id):
            return None
        return usuario

    def identificar(self, token: str) -> Usuario | None:
        if not TokensSessao.formato_valido(token):
            return None
        with self._transacao() as tx:
            return self.identificar_na_transacao(tx, token)

    def sair(self, token: str) -> None:
        if TokensSessao.formato_valido(token):
            with self._transacao() as tx:
                tx.sessoes.revogar(TokensSessao.resumir(token))


class ServicoCadastro:
    def __init__(self, transacao: FabricaTransacao, senhas: ProtecaoSenha, autenticacao: ServicoAutenticacao):
        self._transacao = transacao
        self._senhas = senhas
        self._autenticacao = autenticacao

    def _exigir_chefe(
        self,
        tx: UnidadeTrabalho,
        token: str,
        *,
        para_remocao: bool = False
) -> Usuario:

        ator = self._autenticacao.identificar_na_transacao(tx, token)

        if ator is None:
            raise AcessoNegado("Entre novamente para continuar.")

        if para_remocao and not isinstance(ator, ChefeLaboratorio):
            raise AcessoNegado(
                "Somente o Chefe do laboratório pode remover cadastros."
            )

        ator.exigir_permissao_cadastro()

        return ator

    def listar(self, token: str) -> list[Usuario]:
        with self._transacao() as tx:
            ator = self._exigir_chefe(tx, token)
            return tx.usuarios.listar(ator.laboratorio_id)

    def consultar(self, token: str, usuario_id: int) -> Usuario:
        with self._transacao() as tx:
            ator = self._exigir_chefe(
                tx, token, para_remocao=True
            )

            alvo = tx.usuarios.buscar_por_id(usuario_id)

            if alvo is None or alvo.laboratorio_id != ator.laboratorio_id:
                raise DadosInvalidos(
                "Cadastro não encontrado neste laboratório."
                )

            ator.exigir_permissao_remocao(alvo)

            return alvo


    def remover(self, token: str, usuario_id: int) -> None:
        with self._transacao() as tx:
            ator = self._exigir_chefe(
                tx, token, para_remocao=True
            )

            alvo = tx.usuarios.buscar_por_id(usuario_id)

            if alvo is None or alvo.laboratorio_id != ator.laboratorio_id:
                raise DadosInvalidos(
                    "Cadastro não encontrado neste laboratório."
                )

            ator.exigir_permissao_remocao(alvo)

            if isinstance(alvo, Professor):
                if tx.usuarios.possui_orientandos_ativos(alvo.id):
                    raise DadosInvalidos(
                        "Este professor ainda orienta alunos ativos "
                        "e não pode ter o cadastro removido."
                    )

            tx.contexto(
                ator.id,
                "Desativação de cadastro pelo Chefe de Laboratório"
            )

            if not tx.usuarios.desativar(
                alvo.id, ator.laboratorio_id
            ):
                raise DadosInvalidos(
                    "Este cadastro já está inativo."
                )

            tx.sessoes.revogar_do_usuario(alvo.id)

    def cadastrar(self, token: str, perfil: Perfil, dados: DadosCadastro) -> Usuario:
        with self._transacao() as tx:
            ator = self._exigir_chefe(tx, token)
            base = dict(nome=dados.nome, email=dados.email, laboratorio_id=ator.laboratorio_id, senha_hash="")
            if perfil == Perfil.ALUNO:
                usuario = Aluno(**base, matricula=dados.matricula, tipo=dados.tipo, orientador_id=dados.orientador_id)
                usuario.validar_orientador(tx.usuarios.buscar_por_id(usuario.orientador_id))
            elif perfil == Perfil.PROFESSOR:
                usuario = Professor(**base, programa_pos=dados.programa_pos, ramal=dados.ramal)
            else:
                raise DadosInvalidos("Cada laboratório tem um único Chefe, criado na configuração inicial.")
            # Validamos o objeto antes de calcular o hash e iniciar as gravações.
            usuario = replace(usuario, senha_hash=self._senhas.gerar_hash(dados.senha))
            tx.contexto(ator.id, f"Cadastro de {usuario.perfil.lower()}")
            return tx.usuarios.salvar(usuario)



class ServicoRecursos:
    """Coordena os cadastros de recursos do laboratório."""

    def __init__(
        self,
        transacao: FabricaTransacao,
        autenticacao: ServicoAutenticacao
    ):
        self._transacao = transacao
        self._autenticacao = autenticacao

    def _exigir_chefe(
        self, tx: UnidadeTrabalho, token: str
    ) -> ChefeLaboratorio:

        ator = self._autenticacao.identificar_na_transacao(
            tx, token
        )

        if ator is None:
            raise AcessoNegado(
                "Entre novamente para continuar."
            )

        if not isinstance(ator, ChefeLaboratorio):
            raise AcessoNegado(
                "Somente o Chefe do laboratório "
                "pode cadastrar recursos."
            )

        ator.exigir_permissao_cadastro()
        return ator

    @staticmethod
    def _validar_responsavel(
        tx: UnidadeTrabalho,
        responsavel_id: int,
        laboratorio_id: int
    ) -> None:

        if type(responsavel_id) is not int or responsavel_id <= 0:
            raise DadosInvalidos(
                "Selecione um responsável válido."
            )

        responsavel = tx.usuarios.buscar_por_id(
            responsavel_id
        )

        if (
            not isinstance(responsavel, Professor)
            or not responsavel.ativo
            or responsavel.laboratorio_id != laboratorio_id
        ):
            raise DadosInvalidos(
                "O responsável deve ser um Professor "
                "ativo do mesmo laboratório."
            )

    @staticmethod
    def _buscar_sala(
        tx: UnidadeTrabalho,
        sala_id: int,
        laboratorio_id: int
    ) -> Sala:

        if type(sala_id) is not int or sala_id <= 0:
            raise DadosInvalidos("Selecione uma sala válida.")

        sala = tx.recursos.buscar_sala(sala_id)

        if sala is None or sala.laboratorio_id != laboratorio_id:
            raise DadosInvalidos(
                "Sala não encontrada neste laboratório."
            )

        return sala

    def cadastrar_sala(
        self,
        token: str,
        *,
        nome: str,
        identificacao: str,
        localizacao: str,
        capacidade: int,
        responsavel_id: int | None = None
    ) -> Sala:

        with self._transacao() as tx:
            chefe = self._exigir_chefe(tx, token)

            responsavel = (
                chefe.id
                if responsavel_id is None
                else responsavel_id
            )

            self._validar_responsavel(
                tx, responsavel, chefe.laboratorio_id
            )

            sala = Sala(
                nome=nome,
                identificacao=identificacao,
                localizacao=localizacao,
                capacidade=capacidade,
                laboratorio_id=chefe.laboratorio_id,
                responsavel_usuario_id=responsavel
            )

            tx.contexto(chefe.id, "Cadastro de sala")

            return tx.recursos.salvar_sala(sala)

    def cadastrar_bancada(
        self,
        token: str,
        *,
        nome: str,
        numero_identificacao: str,
        sala_id: int,
        responsavel_id: int | None = None
    ) -> Bancada:

        with self._transacao() as tx:
            chefe = self._exigir_chefe(tx, token)

            sala = self._buscar_sala(
                tx, sala_id, chefe.laboratorio_id
            )

            responsavel = (
                chefe.id
                if responsavel_id is None
                else responsavel_id
            )

            self._validar_responsavel(
                tx, responsavel, chefe.laboratorio_id
            )

            bancada = Bancada(
                nome=nome,
                numero_identificacao=numero_identificacao,
                sala_id=sala_id,
                localizacao=sala.localizacao,
                laboratorio_id=chefe.laboratorio_id,
                responsavel_usuario_id=responsavel
            )

            tx.contexto(chefe.id, "Cadastro de bancada")

            return tx.recursos.salvar_bancada(bancada)

    def cadastrar_equipamento(
        self,
        token: str,
        *,
        nome: str,
        numero_patrimonio: str,
        complemento_local: str,
        bancada_id: int | None = None,
        sala_direta_id: int | None = None,
        foto_uri: str | None = None,
        observacao: str | None = None,
        responsavel_id: int | None = None
    ) -> Equipamento:

        with self._transacao() as tx:
            chefe = self._exigir_chefe(tx, token)

            if (
                (bancada_id is None)
                == (sala_direta_id is None)
            ):
                raise DadosInvalidos(
                    "Informe uma bancada ou uma sala, "
                    "mas não ambas."
                )

            if bancada_id is not None:
                if type(bancada_id) is not int or bancada_id <= 0:
                    raise DadosInvalidos(
                        "Selecione uma bancada válida."
                    )

                bancada = tx.recursos.buscar_bancada(
                    bancada_id
                )

                if (
                    bancada is None
                    or bancada.laboratorio_id != chefe.laboratorio_id
                ):
                    raise DadosInvalidos(
                        "Bancada não encontrada neste laboratório."
                    )

                sala = self._buscar_sala(
                    tx,
                    bancada.sala_id,
                    chefe.laboratorio_id
                )

            else:
                sala = self._buscar_sala(
                    tx,
                    sala_direta_id,
                    chefe.laboratorio_id
                )

            responsavel = (
                chefe.id
                if responsavel_id is None
                else responsavel_id
            )

            self._validar_responsavel(
                tx, responsavel, chefe.laboratorio_id
            )

            equipamento = Equipamento(
                nome=nome,
                numero_patrimonio=numero_patrimonio,
                localizacao=sala.localizacao,
                complemento_local=complemento_local,
                bancada_id=bancada_id,
                sala_direta_id=sala_direta_id,
                foto_uri=foto_uri,
                observacao=observacao,
                laboratorio_id=chefe.laboratorio_id,
                responsavel_usuario_id=responsavel
            )

            tx.contexto(chefe.id, "Cadastro de equipamento")

            return tx.recursos.salvar_equipamento(
                equipamento
            )





class ServicoConfiguracaoInicial:
    """Operações locais de instalação, acessíveis somente pelo terminal do operador."""

    def __init__(self, transacao: FabricaTransacao, senhas: ProtecaoSenha):
        self._transacao = transacao
        self._senhas = senhas

    def criar_chefe(self, laboratorio: str, localizacao: str, dados: DadosCadastro) -> ChefeLaboratorio:
        laboratorio = texto_obrigatorio(laboratorio, "Laboratório")
        localizacao = texto_obrigatorio(localizacao, "Localização", 200)
        senha_hash = self._senhas.gerar_hash(dados.senha)
        with self._transacao() as tx:
            # As FKs adiadas permitem criar Laboratório, Usuário, Professor e Chefe juntos.
            chefe_id = tx.usuarios.reservar_id()
            tx.contexto(None, "Configuração inicial de laboratório e Chefe")
            laboratorio_id = tx.laboratorios.criar(laboratorio, localizacao, chefe_id)
            chefe = ChefeLaboratorio(id=chefe_id, laboratorio_id=laboratorio_id, nome=dados.nome,
                                     email=dados.email, senha_hash=senha_hash,
                                     programa_pos=dados.programa_pos, ramal=dados.ramal)
            return tx.usuarios.salvar(chefe)

    def definir_senha(self, email: str, senha: str) -> None:
        email = normalizar_email(email)
        senha_hash = self._senhas.gerar_hash(senha)
        with self._transacao() as tx:
            usuario = tx.usuarios.buscar_por_email(email)
            if usuario is None:
                raise DadosInvalidos("Usuário não encontrado.")
            tx.contexto(None, "Redefinição de senha pelo operador local")
            tx.usuarios.alterar_senha(usuario.id, senha_hash)
            tx.sessoes.revogar_do_usuario(usuario.id)
