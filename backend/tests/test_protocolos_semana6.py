"""Fluxo de protocolo assinado no sistema, com persistência simulada."""
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from functools import lru_cache
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import urlencode
from unittest.mock import patch

from gestao_lab.aplicacao.protocolos import ServicoProtocolos
from gestao_lab.apresentacao.web import AplicacaoWeb
from gestao_lab.dominio.assinaturas_pdf import EstadoAssinatura
from gestao_lab.dominio.erros import AcessoNegado, DadosInvalidos
from gestao_lab.dominio.protocolos import LIMITE_PDF_BYTES, Protocolo, VinculoEquipamento, validar_documento_pdf
from gestao_lab.dominio.usuarios import Aluno, ChefeLaboratorio


PDF = b"%PDF-1.4\n\x00\xe2\x93\x99conteudo original\n%%EOF"


@lru_cache(maxsize=1)
def chave_de_teste():
    from gestao_lab.dominio.assinatura_rsa import gerar_chave

    return gerar_chave()


class ProtocolosEmMemoria:
    def __init__(self):
        self.registros = {}
        self.arquivos = {}
        self.vinculos = {}
        self.chaves = {(1, 2): chave_de_teste()}
        self.assinaturas = {}

    def bloquear_laboratorio(self, laboratorio_id):
        pass

    def criar(self, lab, autor, titulo, nome, pdf):
        identificador = len(self.registros) + 1
        self.registros[identificador] = Protocolo(
            id=identificador, laboratorio_id=lab, titulo=titulo, nome_arquivo=nome,
            autor_id=autor, autor_nome="Autor de teste", estado="NAO_VALIDADO",
            criado_em=datetime.now(timezone.utc), assinado_em=None, validado_em=None,
        )
        self.arquivos[identificador] = pdf
        return identificador

    def listar(self, lab, *, situacao=None):
        protocolos = [p for p in self.registros.values() if p.laboratorio_id == lab]
        if situacao is None:
            return protocolos
        return [p for p in protocolos if p.validado == (situacao == "validados")]

    def buscar(self, protocolo_id, lab, *, bloquear=False):
        protocolo = self.registros.get(protocolo_id)
        if protocolo is None or protocolo.laboratorio_id != lab:
            return None
        return replace(protocolo, vinculos=tuple(self.vinculos.get(protocolo_id, [])))

    def chave_autor(self, usuario_id, laboratorio_id):
        return self.chaves.get((laboratorio_id, usuario_id))

    def salvar_chave_autor(self, usuario_id, laboratorio_id, n, e, d):
        self.chaves[(laboratorio_id, usuario_id)] = (n, e, d)

    def registrar_assinatura_rsa(self, autor, protocolo_id, assinatura, resumo):
        p = self.registros[protocolo_id]
        if p.autor_id != autor or p.assinado:
            raise DadosInvalidos("Somente o autor pode assinar protocolo ainda não assinado.")
        n, e, _ = self.chave_autor(autor, p.laboratorio_id)
        self.assinaturas[protocolo_id] = {
            "assinatura": assinatura, "resumo": resumo, "modulo": n, "expoente_publico": e,
        }
        self.registros[protocolo_id] = replace(
            p, assinado_em=datetime.now(timezone.utc), pdf_politica_verificacao="rsa-sha256-v1",
        )

    def evidencia_assinatura(self, protocolo_id, laboratorio_id):
        return self.assinaturas.get(protocolo_id) if self.buscar(protocolo_id, laboratorio_id) else None

    def validar(self, chefe, protocolo_id):
        p = self.registros[protocolo_id]
        self.registros[protocolo_id] = replace(p, estado="VALIDADO", validado_em=datetime.now(timezone.utc))

    def vincular(self, protocolo_id, equipamento_id, lab, chefe):
        vinculos = self.vinculos.setdefault(protocolo_id, [])
        if not any(v.equipamento_id == equipamento_id for v in vinculos):
            vinculos.append(VinculoEquipamento(equipamento_id, "Microscópio", "EQ-1"))

    def arquivo(self, protocolo_id, lab):
        p = self.buscar(protocolo_id, lab)
        return (p.nome_arquivo, self.arquivos[p.id]) if p else None


