#!/usr/bin/env sh
set -eu

interval_minutes=60
max_per_run=1
run_agent=1
model=""
variant=""
label="com.felipe.candidaturas.heartbeat"

while [ "$#" -gt 0 ]; do
  case "$1" in
    -IntervalMinutes|--interval-minutes)
      interval_minutes="$2"
      shift 2
      ;;
    -MaxPerRun|--max-per-run)
      max_per_run="$2"
      shift 2
      ;;
    -RunAgent|--run-agent)
      run_agent=1
      shift
      ;;
    --no-run-agent)
      run_agent=0
      shift
      ;;
    -Model|--model)
      model="$2"
      shift 2
      ;;
    -Variant|--variant)
      variant="$2"
      shift 2
      ;;
    -Label|--label)
      label="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [ "$(uname -s)" != "Darwin" ]; then
  echo "launchd is only available on macOS. This project is configured MacBook-first." >&2
  exit 1
fi

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
log_dir="$project_root/outputs/_logs/applications_heartbeat_v2"
mkdir -p "$log_dir" "$HOME/Library/LaunchAgents"

if [ "$run_agent" -eq 1 ]; then
  npm_script="applications:agent-heartbeat"
else
  npm_script="applications:heartbeat"
fi

program="$log_dir/${label}.sh"
plist="$HOME/Library/LaunchAgents/$label.plist"
interval_seconds=$((interval_minutes * 60))

{
  printf '#!/usr/bin/env sh\n'
  printf 'set -eu\n'
  printf 'cd %s\n' "$(printf '%s' "$project_root" | sed "s/'/'\\\\''/g; s/^/'/; s/$/'/")"
  printf 'exec npm run %s -- --max-per-run %s' "$npm_script" "$max_per_run"
  if [ -n "$model" ]; then
    printf ' --model %s' "$(printf '%s' "$model" | sed "s/'/'\\\\''/g; s/^/'/; s/$/'/")"
  fi
  if [ -n "$variant" ]; then
    printf ' --variant %s' "$(printf '%s' "$variant" | sed "s/'/'\\\\''/g; s/^/'/; s/$/'/")"
  fi
  printf '\n'
} > "$program"
chmod 700 "$program"

cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>$program</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$project_root</string>
  <key>StartInterval</key>
  <integer>$interval_seconds</integer>
  <key>RunAtLoad</key>
  <false/>
  <key>StandardOutPath</key>
  <string>$log_dir/launchd.log</string>
  <key>StandardErrorPath</key>
  <string>$log_dir/launchd.err.log</string>
</dict>
</plist>
EOF

launchctl unload "$plist" >/dev/null 2>&1 || true
launchctl load "$plist"

echo "launchd agent installed: $plist"
echo "label=$label interval_minutes=$interval_minutes max_per_run=$max_per_run run_agent=$run_agent"
echo "logs=$log_dir"
