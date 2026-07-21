---
name: output-reviewer
description: >
  Revisora automática de qualidade para todos os documentos de candidatura de Felipe Armel — CV, carta de apresentação, FERAS/pitch e resumo Gupy. Roda obrigatoriamente ao final de cada skill de produção (cv-generator, cover-letter, feras-pitch, gupy-optimizer), ANTES do entrega local em outputs/. Nunca entrega o documento ao usuário sem aprovação desta revisão. Acionar também quando o usuário pedir "revisa o CV", "confere a carta", "está bom?", "revisa antes de entregar" ou qualquer variação que implique verificação de qualidade de um documento já gerado.
---

# Output Reviewer

## Governança da Skill

Manutenção canônica desta skill: `.agents/skills/output-reviewer/SKILL.md`.

Qualquer ajuste nesta skill deve ser feito no caminho canônico em `.agents/skills/output-reviewer/SKILL.md`.

## Adaptação Local OpenCode

Leia também `../career-system/SKILL.md`. Use referências em `../career-system/references/`, FIT_MAP em `.career-state/fit_map.json` e substitua `entrega local em outputs/` por entrega local em `outputs/` ou resposta direta na conversa. Esta skill continua sendo o gate obrigatório antes de qualquer entrega.

Quando a candidatura vier do orquestrador automático ou manual por etapa:
- esta skill atua como gate local e determinístico;
- o agente não deve assumir a responsabilidade primária por rodar reviewer/polish;
- blockers desta skill devem alimentar `repair_request.json/md`, e não reiniciar o pipeline inteiro.
- quando o blocker for ATS top 8, o `repair_request` deve listar explicitamente as keywords críticas ausentes, a experiência-alvo e a ação esperada de reparo no `cv_content.json`.

Revisora automática de qualidade. Roda após cada skill de produção e bloqueia a entrega quando houver blockers objetivos. Warnings devem ser reportados, mas não bloqueiam entrega sozinhos.

**Nunca entregar o documento ao usuário sem aprovação desta revisão.**

Para CV em PT-BR, esta skill também é a camada final obrigatória de polimento textual. O polimento deve acontecer mesmo quando `pt_cv_keyword_shotgun_control` não disparar: o gate automático prova que o documento pode ser entregue; o polimento prova que ele deve ser entregue.

---

## QUANDO RODAR

Obrigatoriamente após:
- `cv-generator` — antes do `entrega local em outputs/` do CV
- `cover-letter` — antes do `entrega local em outputs/` da carta
- `feras-pitch` — antes de exibir o pitch na conversa
- `gupy-optimizer` — antes de exibir resumo e habilidades

Também quando acionada manualmente pelo usuário.

---

## CLASSIFICAÇÃO DE CRITÉRIOS

### Blockers — qualquer falha bloqueia entrega

**Datas e períodos (quando CV — blocker):**
- [ ] Toda data de início e fim foi extraída de `autoconhecimento.md` no Passo 0 — nenhuma data veio de memória, estimativa ou sessão anterior
- [ ] Nenhuma data foi interpolada, consolidada arbitrariamente ou herdada de um CV anterior
- [ ] A ordem cronológica inversa das experiências é consistente com as datas declaradas no documento (não com a ordem "esperada" pelo posicionamento da vaga)
- [ ] Nenhuma experiência, cargo, promoção, fase ou escopo foi consolidado em bloco único; títulos compostos como "Head e Diretor" ou "S&OP | Expedição | Supply Chain" bloqueiam entrega
- [ ] Nenhum período sobreposto entre experiências diferentes sem justificativa explícita do usuário

**Keywords-habilidade ATS (quando CV — blocker ou warning conforme política ATS):**
- [ ] As 8 keywords de maior prioridade do `keywords_habilidade_ats` (FIT_MAP) têm cobertura real no CV como `covered_cv`/`covered_similar_cv`, ou estão classificadas como `declared_gap`
- [ ] Para cada keyword encontrada: registrar em qual experiência e qual bullet aparece
- [ ] Para cada keyword ausente sem explicação (`missing_unexplained`): sinalizar e **bloquear entrega** até correção ou justificativa explícita do usuário
- [ ] Para cada keyword top 8 ausente sem explicação: registrar no pedido de reparo qual experiência defensável deve absorver a cobertura ou, se não houver sustentação real, marcar como gap declarado
- [ ] Nenhuma keyword foi inserida de forma forçada que distorça o fato ou resultado do bullet — a evidência real deve suportar o termo
- [ ] A stack técnica do CV contém apenas ferramentas relevantes para a vaga (sem inflação por keywords)
- [ ] Em CV PT-BR, a prosa não soa como lista metralhada de keywords em inglês; naturalidade humana prevalece sobre matching literal quando houver conflito — falha neste item bloqueia entrega

