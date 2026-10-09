# Migrações

O banco está na versão 1; ainda não há migrações. Alterações futuras usam arquivos sequenciais, como `002_adicionar_campo.sql`, e registram a versão em `gestao_lab.schema_versao`.

Aplique as migrações em ordem. Uma migração aplicada deve ser corrigida por outra versão, sem editar o arquivo anterior.
