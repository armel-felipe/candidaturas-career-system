---
name: self-email-draft
description: >
  Prepara drafts no Gmail usando a conta ja autenticada como remetente, sem perguntar email de
  envio/remetente, para o destinatario informado no prompt, incluindo emails de candidatura
  adaptados aos templates Multinacional ou Startup, com assunto, corpo revisado e anexos opcionais.
  Use esta skill sempre que o usuario pedir para "enviar para", "encaminhar por email", "deixar
  em draft", "rascunhar um email", "email de candidatura", "email para recrutador", "mandar
  curriculo por email", ou qualquer variacao em que exista um destinatario e o envio possa
  permanecer como rascunho.
---

# Self Email Draft

## Governanca da Skill

Manutencao canonica desta skill: `.opencode/skills/self-email-draft/SKILL.md`.

Qualquer ajuste nesta skill deve ser feito no caminho canonico acima.

## Objetivo

Preparar um email para o destinatario informado no prompt.
Criar um rascunho no Gmail usando os scripts locais oficiais do projeto sempre que a autenticacao
ja estiver configurada; caso contrario, orientar a inicializacao da autenticacao e nao afirmar que
o draft foi salvo.

O remetente e sempre a conta Gmail autenticada pelo OAuth local. Nao perguntar o email de envio,
nao pedir senha de Gmail e nao tentar preencher `From`.

Quando o pedido envolver candidatura, recrutador, envio de curriculo ou vaga, escrever o email
usando um dos dois templates de candidatura abaixo, adaptando os campos ao contexto real da vaga
e aos dados validados de Felipe.

## Fluxo de Execucao

### Passo 1 - Confirmar dados minimos

Extrair do prompt:
- endereco de email do destinatario
- objetivo do email
- arquivo(s) a anexar, se o usuario pedir anexo

Se o endereco do destinatario nao estiver no prompt, perguntar apenas: "Para qual email devo
preparar o draft?"

Nao perguntar qual email deve ser usado como remetente; o script usa `userId="me"` e cria o
rascunho na conta Gmail autenticada.

Se o usuario pedir anexo sem indicar qual arquivo usar, perguntar apenas qual arquivo deve ser anexado.

### Passo 2 - Validar anexos solicitados

Quando houver anexo:
- confirmar o caminho real do arquivo mencionado
- verificar que o arquivo existe antes de afirmar que sera anexado
- nao inventar anexos, nomes de arquivo ou localizacoes
- se o arquivo nao existir, informar o bloqueio e pedir o caminho correto

### Passo 3 - Redigir o email

Produzir:
- destinatario
- assunto curto e especifico
- corpo direto, natural e coerente com o pedido
- lista de anexos confirmados, quando houver

Adaptar o tom ao pedido:
- neutro e objetivo por padrao
- mais informal se o usuario escrever de forma casual
- mais profissional se o conteudo pedir contexto de trabalho

### Passo 3-A - Redigir email de candidatura

Acionar esta etapa quando o pedido mencionar candidatura, curriculo, vaga, recrutador, gestor,
"me candidatar", "mandar CV" ou "email para empresa".

Antes de redigir:
- ler `../career-system/SKILL.md`
- ler `../career-system/references/perfil_restricoes.md` para dados fixos de contato e restricoes
- usar `.career-state/fit_map.json` quando houver FIT_MAP ativo da vaga
- se nao houver FIT_MAP nem texto de vaga, usar placeholders para dados nao informados

Escolher o template:
- `MULTINACIONAL`: empresas grandes, globais, corporativas, bancos, industrias, consultorias,
  empresas com tom formal ou quando o usuario pedir tom formal.
- `STARTUP`: startups, scale-ups, empresas em construcao, tecnologia, early-stage, ambientes
  mais diretos ou quando o usuario pedir tom informal.
- Se o tipo de empresa nao estiver claro, perguntar apenas: "Uso o template Multinacional ou Startup?"

Preencher os campos:
- `{TITULO-VAGA}`: titulo da vaga em caixa alta no assunto.
- `{Titulo-Vaga}`: titulo da vaga em capitalizacao natural no corpo.
- `{Nome-Completo}`: `Felipe Armel Dias da Silva`, salvo se o usuario pedir outra assinatura.
- `{Nome-Sobrenome}`: `Felipe Armel`.
- `{Nome}`: primeiro nome do destinatario; se nao houver, usar "equipe da {Nome-Da-Empresa}".
- `{Area-Chave}`: area central aderente a vaga. Preferir FIT_MAP; se nao houver, usar placeholder.
- `{Experiencia-Chave}`: experiencia mais aderente e defensavel. Preferir FIT_MAP ou
  `palavras_chave_carreira.md`; se nao houver, usar placeholder.
