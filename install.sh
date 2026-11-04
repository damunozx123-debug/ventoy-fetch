#!/usr/bin/env bash
# One-action installer for Ventoy Fetch. No pip dependencies or chmod required.
set -Eeuo pipefail
umask 077
APP_HOME="${VENTOY_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/ventoy-fetch}"
BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"
URL='https://raw.githubusercontent.com/damunozx123-debug/ventoy-fetch/master/ventoy_fetch.py'
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || pwd)"

if command -v pkg >/dev/null 2>&1 && [[ "${PREFIX:-}" == *com.termux* ]]; then
  pkg install -y python curl
  if [[ ! -d "$HOME/storage/shared" ]] && command -v termux-setup-storage >/dev/null 2>&1; then
    echo 'Android will ask you once for shared Downloads/storage access.'
    termux-setup-storage || echo 'Storage permission not granted. Use --output-dir under HOME instead.' >&2
  fi
fi
command -v python3 >/dev/null 2>&1 || { echo 'Python 3.10+ required (Termux: pkg install python)' >&2; exit 2; }
python3 -c 'import sys; assert sys.version_info >= (3,10)' || { echo 'Python 3.10+ required' >&2; exit 2; }
mkdir -p "$APP_HOME" "$BIN_HOME"
if [[ -f "$ROOT/ventoy_fetch.py" ]]; then
  cp -f -- "$ROOT/ventoy_fetch.py" "$APP_HOME/ventoy_fetch.py"
else
  command -v curl >/dev/null 2>&1 || { echo 'Missing curl' >&2; exit 2; }
  curl --fail --silent --show-error --location --retry 3 "$URL" -o "$APP_HOME/ventoy_fetch.py.tmp"
  mv -f -- "$APP_HOME/ventoy_fetch.py.tmp" "$APP_HOME/ventoy_fetch.py"
fi
python3 -m py_compile "$APP_HOME/ventoy_fetch.py"
cat > "$BIN_HOME/ventoy-fetch" <<'LAUNCH'
#!/usr/bin/env bash
set -Eeuo pipefail
APP_HOME="${VENTOY_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/ventoy-fetch}"
exec python3 "$APP_HOME/ventoy_fetch.py" "$@"
LAUNCH
chmod 700 "$BIN_HOME/ventoy-fetch"
printf 'Installed. Launcher: %s/ventoy-fetch\n' "$BIN_HOME"
if [[ "${VENTOY_NO_START:-0}" != 1 ]]; then
  exec "$BIN_HOME/ventoy-fetch" --gui
fi
