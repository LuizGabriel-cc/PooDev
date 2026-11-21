# Protótipo do Agente Especialista de Controle Preventivo de Estoque (RF26/RF29)

**Base:** `Definicao_Agente_Controle_Estoque_PooDev.pdf`, proposta de 09/11/2026.  
**Estado:** implementação inicial **não homologada**, sujeita à validação da professora e aos testes reais com PostgreSQL.

## 1. O que foi implementado

O agente é **um sistema especialista com regras explícitas + estimativa estatística**. Ele não é um chatbot, não faz chamadas a APIs externas e não usa redes neurais. É uma opção de inteligência artificial simbólica/explicável, coerente com as opções ainda em discussão no documento.

- Acesso exclusivo ao Chefe responsável pelo laboratório.
- Análise por **item e lote**, com base na quantidade atual, no limite mínimo e no histórico do **próprio laboratório**.
- Considera **somente saídas com finalidade `USO`** como consumo efetivo. Ignora entradas e descartes. Se existem saídas legadas sem finalidade no intervalo, retorna resultado **inconclusivo**.
- Não estima consumo com histórico insuficiente, consumo zero ou lote vencido. Quando o limite já foi alcançado, informa `MINIMO_ATINGIDO` e remete aos alertas já existentes (RF08).
- Estima consumo diário médio e o prazo até o mínimo; recomenda revisão de reposição se o prazo previsto for igual ou inferior ao horizonte de alerta.
- Exibe evidências, explicação e, onde houver histórico suficiente, **MAE retrospectivo** da média de treinamento contra os últimos 7 dias completos.
- O Chefe aciona manualmente a emissão/atualização de recomendações, podendo **aceitar a avaliação** ou **descartar**. A decisão registra identidade e data; não existe compra automática.
- No banco, só existe **uma recomendação pendente por lote**. A mesma evidência de movimentação não reabre recomendação já decidida; nova movimentação permite atualizar uma pendência ou gerar uma nova recomendação quando necessário.

**Não realiza:** atualização de saldo, bloqueios, compras, IA generativa, emissão automática por agendador, classificação retroativa de movimentos sem finalidade, nem substituição dos alertas RF08. Todas as operações existentes continuam independentes do agente.

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

**Limitações:** ritmo médio constante é uma aproximação; demanda variável, sazonalidade, novos experimentos, descarte e validade podem mudar a necessidade de reposição. O MAE mede o erro histórico da média observada sobre os 7 dias anteriores, quando há dados de treinamento suficientes; não prova desempenho futuro e ainda não constitui comparação com outro método concorrente.

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

- **Aprovados neste ambiente:** 14 testes isolados novos do agente, além da regressão disponível sem PostgreSQL (101 testes aprovados no total e 7 subtestes).
- **Verificação sintática do Python:** aprovada.
- **Ainda pendentes:** execução da migração SQL em PostgreSQL 16+, testes de integração do fluxo inteiro com banco e servidor, teste da deduplicação concorrente e comparação com método alternativo de previsão.
- O ambiente de execução usado aqui não disponibilizava a biblioteca `psycopg` nem servidor PostgreSQL para a validação real da migração; por isso, não considere o código como homologado para produção.

## 7. O que deve ser confirmado com a professora

1. Se o agente baseado em regras e estatística satisfaz a definição de IA exigida, ou se é necessário adicionar um modelo de aprendizado de máquina.
2. Janela histórica, frequência de análises e quantidade mínima de dados.
3. Critérios de consumo: a finalidade atual `USO` identifica corretamente consumo efetivo? Casos de correção/perda ainda não são classificados separadamente na interface atual.
4. Critério de risco (7 dias) e se a avaliação precisa ser agendada automaticamente.
5. Metodologia de validação: comparação da média histórica com um segundo modelo e MAE em dados históricos de laboratório.

A arquitetura foi desenhada para que um método mais avançado substitua apenas a política no domínio, mantendo serviço, repositório, rotas e interface com alterações mínimas.