**Números e fatos:**
- [ ] Todo número está validado contra `perfil_restricoes.md` seção NÚMEROS CRÍTICOS
- [ ] Nenhum número foi inventado, arredondado ou alterado
- [ ] Nenhuma experiência, ferramenta ou certificação inexistente na base
- [ ] Todo fato específico do resumo executivo está endossado por pelo menos uma experiência visível no CV; resumo com número, POP, budget, saving, cidade, KPI ou claim factual sem suporte nas experiências bloqueia entrega

**Narrativas protegidas:**
- [ ] VivaReal CS: "responsável pelo desenho" ou "arquiteto" — nunca "gestor de CS"
- [ ] Fill rate: atribuído à Trifil — nunca à VivaReal
- [ ] WeHandle margem bruta: exatamente 15% — nunca outro valor
- [ ] WeHandle custo por atendimento: R$4,14 → R$3,61 (−13%) — nunca outro valor
- [ ] iFood saving: R$70MM/ano — nunca outro valor
- [ ] iFood budget: R$300MM/ano — nunca outro valor
- [ ] P&L total: nunca afirmado — sempre alavanca operacional real (custo logístico, margem, OPEX)
- [ ] Espanhol: ausente em todo o documento
- [ ] Inglês: "Avançado" — nunca "Fluente"
- [ ] BSP em português: "MBA Corporate Strategy — BSP Business School São Paulo"
- [ ] BSP em inglês: "Specialization Certificate in Corporate Strategies — BSP Business School São Paulo"
- [ ] Em CV `_en`, os títulos de cargo das experiências também estão em inglês visível; não aprovar `_en` com headings como `Head de Operações`, `Diretor de Operações` ou `Coordenador de S&OP`

**Tom — regra central:**
- [ ] Nenhuma frase de efeito ou autoproclamação ("sou o que transforma", "conecto planejamento, execução e resultado")
- [ ] Nenhuma linguagem de coach ("minha paixão por", "me impulsiona a", "estou ansioso para", "acredito que posso fazer a diferença")
- [ ] Nenhum formulário de RH ("Espero que estejam bem", "Obrigado pela consideração")
- [ ] Nenhuma justificativa no lugar de evidência — especialmente no movimento iFood → wehandle

**Justificativa vs evidência — wehandle:**
- [ ] O movimento iFood → wehandle não é explicado por motivação ("escolha consciente", "autonomia", "impacto percentual maior")
- [ ] A experiência wehandle é apresentada pelos fatos: o que foi feito, com quantas pessoas, qual resultado

**Bullets de CV (quando aplicável):**
- [ ] O CV traz entre 4 e 8 experiências, salvo pedido explícito do usuário em sentido contrário
- [ ] A redução de quantidade, quando houver, foi feita por seleção/corte de experiências separadas, nunca por junção de cargos
- [ ] Se o usuário não pediu modo expandido, bullet points ou quantidade de bullets, o CV está no modo conciso com exatamente 3 bullets por experiência
- [ ] Se o modo expandido foi usado por inferência do agente, há confirmação explícita do usuário registrada antes da geração
- [ ] Modo conciso: cada experiência tem exatamente 3 bullets no padrão escopo / alavanca de reposicionamento / resultado
- [ ] Modo conciso: bullet 2 começa com verbo de ação, explica como o resultado aconteceu e ajuda no reposicionamento para a vaga
- [ ] Modo conciso: bullet 2 não é lista solta de stack, não repete escopo do bullet 1 e não usa verbo genérico sem mecanismo concreto
- [ ] Modo conciso: bullet "Consegui" traz número defensável e resultado mais relevante
- [ ] Modo expandido: cada experiência tem 1 bullet de síntese da história e os demais bullets são entregas específicas
- [ ] Modo expandido: quantidade de bullets por experiência respeita o número pedido pelo usuário
- [ ] Modo expandido: entregas estão ordenadas por aderência à vaga e cobrem keywords/competências críticas do FIT_MAP
- [ ] Nenhum bullet é genérico; todos devem provar competência, entrega, número ou mitigação de objeção

