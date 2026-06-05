# Entrega de Arquivos via rclone + OneDrive

Objetivo: qualquer máquina que rode este projeto, MacBook ou servidor Ubuntu/RPi5, consegue enviar artefatos aprovados para a mesma pasta no OneDrive.

## Estratégia

- O projeto sempre gera o arquivo localmente em `outputs/`.
- O comando de entrega faz upload para OneDrive via `rclone`.
- MacBook e celular Android apenas sincronizam/visualizam o que está na nuvem.
- Tailscale continua útil para administrar o servidor, mas não é o caminho principal de entrega de arquivos.

## Instalar rclone no Mac

```bash
brew install rclone
```

## Instalar rclone no Ubuntu/RPi5

```bash
sudo apt update
sudo apt install -y rclone
```

Se a versão do apt for antiga, usar o instalador oficial:

```bash
curl https://rclone.org/install.sh | sudo bash
```

## Configurar OneDrive em cada máquina

Rode em cada máquina:

```bash
rclone config
```

Fluxo recomendado:

1. `n` para novo remote.
2. Nome: `onedrive`.
3. Storage: escolha `Microsoft OneDrive`.
4. Siga o login OAuth no navegador.
5. Escolha OneDrive pessoal ou corporativo conforme sua conta.
6. Confirme e salve.

No RPi5 sem navegador, o `rclone` pode pedir autenticação em outra máquina. Nesse caso, siga a instrução que o próprio rclone imprimir. Normalmente ele permite gerar o token em uma máquina com navegador e colar no servidor.

## Variáveis locais do projeto

No `.env` de cada máquina, defina:

```env
RCLONE_ONEDRIVE_REMOTE=onedrive
RCLONE_ONEDRIVE_DELIVERY_DIR=01_armel/Curriculos/personalizados
```

Não coloque tokens do rclone no GitHub. A configuração real do rclone fica no perfil do usuário da máquina.

## Testar se o OneDrive responde

```bash
rclone lsd onedrive:
```

Testar a pasta de entrega:

```bash
rclone mkdir "onedrive:01_armel/Curriculos/personalizados"
rclone lsf "onedrive:01_armel/Curriculos/personalizados"
```

## Entregar um arquivo pelo projeto

Teste sem enviar de verdade:

```bash
npm run deliver:artifact -- --file outputs/<arquivo>.docx --dry-run
```

Enviar de verdade:

```bash
npm run deliver:artifact -- --file outputs/<arquivo>.docx
```

O relatório fica em:

```bash
outputs/_tmp/delivery_report.json
```

Status esperados:

- `dry_run_ok`: comando validado sem upload real.
- `delivered`: upload feito e verificado no OneDrive.
- `failed`: falhou; ver `error`, `stdout` e `stderr` no relatório.

## Comando com pasta diferente

```bash
npm run deliver:artifact -- --file outputs/<arquivo>.docx --folder "01_armel/Curriculos/personalizados/2026_06"
```

## Regra operacional

Entrega não substitui aprovação.

Para CV:

1. Gerar DOCX.
2. Validar DOCX.
3. Rodar `npm run cv:approve -- --artifact outputs/<cv>.docx`.
4. Só depois enviar:

```bash
npm run deliver:artifact -- --file outputs/<cv>.docx
```

## O que vai para GitHub

Vai:

- `scripts/deliver_artifact.py`
- `RCLONE_ONEDRIVE_DELIVERY.md`
- `package.json`
- `.env.example`

Não vai:

- `.env`
- configuração local do rclone
- tokens OAuth
- outputs sensíveis
