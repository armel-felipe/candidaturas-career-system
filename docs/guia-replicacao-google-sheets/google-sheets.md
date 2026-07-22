# Google Sheets: tracker, colunas e conexão segura

O Google Sheets é o painel operacional, não o depósito de arquivos. Cada linha
em `Candidaturas` representa uma vaga. Descrições completas, análises,
evidências, CVs e cartas permanecem no computador, em pastas identificadas
pelo mesmo `id_candidatura`.

## Criar a planilha

1. Crie uma planilha vazia na sua conta Google pessoal: `Tracker de candidaturas`.
2. Crie as abas `Candidaturas`, `Listas`, `Config`, `Métricas` e `Logs`.
3. Importe `templates/candidaturas.csv` para `Candidaturas` e
   `templates/listas.csv` para `Listas`.
4. Congele a primeira linha de `Candidaturas`; aplique filtro; deixe as colunas
   de texto longo com quebra de linha.
5. Use validação de dados em `fonte`, `regime_trabalho`, `idioma_vaga`,
   `decisao` e `etapa`, apontando para as listas da aba `Listas`.

## Aba Candidaturas

| Coluna | Tipo | Quem atualiza | Por quê |
| --- | --- | --- | --- |
| `id_candidatura` | texto imutável, ex. `APP-00001` | harness | Liga planilha, pasta local e logs mesmo se o cargo mudar. |
| `criada_em` | data/hora ISO | harness | Audita a entrada e mede tempo de ciclo. |
| `atualizada_em` | data/hora ISO | harness | Mostra registros parados. |
| `empresa` | texto | harness; humano confirma ambiguidade | Base para filtros e nomeação. |
| `cargo` | texto | harness; humano confirma ambiguidade | Define alvo de análise e CV. |
| `url_vaga` | URL | harness ou humano | Permite retornar à fonte. |
| `fonte` | lista | harness | Separa LinkedIn, indicação e carreira. |
| `localidade` | texto | harness quando disponível | Filtra compatibilidade geográfica. |
| `regime_trabalho` | lista | harness quando disponível | Registra remoto, híbrido, presencial ou não informado. |
| `descricao_arquivo` | caminho relativo | harness | Aponta para cópia local integral da vaga. |
| `descricao_hash` | texto | harness | Detecta mudança de conteúdo após a análise. |
| `idioma_vaga` | lista | harness | Determina o idioma dos materiais. |
| `fit_score` | número 0–100 | harness | Ajuda a priorizar; não decide por você. |
| `fit_resumo` | texto curto | harness | Explica rapidamente o racional. |
| `gaps_declarados` | texto curto | harness | Expõe lacunas reais sem inventar cobertura. |
| `decisao` | lista | humano | Você escolhe `prosseguir`, `pausar` ou `descartar`. |
| `etapa` | lista controlada | harness até revisão; humano para finalização | Controla o estado do fluxo. |
| `proxima_acao` | texto curto | harness | Mantém a fila acionável. |
| `prazo` | data | harness se explícito; humano confirma | Evita perder janelas reais. |
| `cv_arquivo` | caminho/URL | harness após revisão | Localiza o CV final sem armazenar binário. |
| `carta_arquivo` | caminho/URL | harness após revisão | Localiza a carta, se necessária. |
| `pasta_artefatos` | caminho relativo | harness | Permite recuperação por vaga. |
| `observacoes_humanas` | texto | humano | Contexto que o harness nunca sobrescreve. |
| `ultimo_erro` | texto curto | harness | Torna bloqueios visíveis; só limpa após resolução. |

As etapas permitidas são `capturada`, `descricao_validada`, `analisada`,
`artefatos_em_rascunho`, `revisao_pendente`, `pronta_para_aplicacao`,
`aplicada` e `encerrada`. Automação nunca define `aplicada`: essa etapa exige
ação humana real.

## Outras abas

- **Listas:** vocabulário usado pelas validações. Evita que “Aplicado”,
  “aplicada” e “enviei” quebrem os filtros.
- **Config:** somente `spreadsheet_id`, timezone, idioma padrão e pasta local.
  Não armazene tokens, senha, cookies ou `client_secret`.
- **Métricas:** fórmulas sobre `Candidaturas`: quantidade por etapa, média de
  dias em fila, distribuição de fit e taxa de avanço. Não edite manualmente.
- **Logs:** colunas `timestamp`, `id_candidatura`, `acao`, `resultado`,
  `detalhe_curto`, `run_id`. Uma ação de escrita do harness gera uma linha.

## Conectar sua conta Google por OAuth

Peça ao harness para executar estes passos, um de cada vez, e mostrar a
verificação de cada um:

1. Abra Google Cloud Console e crie um projeto exclusivo, por exemplo
   `sistema-candidaturas-pessoal`.
2. Em **APIs e serviços**, habilite **Google Sheets API** e **Google Drive API**.
3. Configure a tela de consentimento como **Externa** e adicione somente seu
   e-mail como usuário de teste, se a tela solicitar.
4. Crie uma credencial OAuth do tipo **Aplicativo para computador**.
5. Baixe o JSON e salve-o localmente, por exemplo em
   `state/google-oauth/credentials.json`; garanta que esse caminho está no
   `.gitignore`. Não cole o conteúdo em um chat.
6. Execute o comando de autorização que o harness gerar. O navegador abrirá
   para você conceder acesso à sua própria planilha. O token local também deve
   ficar ignorado pelo Git.
7. Crie uma planilha de teste e permita que o harness escreva uma única linha
   `TESTE_OAUTH_OK`; confirme no navegador e depois apague essa linha.

## Critérios de conexão aprovada

- O harness lê o título da planilha correta.
- O harness cria e remove a linha de teste somente na aba de teste.
- `git status` não mostra `credentials.json`, token ou pasta de navegador.
- O tracker real continua editável pela sua conta Google no navegador.

Se o OAuth falhar, não recrie todo o projeto: consulte
[validação e recuperação](validacao-e-recuperacao.md).
