#!/bin/bash
# TabDock installer: venv + calendar helper + LaunchAgent (autostart at login).
#   ./install.sh              install / update and (re)start
#   ./install.sh --port 9000  use another port
#   ./install.sh --uninstall  stop and remove the LaunchAgent (data/ is kept)
#   ./install.sh --status     show whether it runs and the tablet URL
set -euo pipefail

LABEL="com.jjustping.tabdock"
DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOGDIR="$HOME/Library/Logs/TabDock"
PORT=8787
ACTION=install

while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --uninstall) ACTION=uninstall; shift ;;
    --status) ACTION=status; shift ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) echo "Unknown option $1"; exit 1 ;;
  esac
done

say() { printf "\033[1;36m▸\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m!\033[0m %s\n" "$*"; }

case "$DIR" in
  "$HOME/Desktop"*|"$HOME/Documents"*|"$HOME/Downloads"*)
    warn "Проект лежит в $DIR — macOS не даёт фоновым службам читать Рабочий стол/Документы/Загрузки."
    warn "Лучше перенести папку, например в ~/tabdock, и запустить install.sh оттуда." ;;
esac

if [ "$ACTION" = uninstall ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  say "LaunchAgent удалён. Данные остались в $DIR/data"
  exit 0
fi

if [ "$ACTION" = status ]; then
  launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null | grep -E "state|pid" | head -3 || echo "не запущен"
  "$DIR/.venv/bin/python" "$DIR/server.py" --port "$PORT" --print-url 2>/dev/null || true
  exit 0
fi

# 1. Python + venv (system python3 from Command Line Tools is enough)
PY=/usr/bin/python3
if ! "$PY" -c 'import sys; assert sys.version_info >= (3, 9)' 2>/dev/null; then
  say "Нужны Command Line Tools (python3). Запускаю установку…"
  xcode-select --install || true
  echo "После установки запустите ./install.sh ещё раз."; exit 1
fi
if [ ! -x "$DIR/.venv/bin/python" ]; then
  say "Создаю venv"
  "$PY" -m venv "$DIR/.venv"
fi
say "Ставлю зависимости (qrcode)"
if [ -d "$DIR/.wheels" ]; then   # offline install (Mac without internet): wheels copied next to the project
  "$DIR/.venv/bin/pip" install -q --disable-pip-version-check --no-index --find-links "$DIR/.wheels" -r "$DIR/requirements.txt"
else
  "$DIR/.venv/bin/pip" install -q --disable-pip-version-check -r "$DIR/requirements.txt"
fi

# 2. Calendar helper (EventKit)
if command -v swiftc >/dev/null; then
  say "Собираю помощник календаря"
  "$DIR/helper/build.sh" >/dev/null && echo "  ok: bin/dock-calendar, bin/TabDock.app" || warn "не удалось собрать помощники — календарь через AppleScript"
else
  warn "swiftc не найден — календарь через AppleScript"
fi

# 3. LaunchAgent
mkdir -p "$HOME/Library/LaunchAgents" "$LOGDIR"
LAUNCHER="$DIR/bin/TabDock.app/Contents/MacOS/TabDock"
[ -x "$LAUNCHER" ] || LAUNCHER="/usr/bin/env"      # no Swift: run python directly
sed -e "s|@LABEL@|$LABEL|g" -e "s|@LAUNCHER@|$LAUNCHER|g" -e "s|@PY@|$DIR/.venv/bin/python|g" -e "s|@DIR@|$DIR|g" \
    -e "s|@PORT@|$PORT|g" -e "s|@LOG@|$LOGDIR|g" "$DIR/launchd/tabdock.plist.in" > "$PLIST"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
sleep 1
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/$LABEL"
say "Служба запущена и будет стартовать при входе в macOS"

# 4. Wait for it and show the URL
for i in $(seq 1 20); do
  curl -fsS "http://localhost:$PORT/api/state" >/dev/null 2>&1 && break
  sleep 0.5
done
if curl -fsS "http://localhost:$PORT/api/state" >/dev/null 2>&1; then
  URL=$("$DIR/.venv/bin/python" "$DIR/server.py" --port "$PORT" --print-url)
  say "Готово!  На Mac: http://localhost:$PORT"
  say "Планшет: отсканируйте QR (кнопка ▦) или откройте $URL"
  open "http://localhost:$PORT" || true
else
  warn "Сервер не ответил. Лог: $LOGDIR/tabdock.err.log"
  tail -20 "$LOGDIR/tabdock.err.log" 2>/dev/null || true
  exit 1
fi
