# Etapa 7 — Operações do laboratório e notificações

- **Restrições.** O Chefe seleciona um aluno ativo e um equipamento do laboratório e informa o motivo. O banco cancela as reservas afetadas e bloqueia novos agendamentos do aluno enquanto a restrição estiver ativa. O aluno pode consultar suas restrições e pedir reativação. O Chefe aprova ou nega o pedido com resposta registrada.
- **Manutenção.** O Chefe pode marcar um equipamento como em manutenção ou danificado e posteriormente tornar o equipamento disponível. A indisponibilidade aplica as regras de bloqueio e cancelamento do banco. Cancelamentos preservam o histórico e não encerram empréstimos de chaves.
- **Ocorrências.** Usuários autenticados registram danos, faltas de estoque e outros problemas. O Chefe é notificado, acompanha as ocorrências do laboratório e pode marcá-las como resolvidas. Os demais usuários consultam os próprios registros.
- **Notificações.** Cada usuário consulta e marca como lidos os próprios avisos. Isso inclui avisos de estoque, cancelamentos de reserva, restrições, reativação e ocorrências, conforme o destinatário registrado.

## E-mail institucional

A Etapa 7 usa a fila `gestao_lab.envio_email` do esquema existente. Com `SMTP_HOST` vazio, os avisos continuam no painel e os e-mails na fila. Ao configurar o host e iniciar `gestao_lab servir`, o trabalhador pode processar inclusive os avisos históricos ainda pendentes de contas ativas.

| Variável | Configuração |
| --- | --- |
| `SMTP_HOST` | Servidor SMTP informado pela instituição. |
| `SMTP_SEGURANCA` | `starttls` ou `tls`, conforme o servidor. |
| `SMTP_PORT` | Porta do provedor. Vazia usa 587 com `starttls` ou 465 com `tls`. |
| `SMTP_REMETENTE` | Endereço individual autorizado pelo servidor. |
| `SMTP_USUARIO` e `SMTP_SENHA` | Credenciais do servidor. Deixe as duas vazias se o servidor não exigir autenticação. |

Informe as configurações no `.env` local e reinicie o Sistema para carregá-las. O conteúdo da ocorrência, o motivo de restrição e as decisões ficam no painel. A mensagem SMTP orienta o destinatário a consultar o sistema.

O envio ocorre em segundo plano. O PostgreSQL bloqueia individualmente cada envio em processamento, com até cinco tentativas e intervalos crescentes. A fila registra a última categoria de erro. O aviso interno permanece disponível. Se a conexão falhar depois da aceitação da mensagem pelo servidor e antes da confirmação no banco, pode acontecer um reenvio.

## Banco e testes

Esta etapa usa os recursos do esquema com as [migrações até a versão 4](../database/migrations/README.md). A integração de teste usa `TEST_DATABASE_URL` em PostgreSQL descartável. O transporte SMTP é simulado nos testes, com cenários de falha e reenvio, sem uso de conta institucional.
