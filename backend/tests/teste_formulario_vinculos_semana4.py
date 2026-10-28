
from gestao_lab.apresentacao.paginas import (
    formulario_vinculos_equipamento
)
from gestao_lab.dominio.usuarios import ChefeLaboratorio
from gestao_lab.dominio.bancadas import Bancada
from gestao_lab.dominio.equipamentos import Equipamento


dados = {
    "laboratorio_id": 1,
    "responsavel_usuario_id": 1,
    "localizacao": "Bloco A"
}

chefe = ChefeLaboratorio(
    id=1,
    laboratorio_id=1,
    nome="Chefe Teste",
    email="chefe@example.org",
    senha_hash="hash_teste",
    programa_pos="Computacao"
)

bancada = Bancada(
    id=20,
    nome="Bancada 1",
    numero_identificacao="B1",
    sala_id=10,
    **dados
)

equipamento_direto = Equipamento(
    id=30,
    nome="Paquimetro",
    numero_patrimonio="213",
    complemento_local="Armario",
    sala_direta_id=10,
    **dados
)

equipamento_vinculado = Equipamento(
    id=31,
    nome="Microscopio",
    numero_patrimonio="214",
    complemento_local="Bancada",
    bancada_id=20,
    **dados
)

html = formulario_vinculos_equipamento(
    chefe,
    "csrf-teste",
    [bancada],
    [equipamento_direto, equipamento_vinculado],
    dados={
        "complemento_local": "<script>teste</script>"
    }
)

# TESTE 1 — Formulários foram criados.
assert "Salvar vínculo" in html
assert "Desvincular equipamento" in html

# TESTE 2 — Operações corretas.
assert 'name="acao" value="vincular"' in html
assert 'name="acao" value="desvincular"' in html

# TESTE 3 — Proteção CSRF nos dois formulários.
assert html.count('name="csrf"') >= 2

# TESTE 4 — Localizações exibidas.
assert "Sala #10 (sem bancada)" in html
assert "Bancada #20" in html

# TESTE 5 — Proteção contra HTML não confiável.
assert "<script>" not in html
assert "&lt;script&gt;" in html

print("Todos os 5 testes do formulário de vínculos passaram!")
