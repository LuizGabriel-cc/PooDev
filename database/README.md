# Semana 1 — Banco de dados

Esta etapa criou a estrutura PostgreSQL para usuários, salas, bancadas, equipamentos, reservas, chaves, estoque, protocolos e histórico. O banco se chama `gestao_laboratorio` e as tabelas ficam no schema `gestao_lab`.

Um equipamento pode ficar em uma bancada ou diretamente na sala. O patrimônio identifica a unidade física e é único no sistema. Reservas de sala abrangem seus recursos; equipamentos também podem ser reservados individualmente. As regras de integridade ficam no banco.

## Instalação pelo pgAdmin

Use PostgreSQL 16 ou superior e uma conta com permissão para criar banco, schema e a extensão `btree_gist`.

1. Abra o Query Tool do banco `postgres` e execute [00_criar_banco.sql](00_criar_banco.sql), com autocommit habilitado.
2. Atualize a lista de bancos e abra o Query Tool em `gestao_laboratorio`.
3. Abra e execute [BancoLaboratorioPostgreSQL.sql](BancoLaboratorioPostgreSQL.sql).
4. Execute [08_verificar_instalacao.sql](08_verificar_instalacao.sql) para conferir as tabelas, a versão e as funções.
5. Se quiser trabalhar com dados fictícios, execute [03_dados_exemplo.sql](03_dados_exemplo.sql) uma vez.

Se o banco já estiver instalado, comece pela conferência do passo 4. O script principal é para instalação inicial; alterações posteriores ficam em `migrations/`.

## Arquivos de apoio

| Arquivo ou pasta | Uso |
| --- | --- |
| `04_consultas_exemplo.sql` | Exemplos de consulta dos dados. |
| `05_testes_integridade.sql` | Verificação das regras em banco de teste com os dados de exemplo. |
| `06_testar_concorrencia.py` | Testes com duas conexões ao PostgreSQL. |
| `docs/` | [Modelo relacional](docs/ModeloRelacionalLaboratorio.md) e [dicionário de dados](docs/DicionarioDadosLaboratorio.md). |

Na semana 2, o backend passa a usar esse mesmo banco. Informe host, porta, banco, usuário e senha locais no `.env` da raiz, conforme o [README principal](../README.md). Os testes devem usar um banco separado. Senhas e backups ficam fora do repositório.
