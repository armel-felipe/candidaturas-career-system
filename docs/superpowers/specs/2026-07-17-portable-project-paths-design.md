# Caminhos Portáveis do Projeto — Design

## Objetivo

Eliminar os caminhos absolutos específicos do Mac encontrados nos arquivos ativos do projeto, para que a mesma árvore do repositório funcione após clone no GitHub, no RPi5 ou em qualquer outro diretório local.

## Escopo

Corrigir os 11 arquivos encontrados pela auditoria:

- `COMO_USAR.md`;
- os 10 scripts JavaScript em `scripts/generated/` que escrevem em `outputs/_tmp` usando `/Users/mac/llm server/projetos/candidaturas`.

## Decisão

- A documentação deve instruir o usuário a executar comandos a partir da raiz do repositório, sem um caminho absoluto de máquina.
- Cada script gerado deve calcular a raiz do projeto a partir do seu próprio local: `path.resolve(__dirname, "..", "..")`.
- Cada caminho de saída deve usar `path.join(workspace, "outputs", "_tmp", <arquivo>)`.
- Não introduzir uma variável de ambiente nova: os scripts legados ficam autocontidos e portáveis.
- A validação estrutural deve bloquear o caminho absoluto específico encontrado em arquivos ativos, incluindo `scripts/generated/` e `COMO_USAR.md`.

## Validação

1. Busca por `/Users/mac/llm server/projetos/candidaturas` em documentação, scripts, fonte e skills retorna vazia.
2. A validação estrutural passa.
3. A suíte pytest passa.
4. Os scripts atualizados continuam sintaticamente válidos com `node --check`.

## Fora de escopo

- Não alterar caminhos externos configuráveis, como OneDrive/rclone, credenciais ou variáveis de ambiente já existentes.
- Não regenerar documentos finais nem modificar o conteúdo dos arquivos DOCX.
