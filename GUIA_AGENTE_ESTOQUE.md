# Protótipo do Agente Especialista de Controle Preventivo de Estoque (RF26/RF29)

**Base:** `Definicao_Agente_Controle_Estoque_PooDev.pdf`, proposta de 09/11/2026.  
**Estado:** segunda versão funcional em avaliação; **não homologada em PostgreSQL neste ambiente**, sujeita à execução local dos testes e à validação da professora.

## 1. O que foi implementado

O agente é **um sistema especialista com regras explícitas + estimativa estatística**. Ele não é um chatbot, não faz chamadas a APIs externas e não usa redes neurais. É uma opção de inteligência artificial simbólica/explicável, coerente com as opções ainda em discussão no documento.

- Acesso exclusivo ao Chefe responsável pelo laboratório.
- Análise por **item e lote**, com base na quantidade atual, no limite mínimo e no histórico do **próprio laboratório**.
- Considera **somente saídas com finalidade `USO`** como consumo efetivo. Ignora entradas e descartes. Se existem saídas legadas sem finalidade no intervalo, retorna resultado **inconclusivo**.
- Não estima consumo com histórico insuficiente, consumo zero ou lote vencido. Quando o limite já foi alcançado, informa `MINIMO_ATINGIDO` e remete aos alertas já existentes (RF08).
- Estima consumo diário médio e o prazo até o mínimo; recomenda revisão de reposição se o prazo previsto for igual ou inferior ao horizonte de alerta.
- Exibe evidências, explicação e, onde houver histórico suficiente, **MAE retrospectivo** da média de treinamento contra os últimos 7 dias completos.
- O Chefe pode acionar manualmente a análise. Além disso, um **monitor automático** reavalia a cada 10 minutos enquanto o servidor local está ligado, registra recomendações elegíveis e dispara notificação no sino/e-mail enfileirado. O Chefe pode **aceitar a avaliação** ou **descartar**. A decisão registra identidade e data; não existe compra automática.
- No banco, só existe **uma recomendação pendente por lote**. A mesma evidência de movimentação não reabre recomendação já decidida; nova movimentação permite atualizar uma pendência ou gerar uma nova recomendação quando necessário.

**Não realiza:** atualização de saldo, bloqueios, compras, IA generativa, classificação retroativa de movimentos sem finalidade, nem substituição dos alertas RF08. O monitor depende de o servidor estar em execução; não é um serviço agendado do sistema operacional. Todas as operações existentes continuam independentes do agente.

## 2. Arquivos novos

| Arquivo | Responsabilidade |
| --- | --- |
| `backend/gestao_lab/dominio/agente_estoque.py` | Classes de dados, política de cálculo e explicação (POO pura, sem HTTP e SQL) |
| `backend/gestao_lab/aplicacao/agente_estoque.py` | Caso de uso, autenticação/autorização, análise e decisão humana |
| `backend/gestao_lab/infraestrutura/agente_estoque_postgres.py` | Consultas filtradas por laboratório, persistência, deduplicação, auditoria |
| `backend/gestao_lab/apresentacao/paginas_agente_estoque.py` | Interface HTML, justificativas, previsões e formulário de decisão |
| `database/migrations/006_agente_estoque.sql` | Tabela `recomendacao_estoque`, índices e proteção de decisões |
| `backend/tests/test_agente_estoque.py` | Testes isolados para cálculo, insuficiência, separação de laboratórios, acesso e UI |

Os pontos de inicialização, roteamento e menu foram integrados em `__main__.py`, `web.py`, `navegacao.py`, `postgres.py`, `repositorios.py` e nas instruções do banco.

## 3. Parâmetros PROVISÓRIOS

Definidos na classe `ParametrosAgenteEstoque`, dentro de `backend/gestao_lab/dominio/agente_estoque.py`:

