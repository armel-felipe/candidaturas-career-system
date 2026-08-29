# Limites de sessão Hermes no pipeline

Este mecanismo mantém as sessões Telegram de `vagas_bot_01` e `vagas_bot_02`
curtas sem apagar o histórico Hermes. A sessão ativa é trocada somente quando o
pipeline chega a um estágio terminal configurado e o handoff compacto já foi
persistido.

## Estado e retomada

Para uma candidatura `<ID>`, os artefatos são:

```text
.career-state/applications_v2/<ID>/hermes_handoff.json
.career-state/applications_v2/<ID>/hermes_session_ledger.json
```

O handoff contém estágio, score, próximos artefatos e IDs de sessão. Ele não
contém transcript, mensagens ou payloads de ferramentas.

No Telegram:

```text
/status
/resume <session_id_antigo>
```

Depois da correção, um novo limite de pipeline cria uma sessão limpa. O histórico
antigo permanece consultável enquanto o registro Hermes existir.

## Inspeção local

```bash
jq . .career-state/applications_v2/<ID>/hermes_handoff.json
jq . .career-state/applications_v2/<ID>/hermes_session_ledger.json
```

Operações com `pending_verification` são reconciliadas no início do heartbeat por
consulta somente leitura ao gateway. A reconciliação nunca envia um segundo
`/new` ou `/resume` automaticamente.

## Configuração e desligamento

O padrão é seguro e permanece desativado:

```json
"hermes_session_boundaries": {
  "enabled": false,
  "mode": "disabled"
}
```

Para observação controlada, configure explicitamente `enabled: true`, `mode:
"dry_run"`, o `profile_id`, o `session_key`, os endpoints e o mapeamento
`binding_profile_ids` do control-plane. Para mutação real, use `mode: "live"`
somente após o canário do perfil correspondente. As chaves ficam apenas
nas variáveis de ambiente `HERMES_GATEWAY_API_KEY_VAGAS_BOT_01` e
`HERMES_GATEWAY_API_KEY_VAGAS_BOT_02`.

Na implantação local, os endpoints autenticados ficam restritos ao host:

```text
vagas_bot_01: http://127.0.0.1:8643/api/gateway/session-boundary
vagas_bot_02: http://127.0.0.1:8644/api/gateway/session-boundary
```

O compose replica a chave do servidor como chave do cliente dentro de cada
container; ela não é registrada neste documento. O arquivo de produção é
`app/deploy/hermes/compose.yaml`.

Para desligar a automação durante uma investigação, altere para `enabled: false`
e `mode: "disabled"`. O uso manual de `/new` e `/resume` continua disponível.

As configurações Hermes dos bots permanecem com `session_reset.mode: none`; esse
plano controla apenas limites explícitos do pipeline, não reset por idle ou por
calendário. O rollout atual usa `mode: live` apenas na configuração de
`applications_v2` de cada workspace, após os canários; a política nativa Hermes
continua desativada.
