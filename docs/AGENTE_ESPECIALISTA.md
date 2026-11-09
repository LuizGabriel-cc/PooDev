# Definição do Agente Especialista — Sistema de Gestão de Laboratório

## 1. Objetivo

O agente especialista será um módulo de Inteligência Artificial destinado a apoiar o Chefe de Laboratório na tomada de decisões, utilizando informações de estoque e reservas para identificar possíveis problemas e apresentar recomendações explicáveis.

O agente não executará bloqueios, cancelamentos ou punições automaticamente.

## 2. Funcionalidades

### RF26 — Previsão de ruptura de estoque

- Analisar o histórico de movimentações dos itens.
- Estimar a taxa de consumo de cada produto.
- Prever quando a quantidade atingirá o limite mínimo configurado.
- Informar a data estimada e os dados utilizados.
- Gerar recomendações pendentes para o Chefe.

### RF27 — Detecção de uso anômalo

- Analisar o histórico de reservas dos recursos.
- Identificar padrões incomuns de frequência, duração, horário e cancelamentos.
- Sinalizar comportamentos atípicos sem considerar automaticamente que houve irregularidade.
- Apresentar os motivos que levaram à identificação da anomalia.

### RF29 — Revisão das recomendações

O Chefe poderá aceitar ou descartar uma recomendação. O sistema registrará a decisão, o responsável, a data e uma justificativa opcional.

## 3. Dados utilizados

| Fonte | Informações |
|---|---|
| `item_estoque` | Quantidade, limite mínimo, produto e laboratório |
| `movimentacao_estoque` | Entradas, saídas, quantidades e datas |
| `reserva` | Usuário, período, situação e cancelamentos |
| `reserva_recurso` | Recursos envolvidos nas reservas |

A análise utilizará apenas os registros do laboratório correspondente.

## 4. Estratégia de implementação

**Arquitetura:** Strategy, com a interface `AnalisadorIA` e duas implementações: `PrevisorRuptura` e `DetectorAnomalia`.

**Previsão:** inicialmente comparar uma baseline de consumo médio com um modelo de previsão baseado em dados históricos.

**Anomalias:** inicialmente comparar regras simples de identificação de comportamento atípico com o algoritmo Isolation Forest.

**Tecnologias propostas:** Python, pandas e scikit-learn.

## 5. Resultado das análises

Cada recomendação deverá conter:

- Identificador do laboratório e do item ou recurso analisado.
- Tipo da recomendação.
- Explicação do resultado e dados utilizados.
- Data da análise.
- Estado inicial `PENDENTE`.
- Decisão posterior do Chefe, quando houver.

Caso não existam dados suficientes, o agente deverá informar essa condição, sem inventar previsões.

## 6. Regras de segurança e qualidade

- RNF13: recomendações obrigatoriamente explicáveis.
- RNF14: nenhuma ação restritiva automática.
- RNF15: comparação com baselines, utilizando MAE para previsão e recall para anomalias.
- RNF16: falhas da IA não podem impedir o funcionamento do sistema principal.

## 7. Planejamento

**Etapa 5:** definição do agente especialista.

**Etapa 6:** preparação de dados, testes iniciais e primeiro protótipo.

**Etapa 7:** implementação e integração dos analisadores, recomendações e revisão pelo Chefe.

**Etapa 8:** testes de integração, avaliação dos resultados e correções.

A definição deverá ser alinhada com o professor responsável pela disciplina de Inteligência Artificial antes da implementação definitiva.

**Fora do escopo:** sugestão automática de horários ou recursos alternativos para reservas (RF28).