- `janela_dias = 30` — movimentações dos últimos 30 dias.
- `antecedencia_dias = 7` — prazo para sinalizar risco preventivo.
- `minimo_dias_observados = 7` — dias mínimos desde o primeiro registro observável dentro da janela.
- `minimo_dias_com_consumo = 3` — pelo menos 3 dias distintos com consumo efetivo.

Esses valores foram escolhidos para viabilizar um **protótipo**, não estão definidos como obrigatórios na proposta. Confirmar com a professora antes da entrega.

### Fórmula inicial

`consumo_diario = soma(saídas USO dos últimos 30 dias) / número de dias observados`

`dias_ate_minimo = (saldo_atual - limite_minimo) / consumo_diario`

Exemplo ilustrativo do PDF: `(12 L - 5 L) / (1 L/dia) = 7 dias`.

**Limitações:** ritmo médio constante é uma aproximação; demanda variável, sazonalidade, novos experimentos, descarte e validade podem mudar a necessidade de reposição. O MAE mede o erro da média calculada apenas com os dias de treinamento anteriores à última semana e compara com uma **referência ingênua** (o consumo no último dia do treino, repetido para cada dia dos 7 dias de avaliação). A estabilidade qualitativa é heurística, não uma probabilidade nem garantia de desempenho futuro.

## 4. Instalação no ambiente de desenvolvimento

**Faça backup do PostgreSQL antes de migrar o banco. Teste primeiro em um banco descartável.**

1. Extraia este projeto em uma pasta nova, sem sobrescrever a versão original.
2. Instale as dependências a partir da pasta `backend`:

   ```bash
   python -m pip install -r requirements.txt
   python -m pip install -r requirements-dev.txt
   ```

3. No PostgreSQL de testes com a versão 5 já instalada, abra no pgAdmin o arquivo `database/migrations/006_agente_estoque.sql` e execute-o **uma única vez**.
4. Execute `database/08_verificar_instalacao.sql` e confirme que a versão 6 aparece.
5. Configure o arquivo `.env` conforme o README do projeto e abra o sistema como já era feito. Exemplo na pasta `backend` (com variáveis de ambiente corretamente carregadas):

   ```bash
   python -m gestao_lab servir
   ```

6. Entre com o perfil **Chefe de Laboratório** e use o novo menu **Agente de estoque** (rota `/agente-estoque`). Veja as projeções; clique em **Analisar estoque e registrar novas recomendações** para persistir aquelas que representam risco; aceite ou descarte na própria página.

> A inicialização agora valida as versões 1 a 6; se a migração 006 estiver faltando, o servidor avisará sobre a versão do schema. **Não** edite a migração 005 que já tenha sido aplicada.

## 5. Como obter uma recomendação para demonstração

Em um banco de testes, cadastre um item com saldo 12 L, limite 5 L e ao menos 10 dias de histórico, registrando saídas por `USO` em dias diferentes, equivalentes a 1 L por dia. Como o sistema atribui as datas atuais às movimentações, **não é possível produzir esse histórico de vários dias com cliques em uma única sessão** sem manipular uma massa de dados de teste. Para demonstrar o cálculo sem alterar o histórico auditável do banco, execute o teste isolado `test_exemplo_documento_12_menos_5_ritmo_1_por_dia`.

Para testar o fluxo completo da interface e a persistência, é necessário um banco de testes com histórico real que atenda aos parâmetros provisórios ou uma massa de integração especialmente preparada. Não retrodate nem edite movimentações auditadas em produção.

## 6. Testes realizados e pendentes

- **Aprovados nesta versão:** 143 testes de unidade/regressão sem PostgreSQL e 7 subtestes. O ambiente de preparação utilizou um substituto apenas para permitir as importações de Psycopg; isso não equivale a um teste com o banco real.
- **Verificação sintática do Python:** aprovada.
- **Ainda pendentes neste ambiente:** testes de integração do fluxo inteiro com PostgreSQL e servidor real, deduplicação concorrente e homologação com histórico real. A comparação retrospectiva com uma referência ingênua foi acrescentada, mas a avaliação usando registros reais permanece pendente.
- O ambiente de preparação não disponibilizava a biblioteca `psycopg` nem servidor PostgreSQL para validação real; por isso, não considere o código homologado para produção.

