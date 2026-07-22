# LinkedIn, intake e pipeline de candidatura

## Princípio de segurança

O LinkedIn é uma fonte opcional. O harness só usa um navegador local no qual
você entrou normalmente. Ele não tenta resolver CAPTCHA, contornar login,
copiar cookies, ignorar limites ou automatizar candidatura. Se a extração não
for possível, cole a descrição da vaga ou registre-a manualmente no tracker.

## Importar vagas salvas

1. Abra Chrome ou Edge no Windows e entre no LinkedIn por conta própria.
2. Peça ao harness para abrir a página de vagas salvas usando automação local
   compatível com sessão persistente, como Playwright.
3. Para cada vaga encontrada, registre no Sheets: empresa, cargo, URL,
   `fonte=linkedin_salva`, localidade, data observada e `etapa=capturada`.
4. Gere `id_candidatura` sequencial. Nunca reutilize um ID.
5. Selecione uma linha pelo ID. Só então extraia o texto e salve em
   `inbox/job_descriptions/<id_candidatura>.md`.
6. Calcule um hash do texto, escreva-o em `descricao_hash`, preencha
   `descricao_arquivo` e mude a etapa para `descricao_validada`.

O fluxo deve parar se a sessão expirar, o LinkedIn solicitar CAPTCHA, a página
não estiver acessível, o texto estiver vazio ou a vaga tiver desaparecido. A
resposta correta é pedir login manual, uma nova tentativa posterior ou o texto
bruto da vaga — nunca burlar controles.

## Fluxo completo por candidatura

```text
capturada
  -> descricao_validada
  -> analisada
  -> [decisão humana: prosseguir]
  -> artefatos_em_rascunho
  -> revisao_pendente
  -> pronta_para_aplicacao
  -> [ação humana de envio] aplicada
```

`pausar` e `descartar` não apagam dados: mudam `decisao`, registram a razão em
`observacoes_humanas` ou log e mantêm a linha auditável. `encerrada` é para vaga
expirada, retirada ou abandonada conscientemente.

## Análise de aderência

O harness lê o perfil factual e a descrição persistida. Ele produz um FIT_MAP
local, contendo requisitos, evidências, lacunas, palavras-chave e recomendação.
No Sheets ele grava apenas `fit_score`, `fit_resumo`, `gaps_declarados`,
`proxima_acao`, `atualizada_em` e uma entrada em `Logs`.

O score prioriza trabalho; não é uma afirmação de que você conseguirá a vaga.
Lacunas explícitas são preferíveis a equivalências inventadas. A decisão
`prosseguir`, `pausar` ou `descartar` é exclusivamente humana.

## Materiais e revisão

Depois de `decisao=prosseguir`, o harness cria uma pasta
`outputs/<id_candidatura>/`. O CV deve usar o idioma da vaga, separar
experiências/cargos reais e citar apenas fatos do perfil. Carta, pitch e lista
de habilidades são opcionais.

Antes de `pronta_para_aplicacao`, revise:

- se cada número e alegação tem evidência no perfil;
- se palavras-chave foram usadas de forma natural, sem “keyword stuffing”;
- se as lacunas foram tratadas honestamente;
- se o arquivo indicado em `cv_arquivo` existe;
- se a vaga ainda está aberta e o prazo não passou.

O harness pode mover até `pronta_para_aplicacao`. Só você pode alterar para
`aplicada`, depois de enviar a candidatura de verdade.

## Retomada

Sempre que o harness voltar a trabalhar, ele deve localizar a candidatura pelo
ID, ler a linha do tracker, o arquivo de descrição, o perfil e a última linha
de log. Depois deve validar se os caminhos existem e informar a `proxima_acao`.
Não recomece uma vaga nem sobrescreva artefatos apenas porque a conversa mudou.
