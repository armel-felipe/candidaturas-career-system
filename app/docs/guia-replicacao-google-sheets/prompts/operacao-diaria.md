# Prompts de operação diária

Substitua `<ID>` pelo identificador da linha. Se o seu harness não tiver
terminal ou navegador local, ele deve parar no passo que exigir essa capacidade
e indicar que Codex ou Claude Code local é necessário.

## Importar vagas salvas

```text
Use o projeto SistemaCandidaturas. Antes de agir, leia README.md e confirme que
nenhum token, cookie ou senha será exposto. No navegador local onde eu já estou
logado no LinkedIn, liste as vagas salvas sem tentar burlar login, CAPTCHA ou
limites. Para cada vaga, crie/atualize uma linha no Sheets com ID sequencial,
empresa, cargo, URL, fonte=linkedin_salva, data observada e etapa=capturada.
Não analise ainda. Registre um log por operação e me devolva uma lista curta:
ID | cargo | empresa | URL | próxima ação.
```

## Analisar uma vaga

```text
Analise a candidatura <ID>. Leia perfil/autoconhecimento.md, a linha <ID> do
Sheets e o arquivo indicado em descricao_arquivo. Se faltar texto completo,
pare e peça a descrição; não reutilize análise de outra vaga. Produza um
FIT_MAP local baseado apenas em fatos verificáveis: requisitos, evidências,
lacunas, top palavras-chave e recomendação. Atualize somente os campos do
harness: descricao_hash se necessário, idioma_vaga, fit_score, fit_resumo,
gaps_declarados, etapa=analisada, proxima_acao, atualizada_em e Logs. Não
altere decisao nem observacoes_humanas. Mostre evidências e lacunas, não uma
promessa de aprovação.
```

## Gerar CV

```text
Gere materiais para <ID> somente se decisao=prosseguir e etapa=analisada.
Leia o perfil, FIT_MAP e descrição persistida. Crie outputs/<ID>/ sem
sobrescrever um arquivo existente; se houver versão anterior, gere nova versão
com data/hora. Escreva no idioma da vaga, separe experiências reais e não
invente métricas. Atualize cv_arquivo, pasta_artefatos, etapa=artefatos_em_rascunho,
proxima_acao, atualizada_em e Logs. Não envie, anexe ou aplique em lugar algum.
```

## Revisar antes de aplicar

```text
Revise a candidatura <ID>. Compare todos os materiais em outputs/<ID>/ com
perfil/autoconhecimento.md e a vaga. Liste blockers factuais, de idioma,
arquivo ausente, prazo e palavra-chave artificial. Se houver blocker, mantenha
etapa=revisao_pendente e explique a correção. Se não houver blocker, defina
etapa=pronta_para_aplicacao e proxima_acao="Revisar e enviar manualmente".
Não mude etapa para aplicada; isso só acontece depois da minha confirmação de
que a candidatura foi enviada.
```

## Retomar após falha

```text
Retome <ID> sem apagar nem recriar artefatos. Leia a linha do Sheets, a última
entrada de Logs, descricao_arquivo, perfil/autoconhecimento.md e os caminhos
em pasta_artefatos/cv_arquivo. Valide o que ainda existe, escreva um resumo do
último erro e execute somente a próxima ação segura. Atualize ultimo_erro,
proxima_acao, atualizada_em e Logs. Se faltar permissão Google, sessão
LinkedIn ou descrição, pare com instruções específicas; não faça tentativa de
contorno.
```
