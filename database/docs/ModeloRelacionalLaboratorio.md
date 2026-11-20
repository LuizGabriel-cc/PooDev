# Modelo relacional do banco implementado

Banco `gestao_laboratorio`, esquema `gestao_lab`, revisão de 19/11/2026, com as migrações até a versão 005. O modelo contém 27 tabelas. Os diagramas mostram cardinalidades por associação. A exclusividade entre subclasses e entre alternativas de localização é imposta por restrições e triggers. O dicionário acompanha os nomes e tipos do SQL base e das migrações.

## Usuários e laboratório

```mermaid
erDiagram
    LABORATORIO ||--o{ USUARIO : vincula
    USUARIO ||--o| ALUNO : especializa
    USUARIO ||--o| PROFESSOR : especializa
    PROFESSOR ||--o| CHEFE_LABORATORIO : especializa
    PROFESSOR ||--o{ ALUNO : orienta
    CHEFE_LABORATORIO ||--|| LABORATORIO : gerencia
    USUARIO ||--o{ SESSAO_USUARIO : autentica
    USUARIO ||--o| CHAVE_ASSINATURA_USUARIO : possui
    LABORATORIO ||--o{ CHAVE_ASSINATURA_USUARIO : delimita
```

Cada usuário deve ser Aluno **ou** Professor. Chefe é Professor. O laboratório tem exatamente um Chefe registrado. O orientador e as demais relações preservam o laboratório. `sessao_usuario` referencia um usuário e guarda validade, revogação e resumo do token. `chave_assinatura_usuario` admite uma chave RSA por usuário. Sua FK composta exige que a chave pertença ao laboratório do usuário.

## Recursos e localização

```mermaid
erDiagram
    RECURSO ||--o| SALA : especializa
    RECURSO ||--o| BANCADA : especializa
    RECURSO ||--o| EQUIPAMENTO : especializa
    SALA ||--o{ BANCADA : contem
    SALA o|--o{ EQUIPAMENTO : local_direto
    BANCADA o|--o{ EQUIPAMENTO : local_bancada
```

Cada recurso tem exatamente uma subclasse compatível com seu `tipo`. Equipamento tem exatamente um local entre `bancada_id` e `sala_direta_id`. A sala do equipamento de bancada é derivada de `bancada.sala_id`; não se duplica esse vínculo no equipamento. `complemento_local` fornece a posição exata, e `numero_patrimonio` identifica globalmente a unidade física. Todos os recursos possuem laboratório e Professor responsável na base `recurso`.

## Reservas e abrangência

```mermaid
erDiagram
    USUARIO ||--o{ RESERVA : solicita
    RECURSO ||--o{ RESERVA : principal
    RESERVA ||--|{ RESERVA_RECURSO : abrange
    RECURSO ||--o{ RESERVA_RECURSO : bloqueado
```

Uma reserva tem um recurso principal e um ou mais itens abrangidos. Cada item repete período e indicador de bloqueio para permitir o índice GiST; uma FK composta sincroniza esses valores com a reserva. Cancelamento atualiza o bloqueio por cascata de **atualização**, sem apagar histórico. O snapshot `local_registrado` preserva a posição do recurso na confirmação.

| Recurso principal | Itens materializados |
|---|---|
| Equipamento | A unidade selecionada. |
| Bancada | Bancada + todos os equipamentos vinculados. |
| Sala | Sala + todas as bancadas + equipamentos diretos e das bancadas. |

O conflito exige mesmo recurso abrangido e sobreposição dos períodos. Assim, dois microscópios da mesma bancada podem ser reservados individualmente, mas qualquer um deles impede a reserva integral da bancada e da sala no mesmo período.

## Cópias e empréstimos de chave

```mermaid
erDiagram
    SALA o|--o{ CHAVE : destino
    BANCADA o|--o{ CHAVE : destino
    CHAVE ||--o{ EMPRESTIMO_CHAVE : possui_historico
    RESERVA ||--o{ EMPRESTIMO_CHAVE : autoriza
```

Cada cópia tem exatamente um destino entre Sala e Bancada. O empréstimo possui usuário, reserva, retirada, entrega, devolução e recebimento. Um índice parcial permite no máximo um empréstimo aberto por cópia. A condição física da cópia é separada da posse: a view deriva `EM_USO`, e ocorrências registram extravio ou indisponibilidade. Cancelamento/fim de reserva preservam o empréstimo aberto.

## Protocolos e assinatura RSA

```mermaid
erDiagram
    LABORATORIO ||--o{ PROTOCOLO : compartilha
    USUARIO ||--o{ PROTOCOLO : autoria
    USUARIO ||--o| CHAVE_ASSINATURA_USUARIO : possui
    LABORATORIO ||--o{ CHAVE_ASSINATURA_USUARIO : delimita
    CHEFE_LABORATORIO o|--o{ PROTOCOLO : valida
    PROTOCOLO ||--o{ PROTOCOLO_EQUIPAMENTO : vincula
    EQUIPAMENTO ||--o{ PROTOCOLO_EQUIPAMENTO : possui
    CHEFE_LABORATORIO ||--o{ PROTOCOLO_EQUIPAMENTO : autoriza
```

A [migração 005](../migrations/005_assinatura_rsa.sql) introduz `chave_assinatura_usuario` e as evidências RSA de `protocolo`. O autor envia o PDF e assina no sistema. A aplicação calcula SHA-256 e a assinatura RSA com código próprio. O Chefe realiza a validação administrativa após a conferência da assinatura, e um protocolo validado pode ser vinculado aos equipamentos do mesmo laboratório.

