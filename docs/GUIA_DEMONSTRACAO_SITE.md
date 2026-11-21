# PooDev — Teste do Agente de IA diretamente pelo site (V3)

## Objetivo

Esta versão adiciona um **modo de demonstração** ao painel do Agente de Estoque.
Os dados de demonstração são **100% fictícios, construídos em memória**. A tela
usa a mesma classe `AgenteEspecialistaEstoque` e a mesma base de conhecimento
`R01–R08` da aplicação normal.

**Importante:** abrir e executar os cenários simulados **não grava movimentações,
não cria recomendações ou notificações** e não muda o saldo de nenhum lote.
O monitor periódico **normal** do servidor continua independente, com seu
comportamento habitual sobre os dados reais. A autenticação pode consultar o
banco, mas os cenários não buscam estoque real.

## Instalar no projeto que já funciona

1. Guarde a versão anterior como cópia de segurança.
2. Extraia `PooDev-com-Agente-Estoque-V3-Demonstracao.zip` em outra pasta;
   se preferir, aplique somente as alterações do ZIP reduzido mantendo a mesma
   estrutura de diretórios.
3. Preserve o arquivo `.env` que você já utiliza. **Não substitua nem publique
   suas credenciais.** Copie-o para a raiz da nova versão se necessário.
4. **Não é necessária nova migração SQL.** A funcionalidade reutiliza o esquema
   da V2 (migração 006 já instalada).
5. No terminal do VS Code, abra a pasta `backend` e execute:

   ```powershell
   python -m gestao_lab servir
   ```

6. Entre no sistema como **Chefe de Laboratório**, com seu banco
   `gestao_laboratorio` configurado como antes.
7. Abra **Agente de estoque** no menu e clique em **Abrir modo de demonstração**.
   Você também pode acessar `/agente-estoque/demonstracao` no navegador,
   após autenticar-se.
8. Escolha um cenário e clique em **Executar simulação**. A página mostrará
   a regra acionada, a justificativa, o consumo considerado, a previsão e as
   movimentações fictícias que foram analisadas.

## Cenários e resultados esperados

| Cenário no site | Regra | Resultado | Previsão |
|---|---|---|---|
| Risco de reposição | R07 | REPOSICAO_SUGERIDA | 7 dias |
| Estoque confortável | R08 | NORMAL | 35 dias |
| Mínimo já atingido | R01 | MINIMO_ATINGIDO | Não calculável |
| Histórico recente | R04 | INCONCLUSIVA | Não calculável |
| Poucos dias com uso | R05 | INCONCLUSIVA | Não calculável |
| Descarte não é consumo | R07 | REPOSICAO_SUGERIDA | 7 dias |
| Saída sem finalidade | R03 | INCONCLUSIVA | Não calculável |
| Lote vencido | R02 | INCONCLUSIVA | Não calculável |

No cenário principal, o saldo fictício é 12 L, o mínimo é 5 L e foram
registradas dez saídas fictícias de 1 L em dez dias. Por isso a média é de
1 L/dia e o prazo previsto é `(12 - 5) / 1 = 7 dias`.

O cenário de descarte tem dez usos de 1 L e um descarte adicional de 5 L:
**apenas os dez litros de uso** entram no cálculo do consumo médio.

## Diferença entre a simulação e o funcionamento real

- **Simulação didática:** não lê lotes do laboratório, não persiste dados, não
  permite aceitar/descartar recomendações e não dispara notificações.
- **Análise real:** aparece em **Agente de estoque** (fora da demonstração),
  lê o histórico real do PostgreSQL e pode registrar recomendações e avisos.
- **Testes de integração:** a gravação de recomendações, as notificações, a
  revisão do Chefe e a medição de erro em histórico real ainda exigem
  validação própria no ambiente PostgreSQL.

Portanto, apresentar a simulação como se fosse uma previsão real do banco
seria incorreto. O objetivo deste modo é **demonstrar a lógica de IA de forma
reproduzível**, sem adulterar a auditoria do estoque.

## Testes automatizados

Com as dependências do projeto instaladas no seu computador:

```powershell
cd backend
python -m pytest -q tests/test_demonstracao_agente_web.py
python -m pytest -q -m "not integracao and not concorrencia"
```

Os testes novos verificam as oito conclusões, a consistência dos saldos,
a autorização por perfil, os parâmetros inválidos e a ausência de chamadas
às operações do serviço de estoque durante a simulação.

## Arquivos incluídos/alterados

- `backend/gestao_lab/dominio/cenarios_demonstracao_estoque.py` (novo):
  cria históricos fictícios e chama o motor de inferência real.
- `backend/gestao_lab/apresentacao/paginas_agente_estoque.py` (alterado):
  botão de entrada e página de simulação com evidências e resultado.
- `backend/gestao_lab/apresentacao/web.py` (alterado): rota GET autenticada.
- `backend/tests/test_demonstracao_agente_web.py` (novo): testes do modo.
- `backend/tests/test_agente_estoque.py` (ajuste de teste): fixa a data de
  referência de um teste antigo para que não mude com o calendário.

Nenhum arquivo SQL, tabela ou regra de produção foi alterado nesta versão.
