#!/usr/bin/env bash
# TabDock installer for Linux: packages + venv + systemd user service (autostart at login).
#   ./install-linux.sh              install / update and (re)start
#   ./install-linux.sh --port 9000  use another port
#   ./install-linux.sh --no-packages  skip apt/dnf/pacman (everything is already installed)
#   ./install-linux.sh --uninstall  stop and remove the service (data/ is kept)
#   ./install-linux.sh --status     show whether it runs and the address for the tablet
#   ./install-linux.sh --keys       also let «Свои кнопки» press key combinations (Wayland: ydotool, needs a re-login)
# Tested on Ubuntu 26.04 (GNOME). Debian, Fedora and Arch use the same steps with their package manager.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT="$UNIT_DIR/tabdock.service"
PORT=8787
ACTION=install
PACKAGES=1
KEYS=0

while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --uninstall) ACTION=uninstall; shift ;;
    --status) ACTION=status; shift ;;
    --no-packages) PACKAGES=0; shift ;;
    --keys) KEYS=1; shift ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "Неизвестный параметр $1"; exit 1 ;;
  esac
done

say()  { printf "\033[1;36m▸\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m!\033[0m %s\n" "$*"; }
die()  { printf "\033[1;31m✗\033[0m %s\n" "$*"; exit 1; }

[ "$(uname -s)" = "Linux" ] || die "Это установщик для Linux. На Mac: ./install.sh"
[ "$(id -u)" -ne 0 ] || die "Запускайте от своего пользователя, без sudo — sudo спросится сам, когда понадобится."
command -v systemctl >/dev/null || die "Нужен systemd (есть в Ubuntu, Debian, Fedora, Arch)."

if [ "$ACTION" = uninstall ]; then
  systemctl --user disable --now tabdock.service tabdock-tray.service tabdock-keys.service 2>/dev/null || true
  rm -f "$UNIT" "$UNIT_DIR/tabdock-tray.service" "$UNIT_DIR/tabdock-keys.service"; systemctl --user daemon-reload
  say "Служба удалена. Данные остались в $DIR/data"
  exit 0
fi

if [ "$ACTION" = status ]; then
  systemctl --user --no-pager status tabdock.service | head -5 || true
  "$DIR/.venv/bin/python" "$DIR/server.py" --port "$PORT" --print-url 2>/dev/null || true
  exit 0
fi

# 1. Packages: Python, Bonjour (Avahi), media keys (playerctl), volume (PipeWire), disks (udisks2), icons (rsvg)
if [ "$PACKAGES" = 1 ]; then
  if command -v apt-get >/dev/null; then
    PKGS="python3 python3-venv curl openssl libnotify-bin avahi-daemon avahi-utils playerctl wireplumber udisks2 lm-sensors librsvg2-bin gnome-screenshot python3-gi gir1.2-ayatanaappindicator3-0.1 wl-clipboard xclip xdotool"
    say "Ставлю пакеты (apt): $PKGS"
    sudo apt-get update -qq && sudo apt-get install -y -qq $PKGS
  elif command -v dnf >/dev/null; then
    PKGS="python3 curl openssl libnotify avahi avahi-tools playerctl wireplumber udisks2 lm_sensors librsvg2-tools gnome-screenshot python3-gobject libayatana-appindicator-gtk3 wl-clipboard xclip xdotool"
    say "Ставлю пакеты (dnf): $PKGS"
    sudo dnf install -y -q $PKGS
  elif command -v pacman >/dev/null; then
    PKGS="python curl openssl libnotify avahi playerctl wireplumber udisks2 lm_sensors librsvg python-gobject libayatana-appindicator wl-clipboard xclip xdotool"
    say "Ставлю пакеты (pacman): $PKGS"
    sudo pacman -S --needed --noconfirm $PKGS
  else
    warn "Не знаю ваш пакетный менеджер. Поставьте сами: python3 (3.9+), venv, avahi, playerctl, wireplumber, udisks2"
  fi
  command -v avahi-daemon >/dev/null && sudo systemctl enable --now avahi-daemon >/dev/null 2>&1 || true
fi

# 1b. Key combinations from the tablet under Wayland (opt-in: lets the user's programs type into any window)
if [ "$KEYS" = 1 ]; then
  say "Включаю нажатия клавиш с планшета (ydotool)"
  if command -v apt-get >/dev/null; then sudo apt-get install -y -qq ydotool
  elif command -v dnf >/dev/null; then sudo dnf install -y -q ydotool
  elif command -v pacman >/dev/null; then sudo pacman -S --needed --noconfirm ydotool; fi
  echo 'KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"' | sudo tee /etc/udev/rules.d/80-tabdock-uinput.rules >/dev/null
  sudo modprobe uinput 2>/dev/null || true
  sudo udevadm control --reload-rules && sudo udevadm trigger --name-match=uinput 2>/dev/null || true
  if ! id -nG "$USER" | grep -qw input; then
    sudo usermod -aG input "$USER"
    NEED_RELOGIN=1
  fi
fi

command -v openssl >/dev/null || die "Нужна команда openssl: без неё TabDock не сможет включить HTTPS для устройств"

# 2. Python venv
PY="$(command -v python3 || true)"
[ -n "$PY" ] && "$PY" -c 'import sys; assert sys.version_info >= (3, 9)' 2>/dev/null || die "Нужен Python 3.9 или новее"
if [ ! -x "$DIR/.venv/bin/python" ]; then
  say "Создаю venv"
  "$PY" -m venv "$DIR/.venv" || die "Не получилось создать venv (Ubuntu/Debian: sudo apt install python3-venv)"
