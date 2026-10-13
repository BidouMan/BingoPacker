#!/usr/bin/env bash
# 用 hdiutil 把 .app 打成 .dmg（不依赖 create-dmg 等第三方工具）
#
# 用法: make_dmg.sh <app路径> <输出dmg路径> [卷名]
set -euo pipefail

APP="${1:?usage: make_dmg.sh <app> <out.dmg> [volume_name]}"
OUT="${2:?usage: make_dmg.sh <app> <out.dmg> [volume_name]}"
VOLNAME="${3:-$(basename "${APP%.app}")}"

[ -d "$APP" ] || { echo "error: app bundle not found: $APP" >&2; exit 1; }

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

rm -f "$OUT"
hdiutil create \
  -volname "$VOLNAME" \
  -srcfolder "$STAGE" \
  -ov -format UDZO \
  "$OUT"

echo "created: $OUT"