## 7. O que deve ser confirmado com a professora

1. A professora autorizou sistemas especialistas baseados em regras e estatística; validar com ela a apresentação da base de conhecimento e das métricas, sem necessidade de Machine Learning por princípio.
2. Janela histórica, frequência de análises e quantidade mínima de dados.
3. Critérios de consumo: a finalidade atual `USO` identifica corretamente consumo efetivo? Casos de correção/perda ainda não são classificados separadamente na interface atual.
4. Critério de risco (7 dias), e se o intervalo atual de monitoramento automático de 10 minutos atende à frequência desejada.
5. Metodologia de validação: MAE retrospectivo e comparação da média com referência ingênua, idealmente em dados históricos de laboratório.

A arquitetura foi desenhada para que um método mais avançado substitua apenas a política no domínio, mantendo serviço, repositório, rotas e interface com alterações mínimas.


## 8. Melhoria acadêmica e operacional — versão 2

### Base de conhecimento (regras R01–R08)

A classe `MotorInferenciaEstoque`, em `backend/gestao_lab/dominio/regras_especialistas_estoque.py`, aplica **encadeamento direto por prioridade** sobre fatos observados. A primeira regra verdadeira determina a conclusão. O catálogo abaixo é a base de conhecimento explícita:

| Regra | Quando | Resultado |
| --- | --- | --- |
| R01 | Saldo atual menor ou igual ao mínimo | `MINIMO_ATINGIDO`, RF08 permanece separado |
| R02 | Lote vencido | `INCONCLUSIVA` |
| R03 | Saída recente sem finalidade classificada | `INCONCLUSIVA` |
| R04 | Menos de 7 dias observados | `INCONCLUSIVA` |
| R05 | Consumo em menos de 3 dias distintos | `INCONCLUSIVA` |
| R06 | Consumo zero ou média não calculável | `INCONCLUSIVA` |
| R07 | Prazo estimado até o mínimo dentro de 7 dias | `REPOSICAO_SUGERIDA` |
| R08 | Prazo estimado superior a 7 dias | `NORMAL` |

**Observação:** R01 tem precedência mesmo sem histórico suficiente, pois reflete o saldo medido, não uma previsão; R03 impede que a falta de classificação seja interpretada como consumo zero. Os limites continuam provisórios.

### Comparação retrospectiva e limitações

- Treino: dias completos entre o início da observação e os 7 dias finais.
- Teste: últimos 7 dias completos, sem usar esses dias no cálculo das referências.
- **Modelo principal:** média de saída diária apenas no treino.
- **Referência simples:** consumo observado no último dia completo de treino, projetado como constante.
- **MAE:** média de `|consumo real diário − consumo previsto diário|` nos 7 dias de teste, em unidade/dia.
- Sem treino suficiente, o sistema exibe `NAO_AVALIADA` em vez de inventar uma pontuação. A classificação `ESTAVEL`/`VARIAVEL` usa um limiar heurístico sobre o MAE do modelo; **não mede probabilidade, garantia de acerto, nem acurácia futura**.

### Monitor automático e avisos

Quando `AGENTE_AUTOMATICO=1` (padrão), um monitor separado verifica os lotes ativos aproximadamente a cada **10 minutos**, com primeira execução ao iniciar o servidor. É executado somente enquanto `python -m gestao_lab servir` estiver rodando. Não há compras, baixas nem cancelamentos automáticos.