O documento permanece em `pdf_original`, com os mesmos bytes enviados. A assinatura é armazenada separadamente em `assinatura_rsa`. `rsa_resumo` guarda o resumo de 32 bytes, e `rsa_modulo` e `rsa_expoente_publico` preservam a chave pública usada na assinatura. A política é `rsa-sha256-v1`, registrada em `pdf_politica_verificacao`, e `pdf_sha256` deve corresponder tanto ao resumo RSA quanto ao SHA-256 do PDF. Os protocolos anteriores conservam a evidência e a política que já possuíam, com os campos RSA nulos.

O expoente privado fica somente em `chave_assinatura_usuario`, junto do módulo e do expoente público. O servidor usa essa chave para assinar pelo autor autenticado. Os valores privados ficam fora das respostas web e da auditoria genérica, que copiaria a linha completa. A tabela revoga permissões de `PUBLIC` e bloqueia atualização, exclusão e truncamento. O acesso da aplicação e os backups devem preservar a confidencialidade dessa tabela, pois o expoente privado é persistido como texto.

O registro da assinatura exige autor habilitado no mesmo laboratório e protocolo ainda não assinado. A operação bloqueia o laboratório antes de atualizar o protocolo. Após a assinatura, os gatilhos preservam o PDF, a autoria e a evidência criptográfica. Novas validações administrativas e novos vínculos a equipamentos exigem a política `rsa-sha256-v1`. O PostgreSQL verifica os vínculos, os estados e a consistência do resumo. A aplicação verifica a operação criptográfica RSA.

## Tabelas e correspondência com os requisitos

| Tabela | Finalidade | Requisitos |
|---|---|---|
| `laboratorio` | Nome, local, Chefe, limites e antecedência de validade. | RF03, RF18 |
| `usuario` | Identidade, e-mail, hash de senha e vínculo. | RF01, RF02 |
| `professor` | Programa de pós e ramal. | RF02 |
| `aluno` | Matrícula, tipo e orientador. | RF02 |
| `chefe_laboratorio` | Especialização do Professor e chefia. | RF02, RF03 |
| `sessao_usuario` | Persistência de sessões e resumo dos tokens. | RF01, RNF01 |
| `chave_assinatura_usuario` | Chave RSA imutável por autor, com acesso privado pelo servidor. | RF09, RF10 |
| `recurso` | Base de Sala, Bancada e Equipamento, estado e responsável. | RF04, RF15 |
| `sala` | Identificação, localização e capacidade. | RF04, RF25 |
| `bancada` | Sala obrigatória e identificação dentro da sala. | RF04, RF25 |
| `equipamento` | Patrimônio único, posição exclusiva, foto e complemento. | RF04, RF25 |
| `reserva` | Dono, principal, período, confirmação e cancelamento. | RF05, RF06, RF18, RF24 |
| `reserva_recurso` | Conjunto bloqueado, período sincronizado e local histórico. | RF05, RF24, RNF13 |
| `chave` | Cópia física, destino, condição e designação. | RF21 |
| `emprestimo_chave` | Retirada/devolução, portador e responsáveis. | RF22, RF23 |
| `ocorrencia_chave` | Condição física e ocorrências de cada cópia. | RF23 |
| `item_estoque` | Nome, lote, unidade, saldo, validade e limite. | RF07, RF08 |
| `movimentacao_estoque` | Variação, saldos anterior/posterior, motivo e ator. | RF07, RF17 |
| `protocolo` | Autor, PDF original, assinatura RSA separada, evidência pública e validação. | RF09, RF10, RF12 |
| `protocolo_equipamento` | Associação de protocolo validado a equipamentos. | RF11 |
| `proibicao_aluno_equipamento` | Restrição ativa/histórica com motivo. | RF13 |
| `solicitacao_reativacao` | Justificativa, decisão e resposta do Chefe. | RF14 |
| `ocorrencia` | Relato de dano, falta de estoque ou outro problema. | RF16 |
| `notificacao` | Mensagem no sino, destinatário, leitura e deduplicação. | RF06, RF08, RF14, RF16, RF19 |
| `envio_email` | Fila, tentativas, envio, falha e reenvio. | RF19 |
| `historico_uso` | Auditoria de cadastros e operações. | RF17, RNF07 |
| `schema_versao` | Identificação da instalação do modelo. | RNF05 |

RF20/PWA usa os mesmos dados e sua implementação pertence ao frontend. RF26/agente especialista aguarda definição funcional e receberá migração específica. O quadro indica o suporte de persistência dos requisitos.

## Integridade entre laboratórios

`laboratorio_id` aparece nas bases e nas tabelas dependentes para permitir FKs compostas. Por exemplo, `(bancada_id, laboratorio_id)` referencia a bancada no mesmo laboratório, e `(orientador_usuario_id, laboratorio_id)` referencia o Professor correto. Essa repetição controlada permite ao próprio PostgreSQL rejeitar um vínculo entre laboratórios.

Os subtipos compartilham a chave da base, sem usar `INHERITS` do PostgreSQL. Tabelas abstratas são completas ao COMMIT; as verificações adiadas permitem gravar base e subtipo juntos. Não há exclusão de histórico em cascata. As FKs de reservas e empréstimos preservam os registros a que se referem.
