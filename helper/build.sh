#!/bin/bash
# Builds bin/dock-calendar (EventKit helper). Needs Xcode Command Line Tools.
set -e
cd "$(dirname "$0")"
mkdir -p ../bin
swiftc -O dock-calendar.swift -o ../bin/dock-calendar \
  -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker Info.plist
codesign -s - -f -i com.jjustping.tabdock.calendar ../bin/dock-calendar 2>/dev/null || true
echo "built bin/dock-calendar"
