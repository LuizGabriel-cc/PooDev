# Sistema de Gestão de Laboratório de Pesquisa

Projeto da disciplina Paradigma Orientado a Objetos para Desenvolvimento de Software, do curso de Ciência da Computação da UENF.

O sistema será desenvolvido para cadastrar usuários e organizar o uso dos recursos do laboratório. A programação é feita em Python pelo VS Code. O PostgreSQL armazena os dados e o pgAdmin é usado para instalar e consultar o banco.

## Organização

| Pasta | Conteúdo |
| --- | --- |
| `backend/` | Aplicação Python e testes. |
| `database/` | Scripts SQL e referências do banco. |
| `docs/` | Guias de cada etapa e documentação do projeto. |
| `.vscode/` | Configurações de execução e depuração. |

- [Semana 1 — banco de dados](database/README.md).
- [Semana 2 — cadastro de perfis](docs/README_Etapa2.md).
- [Semana 4 — reservas e controle de chaves](docs/README_Etapa4.md).
- [Semanas 5 e 6 — estoque e protocolos](docs/README_Etapa5e6.md).
- [Pendências e alertas de estoque](docs/README_Ajustes_Estoque.md).
- [Verificação de assinaturas gov.br](docs/README_Etapa6_Validacao_Assinaturas.md).
- [Etapa 7 — Restrições, manutenção, ocorrências e e-mail institucional](docs/README_Etapa7.md).
- [Proposta inicial do projeto](docs/SistemaDeGestaoDeLaboratorio.pdf).

## Instalação e testes

1. Instale o banco e aplique as migrações seguindo o [guia do PostgreSQL](database/README.md).
2. Selecione o ambiente virtual Python no VS Code e execute a tarefa **Laboratório: instalar dependências**. Pelo terminal, na raiz, use `python -m pip install -r backend/requirements-dev.txt -r backend/requirements-assinatura.txt`.
3. Copie `.env.example` para `.env` e configure a conexão do banco e os caminhos locais dos certificados. Siga o guia de assinaturas para montar a cadeia de confiança.
4. Use **Laboratório: criar Chefe inicial** para preparar um banco vazio e **Laboratório: iniciar sistema** para abrir a aplicação local.

Execute `python -m pytest -m "not integracao"` em `backend/` para os testes sem PostgreSQL. A suíte de integração usa um banco descartável em `TEST_DATABASE_URL`. O [guia do PostgreSQL](database/README.md) descreve seu preparo e os scripts SQL de teste.