fi
say "Ставлю зависимости Python (qrcode)"
"$DIR/.venv/bin/pip" install -q --disable-pip-version-check -r "$DIR/requirements.txt"

# 3. systemd user service: starts when you log in, restarts if it crashes
mkdir -p "$UNIT_DIR" "$HOME/.config/tabdock/commands"
cat > "$UNIT" <<EOF
[Unit]
Description=TabDock — dock for a tablet or phone
After=graphical-session.target network-online.target
PartOf=graphical-session.target

[Service]
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python $DIR/server.py --port $PORT
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=LANG=ru_RU.UTF-8
Environment=YDOTOOL_SOCKET=%t/.ydotool_socket

[Install]
WantedBy=graphical-session.target
EOF
if command -v ydotoold >/dev/null; then   # key presses daemon (installed with --keys)
  cat > "$UNIT_DIR/tabdock-keys.service" <<EOF
[Unit]
Description=TabDock key presses (ydotoold)
PartOf=graphical-session.target

[Service]
ExecStart=$(command -v ydotoold) --socket-path=%t/.ydotool_socket --socket-own=%U:%G
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
EOF
fi
# tray icon (system python3 with PyGObject; needs a desktop session)
cat > "$UNIT_DIR/tabdock-tray.service" <<EOF
[Unit]
Description=TabDock tray icon
After=graphical-session.target
PartOf=graphical-session.target

[Service]
ExecStart=/usr/bin/python3 $DIR/dock/linux/tray.py $PORT
Restart=on-failure
RestartSec=10

[Install]
WantedBy=graphical-session.target
EOF
systemctl --user daemon-reload
systemctl --user enable tabdock.service >/dev/null 2>&1
systemctl --user restart tabdock.service
if [ -f "$UNIT_DIR/tabdock-keys.service" ]; then
  systemctl --user enable tabdock-keys.service >/dev/null 2>&1
  systemctl --user restart tabdock-keys.service 2>/dev/null || true
fi
say "Служба запущена и будет стартовать при входе в систему (systemctl --user status tabdock)"
if /usr/bin/python3 -c 'import gi' 2>/dev/null; then
  systemctl --user enable tabdock-tray.service >/dev/null 2>&1
  if systemctl --user restart tabdock-tray.service 2>/dev/null; then
    say "Значок TabDock — в трее (верхняя панель)"
  else
    warn "Значок в трее не запустился (нет графического сеанса?) — запустится при следующем входе"
  fi
else
  warn "Нет python3-gi — значка в трее не будет (sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1)"
fi

# 4. Firewall: let the home network in (only if ufw is active)
if command -v ufw >/dev/null; then
  if sudo ufw status 2>/dev/null | grep -q "Status: active"; then
    printf "Файрвол ufw включён. Открыть порт %s и mDNS только для домашних сетей? [Y/n] " "$PORT"
    read -r ans || ans=y
    if [ -z "$ans" ] || [ "$ans" = y ] || [ "$ans" = Y ]; then
      for net in 192.168.0.0/16 10.0.0.0/8 172.16.0.0/12; do
        sudo ufw allow from "$net" to any port "$PORT" proto tcp comment TabDock >/dev/null
        sudo ufw allow from "$net" to any port 5353 proto udp comment "TabDock mDNS" >/dev/null
      done
      say "ufw: порт $PORT открыт для домашних сетей"
    fi
  fi
fi

# 5. Wait for it and show the address + QR code
for _ in $(seq 1 30); do
  curl -fsS "http://localhost:$PORT/api/hello" >/dev/null 2>&1 && break
  sleep 0.5
done
if curl -fsS "http://localhost:$PORT/api/hello" >/dev/null 2>&1; then
  URL=$("$DIR/.venv/bin/python" "$DIR/server.py" --port "$PORT" --print-url)
  say "Готово!  На этом компьютере: http://localhost:$PORT"
  say "Планшет или телефон: в приложении TabDock нажмите «Сканировать QR-код» и наведите камеру на этот код —"
  "$DIR/.venv/bin/python" - "$URL" <<'PY'
import sys, qrcode
q = qrcode.QRCode(border=1); q.add_data(sys.argv[1]); q.print_ascii(invert=True)
PY
  say "Затем откройте панель http://localhost:$PORT и нажмите «Разрешить»: новое устройство работает только после этого."
  say "Если приложение уже стояло до версии 0.13, удалите его и поставите новое: у него новый ключ подписи."
  say "Свои команды для виджета «Команды»: исполняемые скрипты в ~/.config/tabdock/commands/"
  if [ "${NEED_RELOGIN:-0}" = 1 ]; then
    warn "Чтобы кнопки могли нажимать клавиши, выйдите из системы и войдите снова (один раз)."
  elif [ "$KEYS" = 0 ] && [ "$(loginctl show-session "$(loginctl | awk -v u="$USER" '$3==u{print $1; exit}')" -p Type --value 2>/dev/null)" = wayland ]; then
    say "Сочетания клавиш с планшета под Wayland включаются отдельно: ./install-linux.sh --keys"
  fi
else
  warn "Сервер не ответил. Журнал: journalctl --user -u tabdock -n 50"
  journalctl --user -u tabdock -n 20 --no-pager 2>/dev/null || true
  exit 1
fi
