from contextlib import closing, contextmanager
from importlib import import_module
from io import BytesIO
from math import isfinite
from threading import Lock

from ..dominio.erros import DadosInvalidos
from ..dominio.protocolos import LIMITE_PDF_BYTES


_LADO_MAXIMO_PX = 1600
_ESCALA_MAXIMA = 1.5
_TRAVA_PDFIUM = Lock()


@contextmanager
def _abrir_pdf(pdf_original: bytes):
    if not isinstance(pdf_original, bytes) or len(pdf_original) > LIMITE_PDF_BYTES:
        raise DadosInvalidos("A prévia está disponível apenas para PDFs de até 5 MB.")
    # O PDFium não admite chamadas simultâneas nem para documentos distintos.
    with _TRAVA_PDFIUM:
        try:
            pdfium = import_module("pypdfium2")
            import_module("PIL.Image")
        except (ImportError, OSError) as erro:
            raise DadosInvalidos(
                "A prévia está indisponível nesta instalação. Use Baixar PDF original."
            ) from erro

        try:
            with closing(pdfium.PdfDocument(pdf_original)) as documento:
                yield documento
        except (RuntimeError, OSError, ValueError, OverflowError) as erro:
            raise DadosInvalidos(
                "Não foi possível gerar a prévia deste arquivo. Use Baixar PDF original."
            ) from erro


def contar_paginas(pdf_original: bytes) -> int:
    with _abrir_pdf(pdf_original) as documento:
        total = len(documento)
        if total < 1:
            raise DadosInvalidos("O PDF não tem páginas para visualizar.")
        return total


def renderizar_previa(pdf_original: bytes, pagina: int) -> bytes:
    if type(pagina) is not int or pagina < 1:
        raise DadosInvalidos("Selecione uma página válida do PDF.")
    with _abrir_pdf(pdf_original) as documento:
        if pagina > len(documento):
            raise DadosInvalidos("Selecione uma página válida do PDF.")
        with closing(documento[pagina - 1]) as folha:
            largura, altura = folha.get_size()
            if not all(isfinite(lado) and lado > 0 for lado in (largura, altura)):
                raise DadosInvalidos("A página tem dimensões inválidas para a prévia.")
            # A renderização arredonda as dimensões em pixels para cima.
            escala = min(_ESCALA_MAXIMA, (_LADO_MAXIMO_PX - 1) / max(largura, altura))
            with closing(folha.render(scale=escala, may_draw_forms=False, draw_annots=True)) as bitmap:
                with bitmap.to_pil() as imagem, BytesIO() as saida:
                    imagem.save(saida, format="PNG")
                    return saida.getvalue()