**FERAS / Pitch oral (quando aplicável):**
- [ ] A entrega contém duas camadas distintas: `FERAS estruturado` e `Pitch fluido para fala/leitura`
- [ ] O pitch fluido não exibe rótulos `F/E/R/A/S`, barras ou costura mecânica entre blocos
- [ ] O pitch fluido soa como fala natural em primeira pessoa, com transições reais entre formação, trajetória, resultado, aderência e motivação
- [ ] O texto incorpora naturalmente de 3 a 5 keywords de maior valor do FIT_MAP, priorizando requisitos críticos da vaga
- [ ] A entrega traz um bloco explícito de `Keywords incorporadas naturalmente`
- [ ] A entrega traz um bloco explícito de `Keywords relevantes não usadas` com justificativa breve

**Cabeçalho do CV (quando aplicável):**
- [ ] Não centralizado
- [ ] Sem emojis
- [ ] Um dado por linha
- [ ] Sem `<hr>` como separador

---

### Warnings / Menor Peso — não bloqueiam entrega sozinhos

- [ ] Keywords do FIT_MAP aparecem naturalmente no texto (sem sinônimo forçado)
- [ ] Em FERAS/pitch oral, a cobertura de keywords é explicada sem transformar o texto em keyword stuffing
- [ ] Em FERAS/pitch oral, a versão fluida mantém cadência de fala e evita excesso de densidade em uma única frase
- [ ] Em CV PT-BR, não há excesso leve de keywords-habilidade em inglês com duas ou mais palavras espalhadas pelo resumo e experiências
- [ ] Ordem dos resultados no bullet "Consegui" prioriza o mais relevante para a vaga
- [ ] Bullet 2 cria ponte causal visível para o bullet 3, em vez de soar como iniciativa avulsa
- [ ] Espaçamento e formatação HTML dentro do padrão da skill cv-generator
- [ ] Resumo do CV dentro do limite de caracteres autorizado
- [ ] Stack técnica filtrada para ferramentas relevantes à vaga (sem listar toda a stack)
- [ ] Formação em ordem cronológica inversa
- [ ] Cobertura de ativos obrigatórios: budget, saving, escala, criação de área, interface C-level (quando existirem e forem relevantes)

---

## FLUXO DE EXECUÇÃO

### Passo 0 — Executar o gate objetivo antes de qualquer aprovação

Quando o documento revisado for um CV em DOCX, executar obrigatoriamente:

```bash
python scripts/review_output.py --kind cv --artifact outputs/<cv_final>.docx --fit-map .career-state/fit_map.json --registry .career-state/derived/keyword_ats_registry.json --report outputs/_tmp/output_review_report.json
```

Gate local/diagnóstico:

```bash
npm run cv:approve -- --artifact outputs/<cv_final>.docx
```

Quando o documento revisado for um CV final e a entrega OneDrive/rclone estiver configurada, o encerramento correto do pipeline é:

```bash
npm run cv:deliver -- --artifact outputs/<cv_final>.docx
```

Regras:
- o arquivo em `--artifact` deve ser o artefato final em `outputs/`, nunca o intermediário de `outputs/_tmp/`
- o gate objetivo deve rodar depois da validação técnica do DOCX final e depois do `register_keywords.py --cv` usando o arquivo final
- se `cv:approve` ou `cv:deliver` retornar erro, `Approved for delivery: no`, `approved_for_delivery=false`, ou listar blockers, a revisão está reprovada e a entrega fica bloqueada
- se `cv:deliver` falhar apenas por rclone/OneDrive depois de aprovação local confirmada, declarar execução parcial: arquivo local aprovado em `outputs/`, entrega remota bloqueada
- aprovação manual nunca substitui este comando
- em CV PT-BR, equivalentes canônicos em `.agents/skills/career-system/references/keyword_translation_registry.json` contam como cobertura aceitável das top 8 keywords
- o arquivo canônico é `.career-state/derived/keyword_translation_candidates.json`: ele mostra, a partir do histórico real de candidaturas, quais keywords em inglês mais frequentemente pedem tradução ou wording alternativo em PT-BR

