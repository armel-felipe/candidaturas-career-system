#!/usr/bin/env python3
"""
Atualiza o corpo de uma página do Notion, appendando texto ao final.
Uso: python3 scripts/append_notion_body.py <page_id> <arquivo_texto> [--dry-run]
"""
import sys
import os
import json
import urllib.request
import urllib.error
from pathlib import Path

# Usar o mesmo padrao do notion_sync.py
sys.path.insert(0, str(Path(__file__).parent))
from notion_sync import load_dotenv

NOTION_VERSION = "2022-06-28"

def load_env():
    load_dotenv()

def get_notion_token():
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise SystemExit("Set NOTION_TOKEN in the environment or in .env before using Notion sync.")
    return token

def notion_request(method, path, token, payload=None):
    url = f"https://api.notion.com/v1/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }
    
    data = json.dumps(payload).encode('utf-8') if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ""
        raise SystemExit(f"Notion API error {e.code}: {error_body}")

def append_body(page_id: str, text_to_append: str, dry_run: bool = False):
    token = get_notion_token()
    
    # Criar blocos a partir do texto
    lines = text_to_append.strip().split('\n')
    
    new_blocks = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('## '):
            new_blocks.append({
                "heading_2": {
                    "rich_text": [{"text": {"content": line.replace('## ', '')}}]
                }
            })
        elif line.startswith('### '):
            new_blocks.append({
                "heading_3": {
                    "rich_text": [{"text": {"content": line.replace('### ', '')}}]
                }
            })
        elif line.startswith('- **'):
            # Bullet list com bold
            content = line.replace('- **', '')
            # Extrair keyword em bold
            if '**' in content:
                parts = content.split('**', 1)
                keyword = parts[0]
                rest = parts[1].lstrip(': ') if len(parts) > 1 else ''
                new_blocks.append({
                    "bulleted_list_item": {
                        "rich_text": [
                            {"text": {"content": keyword}, "annotations": {"bold": True}},
                            {"text": {"content": ": " + rest if rest else ""}}
                        ]
                    }
                })
            else:
                new_blocks.append({
                    "bulleted_list_item": {
                        "rich_text": [{"text": {"content": content}}]
                    }
                })
        elif line.startswith('- '):
            new_blocks.append({
                "bulleted_list_item": {
                    "rich_text": [{"text": {"content": line.replace('- ', '')}}]
                }
            })
        else:
            new_blocks.append({
                "paragraph": {
                    "rich_text": [{"text": {"content": line}}]
                }
            })
    
    if dry_run:
        print(f"[DRY-RUN] Adicionaria {len(new_blocks)} blocos à página {page_id}")
        print(f"Texto a adicionar: {len(text_to_append)} caracteres")
        return
    
    # Adicionar blocos no final da página
    if new_blocks:
        result = notion_request("POST", f"blocks/{page_id}/children", token, {"children": new_blocks})
        print(f"Adicionados {len(result.get('results', []))} blocos à página {page_id}")
        print(f"URL: https://notion.so/{page_id.replace('-', '')}")
    else:
        print("Nenhum bloco foi criado")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Uso: python3 scripts/append_notion_body.py <page_id> <arquivo_texto> [--dry-run]")
        sys.exit(1)
    
    page_id = sys.argv[1]
    text_file = sys.argv[2]
    dry_run = '--dry-run' in sys.argv
    
    with open(text_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    append_body(page_id, text, dry_run=dry_run)
