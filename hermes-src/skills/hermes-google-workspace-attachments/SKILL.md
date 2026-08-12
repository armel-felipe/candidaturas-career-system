---
name: hermes-google-workspace-attachments
description: >
  Local patch applied to the official `google-workspace` Hermes skill, adding `--attach`
  support to `gmail send` so the agent can send application emails with CVs/PDFs
  attached via MIME multipart. Use when the user asks to "send email with attachment",
  "attach CV to email", or "gmail send with file". Authored by Felipe's setup; copies
  the patched google_api.py + setup.py to every Hermes profile so the change is global.
---

# Hermes Google Workspace — Attachments Patch

## Estado atual (em 2026-07-27)

Esta skill é um **patch local** aplicado à skill oficial `google-workspace` (Nous Research) que adiciona:

1. **Suporte a anexos no `gmail send`** — flag `--attach PATH` (repetível para múltiplos arquivos)
2. **Correção do `REDIRECT_URI`** em `setup.py` — de `http://localhost:1` para `http://localhost` (evita `redirect_uri_mismatch` em OAuth clients Desktop app sem whitelist manual)

As mudanças foram aplicadas em **todas as 4 cópias** da skill `google-workspace` no filesystem:

| Caminho | Status |
|---|---|
| `~/.hermes/skills/productivity/google-workspace/scripts/{setup.py,google_api.py}` | patched |
| `~/.hermes/profiles/vagas_bot_01/skills/productivity/google-workspace/scripts/{setup.py,google_api.py}` | patched |
| `~/.hermes/profiles/vagas_bot_02/skills/productivity/google-workspace/scripts/{setup.py,google_api.py}` | patched |
| `~/.herbundefinedhermes-agent/skills/productivity/google-workspace/scripts/{setup.py,google_api.py}` | patched |

## O que mudou em `google_api.py`

### Antes
```python
def gmail_send(args):
    if _gws_binary():
        message = MIMEText(args.body, "html" if args.html else "plain")
        # ... só MIMEText, sem anexo
```

### Depois
```python
def gmail_send(args):
    attachments = getattr(args, "attach", []) or []
    use_multipart = bool(attachments)

    if use_multipart:
        message = MIMEMultipart()
        message.attach(MIMEText(args.body, "html" if args.html else "plain"))
    else:
        message = MIMEText(args.body, "html" if args.html else "plain")
    # ... headers ...
    for path_str in attachments:
        p = Path(path_str).expanduser()
        ctype, _ = guess_type(str(p))
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        with p.open("rb") as f:
            part = MIMEBase(maintype, subtype)
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{p.name}"')
        message.attach(part)
    # ... send via gws or python API
```

### Parser
Adicionada a flag `--attach` (action="append") no subparser `gmail send`.

## O que mudou em `setup.py`

```python
# Antes:
REDIRECT_URI = "http://localhost:1"

# Depois (com comentário explicativo):
REDIRECT_URI = "http://localhost"   # Desktop app OAuth client aceita por default
```

## Como reaplicar (em outra máquina ou após update do Hermes)

Se você rodar `hermes skills update` ou reinstalar a skill `google-workspace`, as mudanças são sobrescritas. Para reaplicar:

```bash
# 1. Identifique todos os paths da skill
find ~/.hermes -type d -name google-workspace | sort

# 2. Para cada path, copie os scripts do source patched:
SRC=~/.hermes/skills/productivity/google-workspace/scripts
for DST in ~/.hermes/profiles/*/skills/productivity/google-workspace/scripts \
           ~/.hermes/hermes-agent/skills/productivity/google-workspace/scripts; do
  if [ -d "$DST" ]; then
    cp "$SRC/setup.py" "$DST/setup.py"
    cp "$SRC/google_api.py" "$DST/google_api.py"
  fi
done
```

## Uso

```bash
GAPI="python ~/.hermes/skills/productivity/google-workspace/scripts/google_api.py"

# Sem anexo (mesma sintaxe anterior)
$GAPI gmail send --to user@example.com --subject "Hello" --body "World"

# Com anexo
$GAPI gmail send --to user@example.com \
  --subject "Application" \
  --body "See attached CV." \
  --from '"Felipe Armel" <armelfelipe@gmail.com>' \
  --attach outputs/felipe_armel_cv.docx

# Múltiplos anexos (repetir --attach)
$GAPI gmail send --to user@example.com --subject "Docs" --body "Below" \
  --attach file1.pdf --attach file2.docx
```

## Compatibilidade

- ✅ Funciona com o fallback Python (gws CLI ausente) — usa `googleapiclient.discovery.build`
- ⚠️ **Não funciona** se o `gws` CLI estiver instalado — o caminho `_gws_binary()` não passa pelo bloco de anexos. Workaround: `which gws || echo "not installed"` — se retornar path, desinstale temporariamente.
- ✅ Backward compatible: se nenhum `--attach` for passado, comportamento idêntico ao original (`MIMEText` simples)
- ✅ Auto-detecta MIME type via `mimetypes.guess_type`; fallback `application/octet-stream`

## Bloqueios conhecidos

- `hermes skills update` sobrescreve os scripts → reaplicar manualmente
- Labels de sistema (SENT, INBOX) não podem ser removidas via `gmail modify` (erro 400) — não relacionado a este patch

## Verificações

- [ ] Sintaxe Python válida em todos os 4 paths
- [ ] `gmail send --help` mostra `--attach` em todos os 4 paths
- [ ] Teste de envio com anexo para si mesmo retorna `{"status": "sent"}`
- [ ] `gmail get <messageId>` confirma que o email foi entregue ao destinatário