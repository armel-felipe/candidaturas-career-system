# Legado Notion Direct API

Arquivos nesta pasta são exemplos antigos e desativados de acesso direto ao Notion.

Eles não fazem parte do fluxo operacional do projeto. O caminho atual é:

```bash
npm run intake:notion-record -- <id_unico>
npm run notion:*
python3 scripts/notion_sync.py ...
python3 scripts/notion_query.py ...
```

Não reativar scripts que leem `.env`, copiam token ou chamam endpoints do Notion diretamente.
