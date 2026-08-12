# Catálogo de Posicionamento para CVs Personalizados — Design

## Objetivo

Usar um catálogo curado de áreas, casos e resultados-chave para escolher o
posicionamento que abre cada CV personalizado. A escolha deve considerar o
contexto completo da candidatura e nunca transformar resultados do catálogo em
alegações atribuídas ao candidato.

## Fonte canônica

O arquivo atualmente na raiz como `resultados.json` será movido, sem alteração
de conteúdo, para:

```text
.agents/skills/career-system/references/catalogo_resultados_chave.json
```

O novo nome explicita que se trata de um catálogo de posicionamento e não de
uma saída gerada. A fonte contém registros com os campos obrigatórios:

```json
{
  "id": 1,
  "area": "Planejamento integrado e S&OP",
  "indice": 3,
  "casos": "Equilibrar demanda, capacidade, supply, custos, estoques e nível de serviço.",
  "resultado_chave": "..."
}
```

O carregamento valida que o documento é uma lista não vazia; cada registro tem
os cinco campos, IDs únicos, `indice` inteiro positivo e textos não vazios. O
catálogo é versionado no Git e documentado na lista de fontes canônicas de
`.agents/skills/career-system/SKILL.md`.

## Limite factual

`resultado_chave` é um sinal para discernir o posicionamento, não uma fonte de
fatos publicáveis. O sistema pode comparar seu texto com a vaga, mas não pode
copiar números, percentuais, empresas ou frases dele para o resumo, bullets,
carta ou qualquer outro artefato de candidatura.

Todas as alegações sobre o candidato continuam sendo originadas e verificadas
em `candidate_cv_facts.json`, `autoconhecimento.md` e `perfil_restricoes.md`.

## Seleção determinística

Um módulo dedicado de posicionamento será chamado por `cv_content._build_cv_payload`
antes de `_build_summary`. Ele receberá o FIT_MAP normalizado e o caminho da
descrição persistida da vaga.

Para cada registro do catálogo, o módulo normaliza texto (minúsculas, sem
acentos e sem pontuação), descarta stopwords e calcula a aderência ponderada
entre `area`/`casos`/`resultado_chave` e estes sinais:

| Sinal da candidatura | Peso |
| --- | ---: |
| Cargo | 5 |
| Dor central | 4 |
| Keywords ATS priorizadas | 3 |
| Keywords e competências da vaga | 2 |
| Responsabilidades e requisitos extraídos | 2 |
| Histórias selecionadas e objeções do FIT_MAP | 1 |
| Texto da descrição persistida | 1 |

`area` e `casos` são os textos primários de correspondência. Tokens de
`resultado_chave` contribuem somente como desempate entre registros já
aderentes à mesma área/caso. Empates finais são resolvidos por menor `id`,
garantindo repetibilidade.

O seletor só publica um posicionamento quando existe ao menos uma correspondência
em `area` ou `casos`; se não houver, o CV mantém a abertura atual e registra
`positioning: null`. Isso evita enquadrar uma vaga em um caso artificialmente.

## Contrato de saída

Quando houver seleção, `cv_content.json` terá:

```json
{
  "positioning": {
    "catalog_entry_id": 1,
    "area": "Planejamento integrado e S&OP",
    "caso": "Equilibrar demanda, capacidade, supply, custos, estoques e nível de serviço.",
    "score": 27,
    "matched_signals": ["cargo: planejamento", "dor_central: capacidade"],
    "catalog_sha256": "<hash do catálogo>"
  },
  "positioning_support": {
    "catalog_entry_id": 1,
    "caso": "Equilibrar demanda, capacidade, supply, custos, estoques e nível de serviço.",
    "evidence_id": "<id de proveniência>"
  }
}
```

`matched_signals` armazena somente tokens ou campos de seleção, sem reproduzir
o resultado-chave. O hash protege contra a reutilização de uma decisão quando
o catálogo tiver sido alterado.

## Composição do resumo

Quando `positioning` existir, a abertura do resumo será:

> Busco posição de `{cargo}` para `{caso}`, apoiado por `{evidência 1}` e `{evidência 2}`.

As duas evidências são as mesmas evidências de experiência que o fluxo atual
seleciona e valida em `summary_support`. O novo `positioning_support` prova a
origem do caso, enquanto `summary_support` continua provando os fatos do
candidato. Quando não houver posicionamento, preserva-se integralmente a
abertura já existente.

## Proveniência e validação

`catalogo_resultados_chave.json` será incluído no catálogo de fontes de
proveniência do CV. A seleção produzirá uma evidência `positioning_catalog`
vinculada ao ID, área e caso do registro. A validação de `cv_content.json`
passará a exigir, quando houver `positioning`:

- campos não vazios e `catalog_entry_id` existente no catálogo;
- hash idêntico ao arquivo canônico em uso;
- `caso` do payload idêntico ao registro canônico;
- `positioning_support` com a evidência de proveniência correspondente;
- presença literal do caso no resumo;
- ao menos duas entradas de `summary_support` vinculadas a bullets reais.

O validador não permitirá que `resultado_chave` seja usado como
`summary_fragment`, `defensible_evidence` ou bullet.

## Testes de aceitação

1. Carregar um catálogo válido retorna seus registros; esquema inválido, ID
   repetido ou campo vazio é rejeitado.
2. Um FIT_MAP de planejamento com termos de demanda, capacidade e S&OP seleciona
   o caso de planejamento e persiste sua explicação de seleção.
3. Dois registros aderentes são desempatados pelo contexto de
   `resultado_chave`, sem que esse texto seja publicado no resumo.
4. Um FIT_MAP sem interseção com área/caso não publica posicionamento e mantém
   a abertura legada.
5. Um `cv_content.json` com caso alterado, hash diferente, evidência ausente ou
   caso fora do resumo falha na validação.
6. Um resumo que contenha número ou frase do `resultado_chave`, mas não esteja
   sustentado por bullet canônico, falha na validação existente de
   `summary_support`.

## Fora de escopo

- Alterar automaticamente o FIT_MAP.
- Usar o catálogo em cartas, pitch, habilidades ou documentos gerais.
- Gerar texto por LLM ou introduzir uma dependência de IA para a seleção.
- Migrar ou reescrever os fatos existentes do candidato.