- `{Resultado-Chave}`: resultado quantitativo validado em `perfil_restricoes.md` e aderente a vaga.
- `{Caracteristica-Chave}`: caracteristica real da empresa quando fornecida; se nao houver, usar
  placeholder.
- `{Nome-Da-Empresa}`: nome da empresa; se nao houver, usar placeholder.

Usar estes contatos fixos, sem copiar os exemplos de Pedro:
- LinkedIn: `https://linkedin.com/in/felipearmel`
- WhatsApp/Tel: `(11) 98674-8218`
- E-mail: `armelfelipe@gmail.com`

#### Template MULTINACIONAL

```text
ASS: VAGA {TITULO-VAGA} - {Nome-Completo}

Prezado {Nome}, bom dia! Como vai?

Sou {Nome-Sobrenome} e tenho mais de 25 anos de experiência na área de {Area-Chave}. Na {Experiencia-Chave}, por exemplo, eu consegui {Resultado-Chave}. Busco oportunidades em uma empresa que {Caracteristica-Chave} e percebi que na {Nome-Da-Empresa} eu encontraria isso.

Gostaria de me candidatar à vaga de {Titulo-Vaga} para que eu possa fazer {Resultado-Chave}.

Deixo em anexo o meu currículo e os meus contatos.

Atenciosamente,

{Nome-Sobrenome}

https://linkedin.com/in/felipearmel

(11) 98674-8218

armelfelipe@gmail.com
```

#### Template STARTUP

```text
ASS: VAGA {TITULO-VAGA} - {Nome-Completo}

Olá {Nome}! Tudo bem?

Sou {Nome-Sobrenome} e tenho mais de 25 anos de experiência na área de {Area-Chave}. Na {Experiencia-Chave}, por exemplo, eu consegui {Resultado-Chave}. Busco oportunidades em uma empresa que {Caracteristica-Chave} e percebi que na {Nome-Da-Empresa} eu encontraria isso.

Quero me candidatar à vaga de {Titulo-Vaga} para fazer {Resultado-Chave}.

Estou compartilhando com você o meu currículo e os meus contatos.

Um abraço,

{Nome-Sobrenome}

https://linkedin.com/in/felipearmel

(11) 98674-8218

armelfelipe@gmail.com
```

Regras de adaptacao:
- Manter a estrutura dos templates, mas adaptar a frase de experiencia e resultado para soar natural.
- Evitar repetir o mesmo `{Resultado-Chave}` duas vezes de forma robotica; se necessario, na segunda
  ocorrencia transformar em contribuicao equivalente.
- Nao inventar caracteristicas da empresa, resultados, anos, certificacoes ou responsabilidades.
- Se faltar informacao essencial, deixar placeholder claro em vez de completar por suposicao.
- Anexar o CV solicitado quando houver caminho de arquivo; se o pedido mencionar curriculo sem caminho,
  perguntar qual arquivo deve ser anexado.

### Passo 3-B - Revisao ortografica e linguagem final

Antes de exibir o preview ao usuario, revisar o assunto e o corpo do email:
- corrigir acentuacao, ortografia, crase, concordancia e pontuacao em portugues do Brasil
- transformar termos internos ou canonicos em linguagem natural de email
- nao vazar chaves, nomes de campo, categorias tecnicas ou sinonimos canonicos do FIT_MAP
- manter nomes proprios, empresas, cargos, ferramentas e metricas exatamente como validados
- preservar o tom do template escolhido, sem linguagem de coach ou frases de efeito
- garantir que o corpo final esteja pronto para ser enviado por uma pessoa real

Executar a revisao objetiva antes do preview e antes do draft real:

```bash
python scripts/review_email_text.py --subject "<assunto>" --body "<corpo>"
```

Se o corpo estiver em arquivo:

```bash
python scripts/review_email_text.py --subject "<assunto>" --body-file "<arquivo_corpo.txt>"
```

Se o script falhar, corrigir o texto e repetir. Nao exibir como aprovado, nem criar draft real,
enquanto `review_email_text.py` nao passar.

### Passo 3-C - Gate obrigatorio de aprovacao textual

Antes de criar qualquer draft real no Gmail:
- exibir ao usuario destino, assunto, corpo completo ja revisado e anexos validados
- informar que nenhum draft foi criado ainda
- pedir aprovacao explicita para criar o draft
- aceitar apenas respostas inequivocas como "aprovado", "pode criar", "gera o draft",
  "crie o draft", "sim, pode gerar" ou equivalente

Se o usuario pedir ajustes:
- revisar o assunto/corpo/anexos
- exibir nova versao completa
- pedir aprovacao novamente

Nao executar `scripts/create_gmail_draft.py` sem `--dry-run` antes dessa aprovacao explicita.

