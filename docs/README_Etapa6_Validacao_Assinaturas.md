# Verificação de assinaturas digitais em protocolos

O autor assina o PDF no gov.br antes do envio. O PooDev confere as assinaturas com as autoridades configuradas e compara os nomes dos certificados com o nome do autor do protocolo. O Chefe do Laboratório confere o conteúdo e a identidade do signatário antes de confirmar a validação administrativa. Nomes iguais podem pertencer a pessoas diferentes.

## Instalação e configuração

1. Instale o suplemento com `python -m pip install -r backend/requirements-assinatura.txt`, a partir da raiz do projeto.
2. Aplique as migrações em ordem até a [004](../database/migrations/004_assinatura_pdf.sql). Ela registra a política e o SHA-256 do PDF em novos cadastros verificados. A data `assinado_em` indica quando o PooDev registrou a verificação.
3. Obtenha a cadeia oficial e confira a origem dos certificados e das listas. Mantenha esses arquivos em local controlado pelo operador. [Cadeia de certificados gov.br](https://www.gov.br/governodigital/pt-br/identidade/assinatura-eletronica/saiba-como-importar-os-certificados-do-gov-br-no-adobe-acrobat-reader)
4. Configure as variáveis no ambiente usado para iniciar a aplicação. Separe múltiplos caminhos por ponto e vírgula no Windows ou dois-pontos no Linux e macOS.

| Variável | Arquivos |
| --- | --- |
| `PDF_RAIZES_CONFIAVEIS` | Certificados-raiz confiáveis em PEM ou DER. |
| `PDF_CERTIFICADOS_INTERMEDIARIOS` | Certificados das autoridades intermediárias, que ajudam a construir a cadeia. |
| `PDF_LISTAS_REVOGACAO` | Uma lista de certificados revogados (LCR) por arquivo, em PEM ou DER. Use listas assinadas pelos emissores da cadeia e renove-as antes do vencimento. |

A validação roda offline. O pyHanko usa as LCRs configuradas e pode validar dados de revogação embutidos no PDF. A política exige evidência de revogação quando o certificado declara um ponto de distribuição de LCR ou OCSP. Sem evidência utilizável, o resultado é `INDETERMINADA`. Listas do gov.br podem ter janela de validade de poucas horas. O operador precisa renovar as listas para novos cadastros e validações.

Se o PDF contiver carimbos de tempo, o PooDev os confere com a cadeia de confiança configurada e verifica as revisões cobertas. A política confere a vigência atual da cadeia. Arquivamento criptográfico de longo prazo e atestação oficial de conformidade exigem outro fluxo. [Documentação de validação pyHanko](https://docs.pyhanko.eu/en/stable/api-docs/pyhanko.sign.validation.html) [VALIDAR do ITI](https://validar.iti.gov.br/sobre.html)

## Consulta, validação e protocolos existentes

- O PostgreSQL guarda os bytes originais em `bytea`. A evidência no banco registra o digest e o identificador da política declarada pelo backend após a verificação. A função SQL aplica as regras de persistência e deve ser chamada pelo backend ou por clientes de escrita confiáveis.
- Na consulta, a verificação atual pode ficar inconclusiva após o vencimento da cadeia ou das listas. A tela preserva a data da conferência registrada no cadastro. A validação administrativa exige uma conferência técnica atual favorável e a confirmação de identidade pelo Chefe.
- Registros criados pelo fluxo antigo preservam o PDF, o estado administrativo e os vínculos existentes. Sem evidência de verificação digital registrada, ficam impedidos de receber nova validação ou vínculo. O autor pode baixar o PDF, assinar no gov.br e enviá-lo como novo protocolo.

## Teste em homologação

Use um PDF gov.br de teste e as LCRs vigentes da cadeia. Confira o aceite, um envio sem assinatura, alteração de bytes, a mesma assinatura sem LCR exigida, signatário com nome incompatível e um protocolo legado. No aceite, confirme a identidade como Chefe, vincule um equipamento do mesmo laboratório e verifique se o download devolve exatamente os bytes enviados.
