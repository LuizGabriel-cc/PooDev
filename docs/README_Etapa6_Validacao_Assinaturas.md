# Assinatura RSA de protocolos no sistema

## Usar o fluxo

1. Entre com sua conta e envie o PDF em **Protocolos → Adicionar protocolo**.
2. Abra os detalhes e confira o documento com **Visualizar PDF**.
3. Como autor, clique em **Assinar protocolo**. Na primeira assinatura da conta, o servidor gera sua chave RSA.
4. O Chefe consulta a assinatura, revisa o conteúdo e a autoria e confirma **Validar protocolo**.
5. Após a validação, o Chefe pode vincular equipamentos. O detalhe mostra os nomes e patrimônios junto à prévia.

A assinatura fica armazenada separadamente, associada ao PDF e ao autor no banco. O download devolve os bytes originais do PDF. A assinatura pode ser conferida na página de detalhes do sistema.

## Algoritmo e referência

O núcleo em `backend/gestao_lab/dominio/assinatura_rsa.py` implementa com operações próprias em Python a geração de primos, o teste Miller–Rabin, o algoritmo de Euclides, a exponenciação modular, o SHA-256 e a assinatura/verificação RSA. A biblioteca padrão `secrets` fornece os bits aleatórios.

Kurose e Ross, *Redes de computadores e a Internet*, 6ª edição, pp. 505 e 512–513, descrevem a geração de chaves e a assinatura do resumo de uma mensagem. Para o protótipo, foram escolhidos RSA de 2048 bits, expoente público 65537, SHA-256 e a codificação PKCS#1 v1.5. A operação privada usa mascaramento aleatório e confere o resultado antes de registrá-lo. A [RFC 8017, seção 9.2](https://www.rfc-editor.org/rfc/rfc8017.html#section-9.2) especifica a codificação.

O SHA-256 calcula o resumo dos bytes do PDF. A chave privada assina esse resumo codificado. Na verificação, a chave pública recupera o bloco assinado para comparação estrita com o bloco recalculado do documento.

Para explicar o código: a geração escolhe dois primos prováveis distintos, `p` e `q`, calcula `n = p × q` e `phi = (p − 1) × (q − 1)`. O algoritmo de Euclides estendido encontra `d` de modo que `e × d mod phi = 1`, usando `e = 65537`. A chave pública é `(n, e)` e a privada inclui `d`. Para o bloco codificado `m`, a assinatura corresponde a `s = m^d mod n`; a verificação calcula `s^e mod n` e compara todos os bytes com o bloco esperado. A exponenciação usa quadrados sucessivos, sem construir a potência inteira.

## Persistência e decisões de implementação

A migração [005](../database/migrations/005_assinatura_rsa.sql) adiciona as chaves por autor e a evidência RSA. O servidor guarda a chave privada na tabela restrita `chave_assinatura_usuario`. Ela é acessível pelo papel da aplicação no PostgreSQL. O código evita expor o expoente privado em páginas, resultados públicos e auditoria. Administradores com acesso ao banco continuam tendo acesso às chaves.

A assinatura guarda uma cópia da chave pública usada, o resumo, o autor e a data. Uma transação única registra o resultado. Bloqueios coordenam assinaturas concorrentes e as restrições preservam documentos assinados e decisões do Chefe. Cada laboratório consulta somente seus próprios protocolos.

Esta implementação atende à demonstração acadêmica do algoritmo. Operações em inteiros Python não oferecem garantia de tempo constante, e a guarda de chaves no servidor depende da proteção do banco e do serviço. Um uso externo à avaliação acadêmica exigiria revisão criptográfica e um armazenamento de chaves adequado à implantação.

Registros de assinatura anteriores permanecem no banco com sua evidência original. Uma nova validação administrativa exige assinatura pelo fluxo RSA atual. Para reutilizar o conteúdo de um registro anterior, o autor envia outra versão e a assina no sistema.

## Dependências e testes

A assinatura funciona com a biblioteca padrão do Python. As dependências opcionais de `backend/requirements-assinatura.txt` servem à geração da prévia em imagem. Psycopg continua fornecendo a conexão ao PostgreSQL.

Execute `python -m pytest tests/test_assinatura_rsa.py tests/test_protocolos_semana6.py` em `backend/`. Os testes conferem vetores conhecidos de SHA-256, assinatura RSA, dados adulterados, permissões, isolamento, CSRF e bytes do download. O teste opcional de interoperabilidade usa um verificador independente quando ele está instalado. A integração em PostgreSQL descartável está em `tests/test_integracao_protocolos_semana6.py`.

O hash em Python próprio tem custo proporcional ao tamanho do PDF. No ambiente de desenvolvimento, um arquivo de 5 MiB levou aproximadamente 13 segundos para calcular o resumo; PDFs pequenos são mais adequados para uma demonstração rápida. O serviço calcula o resumo uma vez por operação de assinatura ou verificação.
