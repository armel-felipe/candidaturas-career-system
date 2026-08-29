---
name: cv-generator
instruction_modules: [runtime-core, cv-delivery]
description: >
  Gera o CV de Felipe Armel em DOCX ou PDF, adaptado a uma vaga ou perfil-alvo.
  Use sempre que o usuário pedir CV, currículo, adaptação, persona ou atualização de currículo.
  Requer FIT_MAP ativo; sem FIT_MAP, execute primeiro a análise de aderência.
---

# CV Generator

## Governança e entrada

Manutenção canônica: `.agents/skills/cv-generator/SKILL.md`. Leia também
`../career-system/SKILL.md` antes de executar.

No fluxo celular/orquestrado, leia primeiro `generation_request.json/md` e os arquivos
de `compact_inputs.primary_files`. Use `cv_content.json` como fonte principal. Produza
somente o artefato pedido; não faça novo intake, não atualize Notion e não gere DOCX,
ATS ou reviewer quando o request pedir apenas texto.

No fluxo manual, confirme o FIT_MAP ativo e execute:

```bash
npm run context:assert-active
npm run cv:build-content
npm run cv:validate-content
npm run cv:docx
```

Se o formato não estiver explícito, pergunte `Prefere DOCX (editável) ou PDF?`. Nunca
gere HTML. Para PDF, gere e aprove o DOCX primeiro e depois use
`scripts/docx/convert_pdf.sh`.

## Idioma obrigatório

O idioma segue a descrição da vaga. Vaga em inglês exige `fit_map.idioma = "en"`,
`cv_content.metadata.language = "en"`, títulos de cargos e labels em inglês e nome
terminado em `_en.docx` ou `_en.pdf`. Vaga em português não usa `_en`.

Antes de `cv:docx`, confira idioma e nome do arquivo. Se houver divergência, não
prossiga: corrija o FIT_MAP e regenere `cv_content`. No DOCX inglês, bloqueie se
restarem verbos portugueses como `fui responsável`, `gerenciei`, `liderei`, `conduzi`
ou `conectei`.

### English executive editorial pass

Do not optimize English resumes by translating Portuguese business language into
grammatically correct English. Rewrite the underlying idea using the idiomatic
vocabulary, collocations, and sentence structures naturally used in English-language
executive resumes. Natural executive English takes precedence over literal fidelity
to the original sentence structure. Factual fidelity to the candidate's actual
experience remains mandatory.

Apply this order before ATS: naturalness, executive syntax and concision,
idiomatic collocations, redundancy removal, seniority framing, executive Summary,
factual verification, ATS keywords, and a final native executive recruiter pass.

For English CVs, prefer direct resume verbs (`Led`, `Built`, `Scaled`, `Owned`,
`Reduced`, `Drove`) over repeated first-person narration. Rewrite the idea rather
than translating structures such as `full scope autonomy`, `direct and indirect
people`, `with C-level`, `correctly modeled ROI`, `deliver expansion`,
`lead-contact time`, or recurring `which allowed me to`. Use conservative wording
when reporting lines or ownership are ambiguous: `a 240-person organization` is
valid when `240 direct and indirect reports` is not proven.

The English Summary is an executive value proposition, not an autobiographical
cover letter. Prefer `Track record of...` and verified scale/results over repeated
`I have...` or `I am pursuing...`. Each bullet must add a distinct dimension of
scope, mechanism, leadership, financial impact, operational impact, or growth.
Apply keywords only after the prose is natural; never add unsupported facts or
repeat keywords for frequency.

The deterministic `english_editorial_guard` runs before DOCX rendering and blocks
known literal or autobiographical patterns. When it blocks, revise the canonical
English source and regenerate the content; do not bypass the guard with a manual
DOCX edit.

## Evidência e narrativa

Antes de escrever, consulte `perfil_restricoes.md` e `autoconhecimento.md`; números,
datas, cargos, empresas e resultados devem ser defensáveis. Nunca invente dados,
P&L total, ferramentas, certificações ou experiências.

Selecione a persona e 4–8 experiências com base em `dor_central` e
`historias_selecionadas` do FIT_MAP. Preserve sempre ordem cronológica inversa. Nunca
consolide cargos, promoções, fases ou escopos: iFood Head e iFood Diretor, e cargos
distintos da Trifil, são entradas separadas.

No modo conciso (padrão), use exatamente 3 bullets por experiência:

1. escopo, responsabilidade e time, começando naturalmente por `Fui responsável por`;
2. alavanca causal com verbo de ação em primeira pessoa;
3. resultado mensurável, começando por verbo de resultado.

Nenhum bullet usa rótulo seguido de `:`. Todo bullet é prosa em primeira pessoa,
contém número defensável e destaca o número mais estratégico. Modo expandido só é
permitido quando o usuário pedir explicitamente mais bullets, bullet points ou versão
expandida; se não informar a quantidade, pergunte.

Distribua as top 8 keywords do FIT_MAP entre experiências e bullets defensáveis.
Em CV PT-BR, prefira equivalentes naturais e no máximo uma keyword-habilidade inglesa
por bullet; não faça keyword stuffing. Keyword sem evidência é gap, nunca invenção.
Todo fato do resumo precisa reaparecer em uma experiência incluída no CV.

Regras protegidas: VivaReal CS é arquitetura da área, não gestão; fill rate pertence
à Trifil; WeHandle usa margem bruta de 15% e custo por atendimento de R$4,14 para
R$3,61; iFood pode usar saving de R$70MM/ano e budget de R$300MM/ano quando sustentados
pelas referências; não inclua espanhol; inglês é `Avançado`.

## Estrutura e arquivo

Cabeçalho fixo, alinhado à esquerda, sem emojis e sem dois contatos na mesma linha:

```text
Felipe Armel Dias da Silva
linkedin.com/in/felipearmel
Guarulhos, SP
(11) 98674-8218
armelfelipe@gmail.com
```

Use hyperlinks externos para LinkedIn, WhatsApp `https://wa.me/5511986748218` e
email `mailto:armelfelipe@gmail.com`. Resumo factual, em primeira pessoa, com máximo
de 480 caracteres salvo autorização explícita. Não abrir com o cargo-alvo se ele não
foi exercido formalmente.

Nome obrigatório: `felipe_armel_cv_[cargo]_[empresa].[ext]`, com cargo e empresa em
snake_case, sem acentos; acrescente `_en` antes da extensão para inglês. Nunca use
`cv.docx`, `cv_final` ou nome genérico.

## Produção e gates

Para DOCX, o artefato final é sempre `outputs/<nome>.docx`. Gere intermediários apenas
em `outputs/_tmp/generated_scripts/`. O script deve usar Arial, `const pt = n => n * 2`,
9pt no texto, 12pt no nome/seções, A4, margens `{top:720,right:504,bottom:720,left:504}`
e numbering real para bullets; não use bullets Unicode manuais. Valide:

```bash
npm run validate:docx
python3 scripts/register_keywords.py --fit-map .career-state/fit_map.json --translation-registry .agents/skills/career-system/references/keyword_translation_registry.json \
  --cv outputs/<nome>.docx
python3 scripts/review_output.py --kind cv --artifact outputs/<nome>.docx \
  --fit-map .career-state/fit_map.json \
  --registry .career-state/derived/keyword_ats_registry.json \
  --report outputs/_tmp/output_review_report.json
npm run cv:approve -- --artifact outputs/<nome>.docx
```

O `register_keywords.py` deve apontar para o DOCX final em `outputs/`, nunca para
temporário. O reviewer precisa retornar `approved_for_delivery=true`, zero blockers,
score mínimo 5,2/8 e zero `missing_unexplained`. Warnings isolados não bloqueiam.
Se houver reprovação, corrija, regenere, registre ATS e revise novamente. CV PT-BR
sempre passa pelo polimento do reviewer; se o texto mudar, repita os gates.

Quando OneDrive estiver configurado, finalize com:

```bash
npm run cv:deliver -- --artifact outputs/<nome>.docx
```

Só declare entrega remota com relatório `status=delivered`. Limpe os intermediários
em `outputs/_tmp/` somente depois de validação, ATS e revisão aprovados. A resposta
final deve registrar ajustes narrativos, keywords cobertas, gaps e comandos executados.

## Proibições críticas

- não reaproveitar FIT_MAP, `cv_content` ou request stale de outra vaga;
- não alterar números críticos, idioma ou narrativas para aumentar matching;
- não aprovar por leitura visual ou autoavaliação;
- não entregar DOCX sem `validate:docx`, registro ATS, reviewer e gate de aprovação;
- não limpar temporários antes dos gates;
- não criar scripts temporários na raiz ou em `scripts/generated/`;
- não remover a seção de competências/tags ATS quando prevista pelo pipeline.