class TransacaoFalsa:
    def __init__(self, repositorio):
        self.protocolos = repositorio
        self.recursos = SimpleNamespace(listar_equipamentos=lambda lab: [
            SimpleNamespace(id=10, laboratorio_id=1, nome="Microscópio", numero_patrimonio="EQ-1")
        ] if lab == 1 else [])
        self.contextos = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def contexto(self, ator_id, motivo):
        self.contextos.append((ator_id, motivo))


class AutenticacaoFalsa:
    def __init__(self, usuarios):
        self.usuarios = usuarios

    def identificar_na_transacao(self, tx, token):
        usuario = self.usuarios.get(token)
        return usuario if usuario is not None and usuario.ativo else None

    def identificar(self, token):
        return self.identificar_na_transacao(None, token)


def sistema_falso():
    chefe = ChefeLaboratorio(id=1, nome="Chefe de teste", email="chefe@example.org",
                             laboratorio_id=1, senha_hash="hash", programa_pos="Biociências")
    aluno = Aluno(id=2, nome="Autor de teste", email="autor@example.org", laboratorio_id=1,
                  senha_hash="hash", matricula="AL-1", orientador_id=1, tipo="GRADUACAO")
    outro = ChefeLaboratorio(id=3, nome="Outro chefe", email="outro@example.org",
                             laboratorio_id=2, senha_hash="hash", programa_pos="Biociências")
    repositorio = ProtocolosEmMemoria()
    tx = TransacaoFalsa(repositorio)
    auth = AutenticacaoFalsa({"chefe": chefe, "autor": aluno, "outro": outro})
    tx.usuarios = SimpleNamespace(buscar_por_id=lambda id_, **kwargs: next(
        (u for u in auth.usuarios.values() if u.id == id_), None))
    return ServicoProtocolos(lambda: tx, auth), repositorio, auth


def cadastrar(servico):
    return servico.cadastrar("autor", titulo="Manual", nome_arquivo="manual.pdf", pdf_original=PDF)


