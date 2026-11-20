# Banco de dados

Esta etapa criou a estrutura PostgreSQL para usuários, salas, bancadas, equipamentos, reservas, chaves, estoque, protocolos e histórico. O banco se chama `gestao_laboratorio` e as tabelas ficam no schema `gestao_lab`.

Um equipamento pode ficar em uma bancada ou diretamente na sala. O patrimônio identifica a unidade física e é único no sistema. Reservas de sala abrangem seus recursos; equipamentos também podem ser reservados individualmente. As regras de integridade ficam no banco.

## Instalação pelo pgAdmin

Use PostgreSQL 16 ou superior e uma conta com permissão para criar banco, schema e a extensão `btree_gist`.

1. Abra o Query Tool do banco `postgres` e execute [00_criar_banco.sql](00_criar_banco.sql), com autocommit habilitado.
2. Atualize a lista de bancos e abra o Query Tool em `gestao_laboratorio`.
3. Abra e execute [BancoLaboratorioPostgreSQL.sql](BancoLaboratorioPostgreSQL.sql) para instalar o schema na versão 1.
4. Aplique as [migrações](migrations/README.md) em ordem até a versão 6.
5. Execute [08_verificar_instalacao.sql](08_verificar_instalacao.sql) para conferir versões e recursos do schema.
6. Se quiser trabalhar com dados fictícios, execute [03_dados_exemplo.sql](03_dados_exemplo.sql) uma vez.

Em um banco com o schema instalado, comece por `08_verificar_instalacao.sql`. Confira `schema_versao`, aplique em ordem somente as migrações pendentes e repita a conferência. Use o script principal apenas na instalação inicial.

## Banco de testes

Crie um banco descartável separado, com um nome que comece por `poodev_teste_` ou `gestao_laboratorio_teste`, por exemplo `poodev_teste_local`. Instale nele o schema principal e todas as migrações em ordem. Aponte `TEST_DATABASE_URL` para esse banco. Os testes de integração gravam dados e histórico, que ficam no banco até seu descarte.

- A suíte `python -m pytest` executada em `backend/` cria sua própria massa de teste.
- Para `05_testes_integridade.sql` e `06_testar_concorrencia.py`, carregue `03_dados_exemplo.sql` uma vez, pois os scripts usam IDs fixos dessa massa. Abra o SQL no banco descartável. Para o script Python, defina `TEST_DATABASE_URL` no ambiente do terminal e execute `python database/06_testar_concorrencia.py` a partir da raiz.

## Arquivos de apoio

| Arquivo ou pasta | Uso |
| --- | --- |
| `04_consultas_exemplo.sql` | Exemplos de consulta dos dados. |
| `05_testes_integridade.sql` | Verificação das regras em banco de teste com os dados de exemplo. |
| `06_testar_concorrencia.py` | Testes com duas conexões ao PostgreSQL que gravam no banco de teste. |
| `docs/` | [Modelo relacional](docs/ModeloRelacionalLaboratorio.md) e [dicionário de dados](docs/DicionarioDadosLaboratorio.md). |

Informe os dados de conexão locais no `.env` da raiz, conforme o [README principal](../README.md). Senhas e backups ficam fora do repositório.
