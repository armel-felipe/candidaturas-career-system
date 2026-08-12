# Hermes deployment

A configuração ativa do projeto está na raiz do deployment:

```text
/opt/agent-projects/candidaturas/compose.yaml
```

Os serviços atuais são `vagas_bot_01` e `vagas_bot_02`. O projeto é montado
nos containers em `/workspace/candidaturas`, e cada agente recebe seu próprio
estado em `workspaces/<agente>/state`.

Use os comandos a partir do host:

```bash
cd /opt/agent-projects/candidaturas
docker compose ps
docker compose logs --tail=100 vagas_bot_01
docker compose restart vagas_bot_01
docker compose up -d --build vagas_bot_01
```

O noVNC do bot 01 é publicado somente em
`127.0.0.1:6081`; acesse-o de outra máquina usando túnel SSH:

```bash
ssh -L 6081:127.0.0.1:6081 <usuario>@srv1876742
```

O arquivo `app/deploy/hermes/compose.yaml` é mantido apenas como referência
de deployment e deve permanecer alinhado ao compose ativo da raiz. Não use
um caminho alternativo para profiles, estado ou workspace.

