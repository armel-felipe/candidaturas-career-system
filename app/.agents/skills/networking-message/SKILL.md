---
name: networking-message
instruction_modules: [runtime-core, intake-fit-map]
description: >
  Gera mensagens de networking para LinkedIn de Felipe Armel, baseadas nos templates do Notion
  (página "Networking" em "Aulas e Atividades"). Use esta skill SEMPRE que o usuário pedir:
  "escreve a mensagem de networking", "mensagem para o recrutador", "mensagem para o gestor",
  "mensagem para os pares", "manda mensagem no LinkedIn", "quero me conectar com alguém dessa vaga",
  "faz a nota de conexão", "mensagem de networking para a empresa", ou qualquer variação que implique
  redigir uma mensagem de contato profissional no LinkedIn — seja para vaga específica ou para
  networking geral com empresa de interesse.
---

# Networking Message

## Governança da Skill

Manutenção canônica desta skill: `.agents/skills/networking-message/SKILL.md`.

Qualquer ajuste nesta skill deve ser feito no caminho canônico em `.agents/skills/networking-message/SKILL.md`.

## Adaptação Local OpenCode

Carregue os módulos declarados no front matter. Use `.career-state/fit_map.json` quando houver vaga analisada e referências em `../career-system/references/`. Continue perguntando o perfil do destinatário antes de gerar qualquer mensagem.

Gera mensagens de LinkedIn personalizadas para Felipe Armel, seguindo os templates do curso PRH
e adaptando com contexto real de vaga quando disponível.

---

## TEMPLATES BASE — IMPORTADOS DO NOTION

Fonte: Página "Networking" > "Aulas e Atividades" > Curso PRH: Emprego em 51 dias

```
ME INSCREVI NA VAGA - RH
Oi {Nome}! Td bm? Me inscrevi p/ a vaga {TítuloDaVaga} da sua empresa. Respondi tudo que era
preciso na plataforma. Você é responsável pela vaga? Qualquer dúvida, posso mandar mais
informações. Ficarei de olho no meu email.

ME INSCREVI NA VAGA - GESTORES
Oi {Nome}! Td bm? Me inscrevi p/ a vaga {TítuloDaVaga} da sua empresa. Respondi tudo que era
preciso na plataforma. Você é líder da vaga? Espero poder chegar na etapa de entrevista com você.
Qualquer coisa, estou à disposição.

ME INSCREVI NA VAGA - PARES
Oi {Nome}! Td bm? Me inscrevi p/ a vaga {TítuloDaVaga} da sua empresa. Sabe dizer se é uma vaga
pro seu time? Respondi tudo que era preciso na plataforma. Pode me passar o LinkedIn da responsável
pela vaga?

GOSTEI DA SUA EMPRESA - GERAL
Oi {Nome}! Tudo bem? Admiro muito {Nome-Da-Empresa} e para mim seria um sonho poder ajudar vocês
com {Resultado-Chave}. Se souber de alguma vaga de {Título-Vaga}, estarei sempre aberto a ouvir
propostas. Bom trabalho!
Muito obrigado! Eu tenho uma história muito interessante de como eu consegui aumentar o
{Indicador-Chave} de {X} para {Y}. Seria bem interessante ter a oportunidade de compartilhar
com vocês!
```

**OBS do curso:** Você pode construir mensagens já quebrando objeção também.

---

## FLUXO DE EXECUÇÃO

### Passo 1 — Identificar perfil do destinatário

**Sempre perguntar ao usuário** qual o perfil antes de gerar qualquer mensagem:

> "Qual o perfil do destinatário?"
> - RH / Recrutador
> - Gestor (futuro líder direto)
> - Par (colega do futuro time)
> - Empresa geral (sem vaga específica)

Nunca assumir o perfil com base no nome ou cargo visível na conversa. Sempre perguntar.

### Passo 2 — Identificar contexto de vaga

Verificar se há FIT_MAP ativo ou vaga analisada na conversa atual:

**Se houver FIT_MAP ou análise de vaga ativa:**
→ Usar automaticamente. Extrair: empresa, título da vaga, dor central, objeções mapeadas,
  histórias selecionadas e resultados mais relevantes para a vaga.
→ Informar ao usuário qual vaga está sendo usada como base antes de gerar.

**Se não houver FIT_MAP mas houver vagas mencionadas na conversa:**
→ Perguntar: "Uso a vaga de [empresa A] ou [empresa B] como base?"
→ Se o usuário responder "nenhuma" ou "não tem": gerar com placeholders (Passo 4-B).

**Se não houver nenhuma vaga na conversa:**
→ Perguntar: "Tem uma vaga ou empresa específica em mente, ou prefere o template com
  placeholders para preencher depois?"
