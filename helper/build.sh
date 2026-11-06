#!/bin/bash
# Builds bin/dock-calendar (EventKit helper) and bin/TabDock.app (launcher that owns macOS permissions).
# Needs Xcode Command Line Tools.
set -e
cd "$(dirname "$0")"
mkdir -p ../bin
swiftc -O dock-calendar.swift -o ../bin/dock-calendar \
  -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker Info.plist
codesign -s - -f -i com.jjustping.tabdock.calendar ../bin/dock-calendar 2>/dev/null || true
echo "built bin/dock-calendar"

APP=../bin/TabDock.app
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp launcher/Info.plist "$APP/Contents/Info.plist"
swiftc -O launcher/main.swift -o "$APP/Contents/MacOS/TabDock"
if [ -f ../web/icon.svg ] && [ ! -f "$APP/Contents/Resources/TabDock.icns" ]; then
  T=$(mktemp -d); qlmanage -t -s 1024 -o "$T" ../web/icon.svg >/dev/null 2>&1 || true
  if [ -f "$T/icon.svg.png" ]; then
    mkdir -p "$T/i.iconset"
    for s in 16 32 128 256 512; do
      sips -z $s $s "$T/icon.svg.png" --out "$T/i.iconset/icon_${s}x${s}.png" >/dev/null
      sips -z $((s*2)) $((s*2)) "$T/icon.svg.png" --out "$T/i.iconset/icon_${s}x${s}@2x.png" >/dev/null
    done
    iconutil -c icns "$T/i.iconset" -o "$APP/Contents/Resources/TabDock.icns" || true
  fi
fi
codesign -s - -f --deep -i com.jjustping.tabdock.app "$APP" 2>/dev/null || true
echo "built bin/TabDock.app"
