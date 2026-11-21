# Ajustes de estoque — pendências e alertas

A revisão do controle de estoque distingue **o estado atual de um item** de **um aviso que já foi enviado**. O Chefe pode consultar os itens que precisam de atenção sem receber o mesmo alerta a cada verificação periódica.

## Pendências

A View PostgreSQL `gestao_lab.vw_pendencias_estoque` calcula, para cada item ativo de laboratório ativo, as condições `estoque_baixo`, `vencido` e `validade_proxima`. O prazo de aviso utiliza `laboratorio.dias_alerta_validade`. Um item pode apresentar duas condições ao mesmo tempo, como quantidade baixa e validade expirada.

Itens com quantidade igual a zero não são classificados como vencidos, porque não existe saldo físico a descartar. Ainda podem constar como estoque baixo.

O painel exibe essas pendências e informa a situação de cada item, mesmo quando há saldo suficiente, mas a validade já passou. Os dados são filtrados pelo laboratório do Chefe autenticado.

## Ciclo das notificações

O monitor de estoque executa `gestao_lab.avaliar_alertas_estoque` periodicamente. O cadastro e a movimentação também reavaliam o item afetado. As duas operações usam o mesmo bloqueio do item, e a chave de deduplicação de `notificacao` limita os avisos a um por ocorrência.

A migração 002 acrescenta `notificacao.resolvida_em`. Quando o item é regularizado, fica inativo ou deixa de ter saldo vencido, a notificação é encerrada e sua chave é liberada, preservando o registro histórico. Se o problema voltar depois, outro aviso pode ser criado. O painel mostra somente os avisos ainda abertos, limitados a dez registros; a View é a fonte da situação atual.

A tabela `envio_email` já registra solicitações de envio criadas junto às notificações, mas **o transporte SMTP não foi implementado nesta revisão**. A presença de uma linha nessa tabela não significa que o e-mail foi enviado.

## Retirada de material vencido

O PostgreSQL confere a data de São Paulo. Lotes vencidos admitem descarte. O histórico registra a finalidade da saída separadamente do motivo, que pode ter até 500 caracteres.

Uma entrada na tela de movimentações é para o mesmo lote, com a mesma validade. O sistema bloqueia entradas em lotes vencidos. Para uma reposição de outro lote ou com outra validade, use **Receber novo lote** e informe os dados do material recebido. O formulário copia o nome, a unidade e o limite do item de origem.

Ao retirar toda a quantidade vencida, o aviso de validade é resolvido. O saldo zero continua como pendência de estoque baixo enquanto o lote estiver ativo. Use **Encerrar lote vazio** quando ele sair de uso. Essa operação resolve os avisos daquele lote e mantém o histórico de movimentações e notificações. Os limites continuam sendo avaliados por lote.

## Organização do código

- `dominio/estoque.py`: entidades e regras numéricas mantidas.
- `aplicacao/servicos.py`: permissão do Chefe e encaminhamento da finalidade da saída.
- `dominio/repositorios.py`: contrato de consulta às pendências.
- `infraestrutura/postgres.py`: consultas parametrizadas à View e aos avisos abertos.
- `apresentacao/web.py` e `apresentacao/paginas_estoque.py`: acesso à consulta e apresentação do resultado.
- `database/migrations/002_pendencias_estoque.sql`: evolução do banco sem recriá-lo.
- `database/migrations/003_movimentacao_estoque.sql`: finalidade no histórico, validação no banco e sincronização dos alertas com o saldo.
- `tests/test_pendencias_estoque.py`: regressões isoladas de regras, consulta e interface.

A revisão não implementa o agente especialista nem o envio SMTP. Esses componentes continuam independentes da consulta de pendências.
