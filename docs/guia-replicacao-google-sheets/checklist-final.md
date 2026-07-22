# Checklist final de aceitação

Marque cada item antes de usar o sistema com vagas importantes.

## Perfil e segurança

- [ ] `perfil/autoconhecimento.md` está preenchido com fatos confirmados.
- [ ] Toda métrica tem unidade, período e evidência; as demais dizem “não mensurado”.
- [ ] O `.gitignore` cobre credenciais, token OAuth e perfil/cookies do navegador.
- [ ] `git status` não mostra segredo, token, cookie ou arquivo de credencial.
- [ ] Nenhum prompt instrui o harness a enviar candidatura, e-mail ou burlar LinkedIn.

## Google Sheets

- [ ] Existem as abas `Candidaturas`, `Listas`, `Config`, `Métricas` e `Logs`.
- [ ] `Candidaturas` tem os 24 cabeçalhos do modelo, na mesma ordem.
- [ ] As colunas de status usam validação baseada em `Listas`.
- [ ] OAuth lê a planilha e a escrita de teste foi confirmada e removida.
- [ ] `Config` não contém senha, token, `client_secret` nem cookie.

## Fluxo de vaga

- [ ] Uma vaga de teste recebeu ID único, pasta local e linha no tracker.
- [ ] A descrição foi salva localmente e possui hash registrado.
- [ ] A análise lista evidências e gaps, sem alegações inventadas.
- [ ] `decisao` foi definida por uma pessoa, não pelo harness.
- [ ] O CV, se gerado, existe no caminho `cv_arquivo` e usa apenas experiência verificada.
- [ ] Uma entrada em `Logs` permite identificar a última operação e `run_id`.
- [ ] `etapa=aplicada` só é usada depois de envio manual confirmado.

## Recuperação

- [ ] Você sabe onde consultar erros: `ultimo_erro` e `Logs`.
- [ ] Você testou ou entendeu como retomar uma sessão LinkedIn expirada.
- [ ] Você consegue trocar de harness sem perder contexto, seguindo a seção de retomada.