class TesteProtocolos(unittest.TestCase):
    def test_valida_tipo_tamanho_extensao_e_nao_muda_bytes(self):
        self.assertEqual(validar_documento_pdf(" Título ", "documento.PDF", PDF), ("Título", "documento.PDF"))
        for nome, arquivo in [("../x.pdf", PDF), ("x.txt", PDF), ("x.pdf", b"texto"),
                              ("x.pdf", b"%PDF-" + b"x" * LIMITE_PDF_BYTES)]:
            with self.subTest(nome=nome, tamanho=len(arquivo)), self.assertRaises(DadosInvalidos):
                validar_documento_pdf("Título", nome, arquivo)

    def test_envio_simples_assinatura_autor_validacao_chefe_e_vinculo(self):
        servico, repositorio, _ = sistema_falso()
        pid = cadastrar(servico)
        p, _ = servico.consultar("autor", pid)
        self.assertFalse(p.assinado)
        self.assertEqual(servico.verificar_assinatura("autor", pid).estado, EstadoAssinatura.SEM_ASSINATURA)
        self.assertEqual([p.id for p in servico.listar("chefe", situacao="revisao")], [pid])
        with self.assertRaises(DadosInvalidos):
            servico.validar("chefe", pid, identidade_conferida=True)
        with self.assertRaises(DadosInvalidos):
            servico.vincular("chefe", pid, 10)
        servico.assinar("autor", pid)
        self.assertEqual(servico.verificar_assinatura("autor", pid).estado, EstadoAssinatura.VALIDA)
        with self.assertRaises(DadosInvalidos):
            servico.assinar("autor", pid)
        with self.assertRaises(AcessoNegado):
            servico.validar("autor", pid, identidade_conferida=True)
        with self.assertRaises(DadosInvalidos):
            servico.validar("chefe", pid)
        servico.validar("chefe", pid, identidade_conferida=True)
        servico.vincular("chefe", pid, 10)
        servico.vincular("chefe", pid, 10)
        p, _ = servico.consultar("chefe", pid)
        self.assertTrue(p.assinado and p.validado)
        self.assertEqual(len(p.vinculos), 1)
        self.assertEqual(servico.baixar("autor", pid), ("manual.pdf", PDF))
        self.assertEqual(repositorio.arquivos[pid], PDF)

    def test_assinatura_exige_autor_ativo_e_mesmo_laboratorio(self):
        servico, repositorio, auth = sistema_falso()
        pid = cadastrar(servico)
        with self.assertRaises(AcessoNegado):
            servico.assinar("chefe", pid)
        with self.assertRaises(DadosInvalidos):
            servico.assinar("outro", pid)
        auth.usuarios["autor"] = replace(auth.usuarios["autor"], ativo=False)
        with self.assertRaises(AcessoNegado):
            servico.assinar("autor", pid)
        self.assertFalse(repositorio.registros[pid].assinado)

    def test_alteracao_do_pdf_ou_da_assinatura_impede_validacao(self):
        for campo in ("pdf", "assinatura", "resumo"):
            with self.subTest(campo=campo):
                servico, repositorio, _ = sistema_falso()
                pid = cadastrar(servico)
                servico.assinar("autor", pid)
                if campo == "pdf":
                    repositorio.arquivos[pid] += b"\nALTERADO"
                else:
                    valor = repositorio.assinaturas[pid][campo]
                    repositorio.assinaturas[pid][campo] = bytes([valor[0] ^ 1]) + valor[1:]
                self.assertEqual(servico.verificar_assinatura("chefe", pid).estado, EstadoAssinatura.INVALIDA)
                with self.assertRaises(DadosInvalidos):
                    servico.validar("chefe", pid, identidade_conferida=True)

    def test_evidencia_antiga_nao_e_assinatura_rsa(self):
        servico, repositorio, _ = sistema_falso()
        pid = cadastrar(servico)
        repositorio.registros[pid] = replace(repositorio.registros[pid],
            assinado_em=datetime.now(timezone.utc), pdf_politica_verificacao="politica-anterior")
        self.assertEqual(servico.verificar_assinatura("chefe", pid).estado, EstadoAssinatura.INDETERMINADA)
        with self.assertRaises(DadosInvalidos):
            servico.validar("chefe", pid, identidade_conferida=True)
        self.assertEqual(servico.baixar("autor", pid)[1], PDF)

    def test_sessao_invalida_e_isolamento_de_laboratorio(self):
        servico, repositorio, _ = sistema_falso()
        with self.assertRaises(AcessoNegado):
            servico.cadastrar("inexistente", titulo="Manual", nome_arquivo="manual.pdf", pdf_original=PDF)
        self.assertFalse(repositorio.registros)
        pid = cadastrar(servico)
        self.assertEqual(servico.listar("outro"), [])
        for operacao in (servico.consultar, servico.baixar, servico.verificar_assinatura):
            with self.assertRaises(DadosInvalidos):
                operacao("outro", pid)
        with self.assertRaises(DadosInvalidos):
            servico.listar("autor", situacao="anteriores")

    def test_wsgi_upload_assinar_csrf_validar_e_preservar_pdf(self):
        servico, _, auth = sistema_falso()
        app = AplicacaoWeb(auth, None, SimpleNamespace(porta=8000, segredo_csrf=b"segredo-de-teste-para-protocolo-2026"), protocolos=servico)
        token = "autor"

        def requisitar(rota, corpo=b"", tipo="application/x-www-form-urlencoded", metodo="GET"):
            resposta = {}
            ambiente = {"REQUEST_METHOD": metodo, "PATH_INFO": rota.split("?")[0],
                "QUERY_STRING": rota.partition("?")[2], "HTTP_HOST": "127.0.0.1:8000",
                "HTTP_COOKIE": f"lab_sessao={token}", "wsgi.url_scheme": "http",
                "wsgi.input": BytesIO(corpo), "CONTENT_LENGTH": str(len(corpo)), "CONTENT_TYPE": tipo}
            def iniciar(status, headers):
                resposta.update(status=int(status.split()[0]), headers=dict(headers))
            resposta["body"] = b"".join(app(ambiente, iniciar))
            return resposta

        formulario = requisitar("/protocolos/novo")
        self.assertEqual(formulario["status"], 200)
        self.assertNotIn(b"gov.br", formulario["body"])
        csrf = app._csrf.para_sessao(token)
        fronteira = b"fronteira-local-2026"
        partes = [
            (b'Content-Disposition: form-data; name="csrf"', csrf.encode()),
            (b'Content-Disposition: form-data; name="titulo"', b"Manual <script>"),
            (b'Content-Disposition: form-data; name="arquivo"; filename="manual.pdf"\r\nContent-Type: application/pdf', PDF),
        ]
        corpo = b"".join(b"--" + fronteira + b"\r\n" + h + b"\r\n\r\n" + v + b"\r\n" for h, v in partes)
        corpo += b"--" + fronteira + b"--\r\n"
        tipo = "multipart/form-data; boundary=" + fronteira.decode()
        self.assertEqual(requisitar("/protocolos/novo", corpo.replace(csrf.encode(), b"invalido"), tipo, "POST")["status"], 403)
        self.assertEqual(requisitar("/protocolos/novo", corpo, tipo, "POST")["status"], 303)
        detalhe = requisitar("/protocolos/detalhe?id=1")
        self.assertIn(b' action="/protocolos/assinar"', detalhe["body"])
        self.assertIn(b"&lt;script&gt;", detalhe["body"])
        self.assertNotIn(b"<script>", detalhe["body"])
        self.assertEqual(requisitar("/protocolos/assinar", urlencode({"protocolo_id": 1}).encode(), metodo="POST")["status"], 403)
        campos = urlencode({"csrf": csrf, "protocolo_id": 1}).encode()
        self.assertEqual(requisitar("/protocolos/assinar", campos, metodo="POST")["status"], 303)
        self.assertEqual(requisitar("/protocolos/assinar", campos, metodo="POST")["status"], 400)
        self.assertNotIn(str(chave_de_teste()[2]).encode(), requisitar("/protocolos/detalhe?id=1")["body"])
        baixado = requisitar("/protocolos/download?id=1")
        self.assertEqual(baixado["body"], PDF)
        self.assertIn("attachment;", baixado["headers"]["Content-Disposition"])
        with patch("gestao_lab.apresentacao.web.contar_paginas", return_value=2), patch(
                "gestao_lab.apresentacao.web.renderizar_previa", return_value=b"\x89PNG\r\n\x1a\n"):
            self.assertEqual(requisitar("/protocolos/detalhe?id=1&pagina=1")["status"], 200)
            previa = requisitar("/protocolos/previa?id=1&pagina=1")
            self.assertEqual(previa["headers"]["Content-Type"], "image/png")
            self.assertEqual(previa["headers"]["Cache-Control"], "no-store")
            token = "outro"
            self.assertEqual(requisitar("/protocolos/previa?id=1&pagina=1")["status"], 400)
        token = "chefe"
        campos = urlencode({"csrf": app._csrf.para_sessao(token), "protocolo_id": 1, "identidade_conferida": "sim"}).encode()
        self.assertEqual(requisitar("/protocolos/validar", campos, metodo="POST")["status"], 303)
        self.assertIn(b"Manual &lt;script&gt;", requisitar("/protocolos")["body"])


if __name__ == "__main__":
    unittest.main()