Política ATS para CV:
- Top 8 keywords: `covered_exact=1,0`, `covered_similar=0,8`, `declared_gap=0`, `missing_unexplained=0`
- ótimo: score >= 6,2/8
- mínimo aprovável: score >= 5,2/8 e zero `missing_unexplained`
- bloqueio: score < 5,2/8 ou qualquer keyword top 8 com `missing_unexplained`
- `declared_gap` não bloqueia; aparece como warning/limite explícito
- Top 15 abaixo de 9,0/15 gera warning, não blocker
- `pt_cv_keyword_shotgun_control` gera blocker em CV PT-BR quando o gate detectar cluster artificial de keywords em inglês. Exemplos bloqueadores: duas ou mais multiword keywords na mesma frase, termo inglês enxertado em sintaxe portuguesa ruim, mais de 6 keywords multiword únicas em inglês na prosa, ou existência de equivalente PT-BR canônico ignorado sem necessidade.

O relatório JSON gerado é a evidência mínima para:
- existência do artefato final
- validação do DOCX final
- existência da aplicação correta no registry
- `cv_path` do registry apontando para o artefato final
- cobertura das 8 keywords prioritárias do FIT_MAP por `covered_cv` ou `covered_similar_cv`
- contagem objetiva de blockers e warnings

### Passo 1 — Ler o documento gerado
Ler o output completo da skill de produção antes de iniciar qualquer avaliação.

### Passo 2 — Polimento textual obrigatório para CV PT-BR

Quando o artefato revisado for CV em português, executar uma revisão editorial completa do texto visível, mesmo que o gate objetivo tenha retornado `Approved for delivery: yes`.

Objetivo do polimento:
- preservar fatos, números, cargos, datas, ferramentas e certificações;
- preservar cobertura ATS das top 8 por termos exatos naturais ou equivalentes PT-BR canônicos;
- trocar keywords em inglês que soem artificiais por português executivo natural;
- melhorar fluidez, cadência e especificidade dos bullets;
- remover formulações com cara de robô, lista de keywords ou tradução literal;
- manter o tom factual, direto e executivo.

Checklist de polimento obrigatório:
- [ ] Resumo lido como parágrafo humano, sem concentração de keywords cruas.
- [ ] Todo fato do resumo reaparece com suporte claro nas experiências; o resumo não carrega provas “exclusivas”.
- [ ] Cada bullet prova escopo, ação, método ou resultado; nenhum bullet existe só para encaixar keyword.
- [ ] Termos em inglês permanecem apenas quando forem naturais no mercado brasileiro (`SQL`, `Python`, `S&OP`, `pricing`, `pipeline`, `stakeholders`, `growth`, nomes de ferramentas).
- [ ] Termos como `data-driven decision making`, `cross-functional leadership`, `operational excellence`, `decision automation`, `process governance`, `experimentation` e equivalentes não aparecem crus quando houver wording PT-BR defensável.
- [ ] Se uma keyword top 8 depender de tradução, o equivalente usado está em `keyword_translation_registry.json`; se não estiver, adicionar o equivalente canônico antes de aprovar.
- [ ] Nenhum número, experiência ou ferramenta foi adicionado para melhorar frase ou ATS.

Se o polimento alterar o texto do CV:
→ regenerar o DOCX final em `outputs/`
→ rodar `python scripts/register_keywords.py --fit-map .career-state/fit_map.json --cv outputs/<cv_final>.docx --translation-registry .agents/skills/career-system/references/keyword_translation_registry.json`
→ rodar novamente `python scripts/review_output.py --kind cv --artifact outputs/<cv_final>.docx --fit-map .career-state/fit_map.json --registry .career-state/derived/keyword_ats_registry.json --report outputs/_tmp/output_review_report.json`
→ repetir até `approved_for_delivery=true`, zero blockers, e texto humano.

Quando o gate reprovar top 8 por `missing_unexplained` em CV PT-BR:
→ primeiro verificar se o texto já contém um equivalente português defensável;
→ se contiver, adicionar ou corrigir a entrada correspondente em `keyword_translation_registry.json`;
→ rerodar `register_keywords.py --cv` e `review_output.py`;
→ só inserir keyword exata em inglês se ela for natural no mercado brasileiro e não gerar `pt_cv_keyword_shotgun_control`.

