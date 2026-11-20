from ..dominio.protocolos import Protocolo, VinculoEquipamento
from ..dominio.repositorios import RepositorioProtocolos


class ProtocolosPostgres(RepositorioProtocolos):
    """Persistência das versões originais em bytea, sem transformação do PDF."""

    _BASE = """
        SELECT p.id, p.laboratorio_id, p.titulo, p.nome_arquivo,
               p.autor_id, u.nome AS autor_nome, p.estado::text AS estado,
               p.criado_em, p.assinado_em, p.validado_em, p.pdf_politica_verificacao
        FROM gestao_lab.protocolo p
        JOIN gestao_lab.usuario u ON u.id = p.autor_id
    """
    _FILTROS = {
        None: "",
        "validados": "AND p.estado = 'VALIDADO' AND p.pdf_politica_verificacao IS NOT NULL",
        "revisao": "AND p.estado = 'NAO_VALIDADO'",
    }

    def __init__(self, conexao):
        self._conexao = conexao

    def bloquear_laboratorio(self, laboratorio_id):
        self._conexao.execute(
            "SELECT 1 FROM gestao_lab.laboratorio WHERE id = %s FOR UPDATE",
            (laboratorio_id,),
        )

    @staticmethod
    def _modelo(linha, vinculos=()):
        return Protocolo(**linha, vinculos=tuple(vinculos))

    def listar(self, laboratorio_id, *, situacao=None):
        filtro = self._FILTROS[situacao]
        linhas = self._conexao.execute(
            self._BASE + f"""
            WHERE p.laboratorio_id = %s
            {filtro}
            ORDER BY p.criado_em DESC, p.id DESC
            LIMIT 200
            """, (laboratorio_id,)
        ).fetchall()
        return [self._modelo(linha) for linha in linhas]

    def buscar(self, protocolo_id, laboratorio_id):
        linha = self._conexao.execute(
            self._BASE + " WHERE p.id = %s AND p.laboratorio_id = %s",
            (protocolo_id, laboratorio_id)
        ).fetchone()
        if linha is None:
            return None
        associados = self._conexao.execute("""
            SELECT pe.equipamento_id, r.nome, e.numero_patrimonio AS patrimonio
            FROM gestao_lab.protocolo_equipamento pe
            JOIN gestao_lab.equipamento e ON e.recurso_id = pe.equipamento_id
            JOIN gestao_lab.recurso r ON r.id = pe.equipamento_id
            WHERE pe.protocolo_id = %s AND pe.laboratorio_id = %s
            ORDER BY r.nome, e.numero_patrimonio
        """, (protocolo_id, laboratorio_id)).fetchall()
        return self._modelo(linha, (VinculoEquipamento(**r) for r in associados))

    def criar(self, laboratorio_id, autor_id, titulo, nome_arquivo, pdf_original):
        resultado = self._conexao.execute("""
            INSERT INTO gestao_lab.protocolo (
                laboratorio_id, titulo, autor_id, nome_arquivo, pdf_original
            ) VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (laboratorio_id, titulo, autor_id, nome_arquivo, pdf_original))
        return resultado.fetchone()["id"]

    def chave_autor(self, usuario_id, laboratorio_id):
        linha = self._conexao.execute("""
            SELECT modulo, expoente_publico, expoente_privado
            FROM gestao_lab.chave_assinatura_usuario
            WHERE usuario_id = %s AND laboratorio_id = %s
        """, (usuario_id, laboratorio_id)).fetchone()
        if linha is None:
            return None
        return tuple(int(linha[nome]) for nome in ("modulo", "expoente_publico", "expoente_privado"))

    def salvar_chave_autor(self, usuario_id, laboratorio_id, modulo, expoente_publico, expoente_privado):
        self._conexao.execute("""
            INSERT INTO gestao_lab.chave_assinatura_usuario
                (usuario_id, laboratorio_id, modulo, expoente_publico, expoente_privado)
            VALUES (%s, %s, %s, %s, %s)
        """, (usuario_id, laboratorio_id, str(modulo), str(expoente_publico), str(expoente_privado)))

    def registrar_assinatura_rsa(self, autor_id, protocolo_id, assinatura, resumo):
        self._conexao.execute(
            "SELECT gestao_lab.registrar_assinatura_rsa(%s, %s, %s, %s)",
            (autor_id, protocolo_id, assinatura, resumo),
        )

    def evidencia_assinatura(self, protocolo_id, laboratorio_id):
        linha = self._conexao.execute("""
            SELECT assinatura_rsa AS assinatura, rsa_resumo AS resumo,
                   rsa_modulo AS modulo, rsa_expoente_publico AS expoente_publico
            FROM gestao_lab.protocolo WHERE id = %s AND laboratorio_id = %s
              AND pdf_politica_verificacao = 'rsa-sha256-v1'
        """, (protocolo_id, laboratorio_id)).fetchone()
        if linha is None or linha["assinatura"] is None:
            return None
        return {"assinatura": bytes(linha["assinatura"]), "resumo": bytes(linha["resumo"]),
                "modulo": int(linha["modulo"]), "expoente_publico": int(linha["expoente_publico"])}

    def validar(self, chefe_id, protocolo_id):
        self._conexao.execute(
            "SELECT gestao_lab.validar_protocolo(%s, %s)",
            (chefe_id, protocolo_id)
        )

    def vincular(self, protocolo_id, equipamento_id, laboratorio_id, chefe_id):
        self._conexao.execute("""
            INSERT INTO gestao_lab.protocolo_equipamento (
                protocolo_id, equipamento_id, laboratorio_id, vinculado_por
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT (protocolo_id, equipamento_id) DO NOTHING
        """, (protocolo_id, equipamento_id, laboratorio_id, chefe_id))

    def arquivo(self, protocolo_id, laboratorio_id):
        linha = self._conexao.execute("""
            SELECT nome_arquivo, pdf_original
            FROM gestao_lab.protocolo
            WHERE id = %s AND laboratorio_id = %s
        """, (protocolo_id, laboratorio_id)).fetchone()
        return (linha["nome_arquivo"], bytes(linha["pdf_original"])) if linha else None
