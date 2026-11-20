# Migrações

O [schema inicial](../BancoLaboratorioPostgreSQL.sql) registra a versão 1. A aplicação precisa do schema inicial e das migrações abaixo.

| Versão | Arquivo | Mudança |
| --- | --- | --- |
| 2 | [002_pendencias_estoque.sql](002_pendencias_estoque.sql) | Pendências e ciclo de vida dos alertas de estoque. |
| 3 | [003_movimentacao_estoque.sql](003_movimentacao_estoque.sql) | Regras de consumo e descarte na operação de estoque do PostgreSQL. |
| 4 | [004_assinatura_pdf.sql](004_assinatura_pdf.sql) | Registro de evidência da verificação dos PDFs assinados. |
| 5 | [005_assinatura_rsa.sql](005_assinatura_rsa.sql) | Chaves por autor e assinatura RSA realizada pelo próprio sistema. |
| 6 | [006_agente_estoque.sql](006_agente_estoque.sql) | Recomendações preventivas e decisões do Chefe auditáveis (RF26/RF29). |

Cada migração registra sua versão em `gestao_lab.schema_versao`. Em um banco existente, use [08_verificar_instalacao.sql](../08_verificar_instalacao.sql) para identificar as versões pendentes e aplique-as em ordem. Corrija uma migração já aplicada por meio de uma nova versão.