→ Se sim: pedir os dados mínimos (empresa, cargo, canal de candidatura).
→ Se não: gerar com placeholders (Passo 4-B).

### Passo 3 — Identificar canal de candidatura

Quando houver vaga específica, verificar como a candidatura foi enviada:
- Por plataforma (Gupy, LinkedIn, site da empresa): manter "Respondi tudo que era preciso
  na plataforma"
- Por email: substituir por "Enviei meu currículo para o email de recrutamento"
- Ainda não candidatou: adaptar para tom de interesse ("Estou me candidatando à vaga...")

### Passo 4-A — Gerar com contexto de vaga

**Placeholders obrigatórios a preencher:**
- `{Nome}` → primeiro nome do destinatário (pedir ao usuário se não souber)
- `{TítuloDaVaga}` → título exato da vaga
- `{Nome-Da-Empresa}` → nome da empresa
- `{canal}` → ajuste conforme Passo 3

**Adaptações por perfil:**

| Perfil | Ajuste principal |
|---|---|
| RH / Recrutador | Perguntar se é responsável pela vaga; abrir para dúvidas |
| Gestor | Perguntar se é líder da vaga; sinalizar interesse na entrevista |
| Par | Perguntar se é a vaga do time; pedir contato do RH |
| Empresa geral | Substituir indicador genérico por resultado real da base |

**Enriquecimento com contexto da vaga (quando houver FIT_MAP):**

Usar os dados do FIT_MAP para personalizar — não para alongar a mensagem, mas para
torná-la mais específica e quebrar objeção quando relevante:

- Para **RH**: pode incluir 1 resultado quantitativo curto se a mensagem ainda couber
  no limite de nota de conexão (300 chars). Só incluir se couber sem forçar.
- Para **Gestor**: pode incluir referência direta à dor central da vaga em 1 frase.
  Ex: "Vi que vocês estão estruturando [área/desafio] — tenho histórico direto nisso."
- Para **Par**: manter simples — foco em descobrir se é a vaga certa.
- Para **Empresa geral**: substituir `{Resultado-Chave}` e `{Indicador-Chave}` pelos
  resultados mais relevantes da base (`palavras_chave_carreira.md` seção 15).

**Regra de tamanho:**
- Nota de conexão (antes de aceitar): máximo 300 caracteres
- Mensagem após aceitar: sem limite rígido, mas manter direto — máximo 3 frases

### Passo 4-B — Gerar com placeholders

Quando não há vaga nem empresa específica: entregar o template original com placeholders
claramente marcados para preenchimento posterior. Indicar o que cada placeholder deve conter.

### Passo 5 — Regras de tom

Seguir o tom dos templates originais do curso — informal, direto, primeira pessoa:
- Manter "Td bm?" e linguagem conversacional dos templates originais
- Nunca usar linguagem formal de email corporativo
- Nunca usar frases de coach ou autoproclamação
- Nunca inventar resultados — usar apenas o que está validado em `perfil_restricoes.md`
  e `palavras_chave_carreira.md`
- Espanhol: nunca incluir
- Inglês: só se o destinatário for de empresa com operação em inglês

---

## REGRAS CRÍTICAS — NUNCA VIOLAR

- **Sempre perguntar o perfil** antes de gerar — nunca assumir
- **Sempre verificar canal de candidatura** — "plataforma" vs "email" muda a mensagem
- **Nota de conexão: máximo 300 caracteres** — contar antes de entregar
- **Nunca inventar resultados** — usar apenas dados validados da base
- **Nunca usar P&L total** — usar alavanca operacional real
- **VivaReal CS: sempre "arquiteto da área"** — nunca "gestor de CS"
- **wehandle: sempre minúsculas** — nunca "WeHandle"
- **Números: validar contra `perfil_restricoes.md`** antes de incluir qualquer métrica
- **Não repetir a mensagem de networking já enviada** — se houver registro na conversa
  de mensagem anterior para o mesmo destinatário, perguntar antes de gerar nova versão

---

## OUTPUT VISÍVEL AO USUÁRIO

Após gerar a mensagem, exibir:

```
Mensagem gerada — [Perfil] | [Empresa] | [Canal]

Template base: [qual template do Notion foi usado]
Adaptações aplicadas:
• [adaptação 1 — ex: resultado X incluído com base na dor central da vaga]
• [adaptação 2 — ex: canal ajustado para email]
• [adaptação N]

Caracteres: [N] [✅ dentro do limite / ⚠️ acima do limite de nota de conexão]
```

Se nenhuma adaptação além do preenchimento de placeholders foi feita, exibir:
"Nenhuma adaptação além do preenchimento de placeholders — vaga não especificada."