- Cada lote é analisado com filtro pelo seu laboratório, em transação própria, após bloqueio da linha do item.
- Só há gravação se a regra aplicada resultar em `REPOSICAO_SUGERIDA`.
- O banco evita recomendações pendentes duplicadas e impede reabrir uma decisão para a mesma evidência.
- **Novo registro:** mensagem na página Notificações e inclusão na fila SMTP institucional (quando configurado). **Atualização de pendência existente:** sem mensagem repetida.
- Para desativar o monitor preventivo no servidor, defina `AGENTE_AUTOMATICO=0` em `.env` e reinicie. A análise manual continua disponível, assim como alertas RF08.
- Em uma falha, o monitor registra apenas o tipo da exceção e tenta novamente mais tarde; o servidor e o monitor RF08 seguem independentes.
- Recomendações anteriores registram a evidência no momento de sua criação. Elas não são apagadas automaticamente se o saldo for reposto; o Chefe deverá revê-las. Isso é uma limitação conhecida da versão de demonstração.

**Banco:** não há migração 007 nesta versão, pois a tabela `recomendacao_estoque` e a função `gestao_lab.notificar` já estavam instaladas pelas versões anteriores. **A versão 006 continua obrigatória.**

### Roteiro de validação (Windows / VS Code)

1. **Mantenha backup** e use um PostgreSQL com schema `gestao_lab` instalado até a versão **6**. Recomenda-se validar primeiro com um banco `poodev_teste_*` ou `gestao_laboratorio_teste*`, jamais em produção.
2. Na pasta `backend`, instale `python -m pip install -r requirements.txt -r requirements-dev.txt` e carregue `.env` com `DATABASE_URL` para o banco desejado.
3. Demonstre as previsões puramente sintéticas com `python -m gestao_lab.dominio.demo_agente_estoque`. Serão apresentados 4 cenários com as conclusões esperadas. Isso **não acessa PostgreSQL**.
4. Execute `python -m pytest -q -m "not integracao and not concorrencia"` para checar cálculos, motor de regras, acesso, interface, monitor e regressão.
5. Configure `TEST_DATABASE_URL` para um banco descartável com schema 1–6 e execute `python -m pytest -q tests/test_integracao_agente_melhorias.py -m integracao`. O teste cria um item de teste e usa um sinal de risco **sintético apenas para comprovar gravação, deduplicação, aviso e decisão**; ele não pretende demonstrar precisão preditiva.
6. Suba o sistema (`python -m gestao_lab servir`). Confira o menu Agente de estoque, a área Notificações e aceite/descarte. Para medir previsão no banco real, use **histórico legítimo de consumo distribuído em dias distintos**, sem alterar a auditoria existente.

**Testes neste ambiente de preparação:** 143 testes sem banco aprovados, 7 subtestes aprovados e 87 testes de integração/concorrência não executados. A execução isolada usou um módulo substituto em memória para disponibilizar importações de Psycopg, pois o pacote PostgreSQL não estava disponível no ambiente; **a integração real está pendente e não foi simulada como aprovada**.

### Arquivos acrescidos na versão 2

- `dominio/regras_especialistas_estoque.py`: fatos, regras e motor de inferência.
- `dominio/demo_agente_estoque.py`: cenários de demonstração sintética.
- `tests/test_agente_melhorias.py`: testes da base de conhecimento, motor, MAE, notificação e monitor.
- `tests/test_integracao_agente_melhorias.py`: verificação real do fluxo de persistência para rodar no PostgreSQL de testes.

Arquivos modificados: `dominio/agente_estoque.py`, `aplicacao/agente_estoque.py`, `infraestrutura/agente_estoque_postgres.py`, `apresentacao/paginas_agente_estoque.py`, `gestao_lab/__main__.py`, `.env.example` e este guia.

### Conferência somente leitura no pgAdmin

Execute `database/09_verificar_agente_estoque.sql` para verificar se a tabela e a função de notificação existem, quantificar recomendações e avisos por laboratório, e detectar qualquer duplicidade pendente. O script não altera o banco e pode ser executado no ambiente de demonstração.
