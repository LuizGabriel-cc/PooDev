from hashlib import sha256
from pathlib import Path


_PASTA = Path(__file__).parent
_ESTILO = (_PASTA / "estilo.css").read_bytes()
_REVISAO_ESTILO = sha256(_ESTILO).hexdigest()[:16]
URL_ESTILO = f"/estilo.css?v={_REVISAO_ESTILO}"

# O HTML online e o precache offline apontam para os mesmos bytes do CSS.
ARQUIVOS_VERSIONADOS = {
    "/estilo.css": _ESTILO,
    "/service-worker.js": (_PASTA / "service-worker.js").read_bytes()
        .replace(b"__URL_ESTILO__", URL_ESTILO.encode("ascii"))
        .replace(b"__REVISAO_ESTILO__", _REVISAO_ESTILO.encode("ascii")),
}
