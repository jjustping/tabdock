#!/bin/bash
# Builds android/build/TabDock.apk without Gradle: aapt2 + javac + d8 + apksigner.
# Needs: Android SDK (build-tools, one platform) and JDK 17.
#   ANDROID_HOME=~/Library/Android/sdk JAVA_HOME=/opt/homebrew/opt/openjdk@17 ./android/build.sh
set -euo pipefail
cd "$(dirname "$0")"
SDK="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
BT="$SDK/build-tools/$(ls "$SDK/build-tools" | sort -V | tail -1)"
PLATFORM="$SDK/platforms/$(ls "$SDK/platforms" | sort -V | tail -1)/android.jar"
JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk@17}"
export PATH="$JAVA_HOME/bin:$PATH"
OUT=build; rm -rf "$OUT"; mkdir -p "$OUT"/{res,gen,classes,dex,apk}

cp ../web/connect.js assets/connect.js          # same discovery code as the web login page
"$BT/aapt2" compile --dir res -o "$OUT/res/res.zip"
"$BT/aapt2" link -o "$OUT/apk/base.apk" -I "$PLATFORM" --manifest AndroidManifest.xml \
  -A assets --java "$OUT/gen" --min-sdk-version 26 --target-sdk-version 35 "$OUT/res/res.zip"
javac --release 11 -nowarn -Xlint:none -classpath "$PLATFORM" -d "$OUT/classes" \
  $(find src "$OUT/gen" -name '*.java')
"$BT/d8" --min-api 26 --release --lib "$PLATFORM" --output "$OUT/dex" $(find "$OUT/classes" -name '*.class')
(cd "$OUT/dex" && zip -q -j ../apk/base.apk classes.dex)
"$BT/zipalign" -f -p 4 "$OUT/apk/base.apk" "$OUT/apk/aligned.apk"

KS="${TABDOCK_KEYSTORE:-$HOME/.android/tabdock-release.keystore}"
if [ ! -f "$KS" ]; then
  mkdir -p "$(dirname "$KS")"
  keytool -genkeypair -keystore "$KS" -storepass tabdock -keypass tabdock -alias tabdock \
    -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=TabDock" >/dev/null 2>&1
  echo "created signing key $KS (keep it to be able to update the app)"
fi
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:tabdock --key-pass pass:tabdock --ks-key-alias tabdock \
  --out "$OUT/TabDock.apk" "$OUT/apk/aligned.apk"
echo "OK: android/$OUT/TabDock.apk ($(du -h "$OUT/TabDock.apk" | cut -f1))"