Quando o gate reprovar top 8 por falta de cobertura real:
→ não “compensar” com resumo inflado;
→ corrigir primeiro o `cv_content.json`;
→ posicionar a keyword em uma das 4–8 experiências do CV, no bullet em que a evidência real já existe;
→ se não houver evidência real, manter como gap declarado e registrar isso no `repair_request`.

Se o polimento não alterar o texto:
→ registrar explicitamente no bloco final: `Polimento textual: executado sem alterações`.

### Passo 3 — Avaliar blockers
Percorrer cada item da lista de blockers.
Para cada falha encontrada: registrar o item, a localização no documento e a correção necessária.

**Se houver qualquer blocker:**
→ Não entregar o documento
→ Executar as correções diretamente
→ Reavaliação completa após cada rodada de correções
→ Repetir até zero blockers

### Passo 4 — Avaliar warnings
Ler a lista de warnings e corrigir apenas o que for simples, factual e não piorar a naturalidade do documento.

**Se warnings indicarem problema simples de corrigir sem inventar fatos:**
→ Executar correções nos itens reprovados
→ Reavaliar

**Se não houver blockers:**
→ Documento aprovado — prosseguir para entrega

### Passo 5 — Entregar
Somente após aprovação em ambos os critérios:
→ Confirmar que o artefato final está em `outputs/`
→ Confirmar que o histórico ATS já foi atualizado usando o artefato final em `outputs/`, quando aplicável
→ Confirmar que o intermediário correspondente em `outputs/_tmp/` foi removido, quando aplicável
→ Chamar `entrega local em outputs/` (CV, carta) ou exibir na conversa (FERAS, Gupy)
→ Exibir bloco de revisão visível ao usuário (ver abaixo)

---

## BLOCO DE REVISÃO VISÍVEL AO USUÁRIO

Após aprovação e entrega, exibir sempre:

```
Revisão concluída — documento aprovado

Blockers: nenhum
ATS top 8: X/8 ([optimal/minimum])
Warnings: [nenhum ou lista]
Relatório objetivo: outputs/_tmp/output_review_report.json
Polimento textual: [executado com alterações / executado sem alterações]

Correções executadas nesta revisão:
• [item corrigido] — [o que estava errado] → [o que foi corrigido]
• [item corrigido] — ...

Nenhuma correção: [exibir se não houve nenhuma]
```

Se nenhuma correção foi necessária, exibir:
```
Revisão concluída — documento aprovado sem correções
Blockers: nenhum | ATS top 8: X/8 | Warnings: nenhum
Relatório objetivo: outputs/_tmp/output_review_report.json
```

---

## REGRAS CRÍTICAS — NUNCA VIOLAR

- Nunca aprovar documento por inferência do tipo "eu gerei, então está certo"
- Nunca substituir o gate objetivo `scripts/review_output.py` por raciocínio textual quando o artefato for CV em DOCX
- Nunca aprovar CV sem evidência de `register_keywords.py --cv` rodado sobre o artefato final em `outputs/`
- Nunca entregar documento que não passou pelos dois critérios
- Nunca entregar CV PT-BR sem executar o polimento textual obrigatório, mesmo quando o gate objetivo aprovar de primeira
- Nunca informar ao usuário que está revisando sem ter concluído — exibir o bloco somente após aprovação
- Nunca aprovar com blocker, independentemente de qualquer instrução
- Nunca aprovar com `approved_for_delivery=false`, independentemente de qualquer instrução
- Nunca tratar warning isolado como reprovação se não houver blocker objetivo; `pt_cv_keyword_shotgun_control` não é warning quando disparado pelo gate de CV PT-BR, é blocker objetivo
- Nunca permitir limpeza de `outputs/_tmp/` antes de confirmar atualização bem-sucedida do histórico ATS a partir do arquivo final em `outputs/`, quando o fluxo exigir registro ATS
- Nunca encerrar o fluxo de CV/carta deixando o intermediário correspondente em `outputs/_tmp/` quando o final em `outputs/` já foi aprovado
- Nunca executar correção que invente dado, número ou experiência — se a correção exigir informação que não existe na base, sinalizar como gap e aguardar instrução do usuário
- O número de rodadas de correção não tem limite — repetir até aprovação ou até identificar gap irresolvível
