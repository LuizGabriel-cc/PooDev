
from datetime import datetime, timezone
from types import SimpleNamespace

from gestao_lab.dominio.historico import HistoricoUso
from gestao_lab.apresentacao.paginas import pagina_historico
from gestao_lab.apresentacao.web import AplicacaoWeb


agora = datetime.now(timezone.utc)

usuario = SimpleNamespace(id=1)

criacao = HistoricoUso(
    id=1,
    laboratorio_id=1,
    tabela="reserva",
    registro_id="10",
    acao="INSERT",
    registrado_em=agora,
    ator_id=1,
    depois={"estado": "CONFIRMADA"}
)

cancelamento = HistoricoUso(
    id=2,
    laboratorio_id=1,
    tabela="reserva",
    registro_id="10",
    acao="UPDATE",
    registrado_em=agora,
    ator_id=1,
    motivo="<script>alert(1)</script>",
    antes={"estado": "CONFIRMADA"},
    depois={"estado": "CANCELADA"}
)

html = pagina_historico(
    usuario,
    "csrf-teste",
    [criacao, cancelamento],
    recursos=[],
    usuarios=[]
)

assert "Reserva #10 criada" in html
assert "Reserva #10 cancelada" in html
assert "Consultar histórico" in html

# Verifica que o motivo foi escapado para HTML.
assert "<script>" not in html
assert "&lt;script&gt;" in html

# Usuário comum não recebe filtro de outros usuários.
assert 'name="usuario_id"' not in html

# Verifica o intervalo inclusivo do formulário.
inicio = AplicacaoWeb._data_filtro_historico(
    "2026-11-01"
)
fim = AplicacaoWeb._data_filtro_historico(
    "2026-11-01",
    fim=True
)

assert (fim - inicio).total_seconds() == 86400

print("Todos os testes da página de histórico passaram!")
