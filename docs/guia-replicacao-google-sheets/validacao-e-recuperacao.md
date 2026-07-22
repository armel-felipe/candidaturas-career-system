# Validação e recuperação

Use esta página quando o harness reportar falha. Regra geral: preservar
arquivos, registrar o erro e corrigir o menor componente possível. Não apague
o projeto, token ou planilha como primeira tentativa.

## Dependência Windows ausente

**Sinal:** `git`, `node`, `python` ou `npx playwright` não responde.

**Preserve:** o projeto e arquivos de perfil.

**Ação segura:** o harness mostra o comando `winget` exato, explica o programa
e pede confirmação. Após instalar, fecha/reabre o terminal se necessário e
executa a verificação correspondente.

**Aprovado quando:** `git --version`, `node --version`, `python --version` e,
quando aplicável, `npx playwright --version` retornam versões.

## OAuth recusado ou token inválido

**Sinal:** navegador informa acesso negado, escopo incorreto ou token expirado.

**Preserve:** `credentials.json`, a planilha e dados locais. Não os envie ao
chat nem ao Git.

**Ação segura:** confira que Sheets API e Drive API estão habilitadas; confirme
que a credencial é “Aplicativo para computador”; apague somente o token local
expirado, não o arquivo de credenciais; refaça o consentimento no navegador.

**Aprovado quando:** o harness lê o título da planilha e escreve/remove a linha
`TESTE_OAUTH_OK` na aba `Logs` e a remove em seguida.

## Sem permissão na planilha

**Sinal:** erro 403, planilha não encontrada ou aba inexistente.

**Preserve:** token e projeto local.

**Ação segura:** abra a URL da planilha no mesmo navegador/conta que autorizou
o OAuth; confirme o `spreadsheet_id` em `Config`; crie as abas exigidas com os
nomes exatos. Reautorize somente se a conta estiver diferente.

**Aprovado quando:** o harness lista as abas `Candidaturas`, `Listas`, `Config`,
`Métricas` e `Logs` sem alterar linhas reais.

## Linha inválida ou estado incoerente

**Sinal:** ID duplicado, `etapa` livre, caminho de descrição ausente ou uma
candidatura muda de etapa sem arquivo correspondente.

**Preserve:** linha, logs e artefatos existentes.

**Ação segura:** peça ao harness para identificar o ID, ler o log mais recente,
validar caminhos e corrigir somente o campo inconsistente. IDs nunca são
renumerados; crie novo ID apenas para uma nova vaga.

**Aprovado quando:** o caminho existe, as listas validadas são usadas e
`proxima_acao` descreve uma ação possível.

## Sessão LinkedIn expirada ou CAPTCHA

**Sinal:** tela de login, CAPTCHA, bloqueio, vaga indisponível ou extração sem
texto útil.

**Preserve:** linha do tracker e qualquer descrição já salva.

**Ação segura:** pare a automação; faça login manualmente no navegador ou cole
a descrição de fonte autorizada. Nunca resolva CAPTCHA por automação, nunca
importe cookies para o chat e não tente repetir agressivamente.

**Aprovado quando:** há uma descrição completa salva no caminho da linha e um
novo `descricao_hash` calculado.

## Descrição ausente ou alterada

**Sinal:** `descricao_arquivo` não existe, está vazio ou o hash não coincide.

**Preserve:** FIT_MAP e CV anteriores como histórico, mas não os trate como
atuais.

**Ação segura:** recapture ou cole a descrição; salve nova versão local;
atualize hash e retorne a `descricao_validada`. Refaça a análise antes de gerar
materiais novos.

**Aprovado quando:** texto, caminho, hash, empresa e cargo se referem à mesma
vaga.

## Artefato perdido ou revisão reprovada

**Sinal:** `cv_arquivo` não existe, o CV contém fato não comprovado, ou a
revisão aponta lacuna/idioma/ATS.

**Preserve:** versões existentes; nunca sobrescreva a única cópia.

**Ação segura:** mantenha `etapa=revisao_pendente`; gere uma nova versão com
data/hora a partir do perfil e FIT_MAP atuais; repita a revisão factual e ATS.

**Aprovado quando:** o arquivo apontado existe, não há blockers e a etapa é
`pronta_para_aplicacao`.

## Troca de harness ou contexto perdido

**Sinal:** nova ferramenta não sabe o que foi feito ou propõe recomeçar.

**Preserve:** todo estado local e tracker.

**Ação segura:** peça para ler `README.md`, `perfil/autoconhecimento.md`, a
linha do ID, `descricao_arquivo`, `pasta_artefatos` e última entrada de `Logs`.
Só depois ela propõe a próxima ação.

**Aprovado quando:** a ferramenta relata o mesmo ID, etapa, último erro e
próxima ação que aparecem no Sheets.
