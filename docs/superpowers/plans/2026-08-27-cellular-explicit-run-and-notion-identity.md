# Plano de correção — execução celular explícita e identidade Notion

Plano: `2026-08-27-cellular-explicit-run-and-notion-identity` — concluído em
2026-08-27.

## Diagnóstico confirmado

- `vagas_bot_01`: a run `run_3a2abf1f4ff64bd1b359c2b6636a34d3` está `running`, com
  `normalize_job` validado e `analyze_fit` pronto. O comando
  `applications:run` só executa nós determinísticos e devolve “ready”; não há
  caminho explícito para disparar o agente do nó externo.
- `vagas_bot_02`: a run `run_869307acaded4d6aaf1bee493b41d618` está bloqueada em
  `review_cv` por qualidade ATS real e em `sync_notion_initial` porque o
  application ID local foi gravado como `notion_page_id`. São bloqueios
  independentes: o primeiro exige evidência no CV; o segundo é defeito de
  roteamento/identidade.
- Os processos Hermes efetivos dos dois containers rodam como UID 10000; root
  é apenas o supervisor s6. A verificação de permissões do estado montado e do
  banco canônico passa, portanto não será feita uma correção indiscriminada de
  ownership.

## Itens do roadmap

- `CELLULAR-005`: execução explícita de agente e descoberta segura de runs
  locais.
- `NOTION-001`: validação de aliases Notion e criação inicial sem target falso.
- `CV-012`: materialização de keywords de planejamento/S&OP somente quando
  suportada pelas fontes canônicas do candidato.

## Implementação

1. Escrever testes regressivos antes da implementação para:
   - diferenciar `applications:run` determinístico de
     `applications:run --run-agent`;
   - carregar a aplicação exclusivamente do diretório escopado quando o bot
     retoma uma run local;
   - fazer o heartbeat encontrar uma run local com nó externo pronto;
   - preservar a identidade LinkedIn e não converter o application ID em
     página Notion;
   - ignorar aliases inválidos no sync inicial e usar create.
2. Implementar o executor explícito, atualizar o payload `next_action` e fazer
   o supervisor Hermes incluir `--run-agent` nas retomadas que exigem agente.
3. Integrar runs locais elegíveis na seleção celular sem reabrir runs
   bloqueadas nem criar novas runs duplicadas.
4. Validar UUID/record ID no alvo Notion, preservar `identity.json` existente e
   impedir update final sem receipt válido.
5. Completar a tabela de cláusulas ATS em inglês para o conjunto de
   planejamento/S&OP que aparece nas fontes canônicas, sem criar equivalentes
   para `SIOP` ou outros termos sem evidência explícita.
6. Rodar testes focados, validação estrutural e verifier estrito; confirmar
   que os dois containers continuam UID 10000 e que o código montado é o
   código corrigido.
7. Executar `processe-a-vaga` nos dois casos atuais, usando os
   mesmos `application_id` e `run_id`. Bloqueios de conteúdo do CV ou de
   credencial externa serão reportados como tais, sem editar artefatos ou
   relaxar gates.

## Critério de saída

Uma retomada via Telegram consegue executar o nó `analyze_fit` quando ele está
pronto; uma run local não depende de aparecer na fila Notion; nenhum alias
sintético causa update inválido; e as duas candidaturas avançam até o limite
real de seus gates, com evidência persistida. Essa prova foi executada: bot01
alcançou o agente e bot02 alcançou o review objetivo após criar o receipt
Notion.