### Passo 4 - Criar draft com a integracao local do Gmail

Usar os scripts locais do projeto:

```bash
npm run gmail:auth
```

Esse comando prepara a autorizacao OAuth local usando as variaveis definidas em `.env`
e salva o token em `.secrets/gmail/token.json` por padrao.

Configuracao esperada no `.env`:

```env
GMAIL_OAUTH_CLIENT_ID=
GMAIL_OAUTH_CLIENT_SECRET=
GMAIL_OAUTH_AUTH_URI=https://accounts.google.com/o/oauth2/auth
GMAIL_OAUTH_TOKEN_URI=https://oauth2.googleapis.com/token
GMAIL_OAUTH_REDIRECT_URI=http://localhost:8080/
GMAIL_OAUTH_LOCAL_PORT=8080
GMAIL_TOKEN_PATH=.secrets/gmail/token.json
```

No Google Cloud, o OAuth Client deve ser do tipo Desktop app. Se for Web application, a
Authorized redirect URI precisa bater exatamente com `GMAIL_OAUTH_REDIRECT_URI`.

Depois criar o draft:

```bash
python scripts/create_gmail_draft.py --to "<email>" --subject "<assunto>" --body "<corpo>"
```

O remetente nao e parametro do comando; a Gmail API usa a conta autenticada.

Quando houver anexo, repetir `--attach` para cada arquivo:

```bash
python scripts/create_gmail_draft.py --to "<email>" --subject "<assunto>" --body "<corpo>" --attach "<arquivo>"
```

Antes de chamar a API, usar `--dry-run` quando precisar validar corpo e anexos sem criar draft:

```bash
python scripts/create_gmail_draft.py --to "<email>" --subject "<assunto>" --body "<corpo>" --attach "<arquivo>" --dry-run
```

Depois do preview aprovado pelo usuario, executar o mesmo comando sem `--dry-run` para criar o
rascunho real.

Se a autenticacao ainda nao tiver sido feita:
- informar que falta executar `npm run gmail:auth`
- informar que `.env` precisa conter `GMAIL_OAUTH_CLIENT_ID` e `GMAIL_OAUTH_CLIENT_SECRET`
- entregar o email pronto e marcar o status como `rascunho preparado, autenticacao Gmail pendente`

Quando a autenticacao existir:
- criar apenas um rascunho
- nunca enviar automaticamente
- so disparar o envio se o usuario pedir isso de forma explicita em uma etapa posterior
- anexar apenas arquivos previamente validados

### Passo 5 - Responder com status operacional

Ao concluir, exibir:

```text
Email preparado
Destino: <email>
Assunto: <assunto>
Anexos: <lista ou "nenhum">
Status: <draft criado / rascunho preparado, autenticacao Gmail pendente>
```

Depois mostrar o corpo completo do email.

## Regras Criticas

- Nunca enviar automaticamente por padrao.
- Nunca criar draft real antes de exibir preview completo e receber aprovacao explicita do usuario.
- Nunca afirmar que um draft foi criado sem sucesso real de `scripts/create_gmail_draft.py`.
- Nunca perguntar email de envio/remetente; usar a conta Gmail autenticada.
- Nunca assumir o endereco de email destinatario se ele nao estiver no pedido.
- Nunca entregar corpo de email com termos internos, chaves canonicas, labels de FIT_MAP ou texto sem revisao ortografica.
- Nunca pular `scripts/review_email_text.py` antes do preview e antes do draft real.
- Nunca prometer anexo que nao foi localizado.
- Quando houver mais de um anexo, listar todos de forma explicita.
- Se o usuario pedir apenas o envio de um arquivo sem texto adicional, usar um corpo curto e funcional.

## Execucao Multiagente

Quando acionada pelo maestro, esta skill deve operar como `email-agent`.

Entrada obrigatoria:
- ler primeiro `.career-state/agent_requests/email-draft_request.json` ou `.career-state/agent_requests/email-draft_request.md`
- usar somente anexos existentes e comandos permitidos no request

Saida obrigatoria:
- gerar preview completo de destino, assunto, corpo e anexos
- rodar `python3 scripts/review_email_text.py --subject "<assunto>" --body "<corpo>"`
- criar draft real somente apos aprovacao explicita do usuario

Proibido neste modo:
- enviar email automaticamente
- perguntar email remetente
- criar draft real sem preview aprovado
- criar scripts temporarios na raiz

## Exemplos de Gatilho

- "encaminhe esse PDF para felipe@example.com"
- "deixa um draft para eu me enviar esse curriculo"
- "envia para recrutador@empresa.com com o arquivo outputs/cv.docx anexado"
- "rascunha um email de candidatura para talentos@empresa.com com o relatorio em anexo"
