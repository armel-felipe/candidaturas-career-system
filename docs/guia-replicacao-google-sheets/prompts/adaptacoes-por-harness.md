# Adaptações por harness

Use primeiro o [prompt-mestre](prompt-mestre-instalacao.md). Estas adaptações
apenas resolvem diferenças de ambiente; não alteram as regras de segurança.

## Codex

Use Codex no projeto local e autorize somente os comandos que você entende.
Ele é a opção mais direta para criar arquivos, executar PowerShell, instalar
dependências e manter o Git. Peça sempre um resumo dos comandos e resultados.

## Claude Code

Abra o diretório `SistemaCandidaturas` no terminal/VS Code, execute Claude
Code dentro dele e cole o prompt-mestre. Confirme ações externas no navegador
você mesmo. Para LinkedIn, mantenha a sessão no navegador local; não compartilhe
cookies com o chat.

## Gemini

Use Gemini com acesso ao terminal/local workspace, se disponível. Se a sua
versão não executar terminal ou navegador persistente, peça para ele criar a
estrutura, os prompts e os scripts; conclua OAuth e LinkedIn depois com Codex
ou Claude Code localmente.

## ChatGPT Work

Use o ambiente de coding/agente que possua acesso ao diretório Windows. Caso o
seu ChatGPT Work não possa rodar comandos locais, ele ainda pode preencher o
perfil, revisar descrições e gerar prompts, mas a instalação, OAuth e o
extrator do LinkedIn devem ser executados por Codex ou Claude Code local.

## Regra de compatibilidade

Nenhum harness deve presumir que outro manteve memória. O estado está nos
arquivos locais e no Sheets: ao trocar de ferramenta, peça para ela ler
`README.md`, `perfil/autoconhecimento.md`, a linha da candidatura e o log
correspondente antes de alterar qualquer coisa.
