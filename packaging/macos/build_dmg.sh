#!/bin/zsh
set -euo pipefail

script_dir=${0:A:h}
project_root=${script_dir:h:h}
build_root="$project_root/build/macos"
dist_root="$project_root/dist/macos"
venv_root=${AIPET_BUILD_VENV:-"$project_root/.build-macos"}
python_command=${PYTHON:-python3}

if [[ ! -x "$venv_root/bin/python" ]]; then
  "$python_command" -m venv "$venv_root"
fi
"$venv_root/bin/python" -m pip install \
  -r "$script_dir/requirements-build.txt"

iconset="$build_root/AIpet-Murasame.iconset"
icon_file="$build_root/AIpet-Murasame.icns"
rm -rf "$iconset"
mkdir -p "$iconset" "$dist_root"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$project_root/icon.png" \
    --out "$iconset/icon_${size}x${size}.png" >/dev/null
  double_size=$((size * 2))
  sips -z "$double_size" "$double_size" "$project_root/icon.png" \
    --out "$iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$iconset" -o "$icon_file"

export AIPET_MACOS_ICON="$icon_file"
export AIPET_MACOS_UV="$venv_root/bin/uv"
gpt_sovits_source="$build_root/gpt-sovits-source.zip"
gpt_sovits_checksum="$build_root/gpt-sovits-source.sha256"
gpt_sovits_commit="d7c2210da8c013e81a94bfc7b811a477c99fd506"

# Reuse a previously verified download when the cached archive still matches
# its recorded checksum; otherwise fetch the pinned source. The codeload
# endpoint is tried first because the github.com archive redirect is blocked
# on some networks, with the standard archive URL kept as a fallback.
if [[ -f "$gpt_sovits_source" && -f "$gpt_sovits_checksum" ]] \
  && [[ "$(cat "$gpt_sovits_checksum")" == "$(shasum -a 256 "$gpt_sovits_source")" ]]; then
  echo "Reusing verified cached GPT-SoVITS source: $gpt_sovits_source"
else
  curl --fail --location --retry 3 --connect-timeout 15 --max-time 900 \
    --output "$gpt_sovits_source.partial" \
    "https://codeload.github.com/RVC-Boss/GPT-SoVITS/zip/$gpt_sovits_commit" \
    || curl --fail --location --retry 3 --connect-timeout 15 --max-time 900 \
      --output "$gpt_sovits_source.partial" \
      "https://github.com/RVC-Boss/GPT-SoVITS/archive/$gpt_sovits_commit.zip"
  mv "$gpt_sovits_source.partial" "$gpt_sovits_source"
  shasum -a 256 "$gpt_sovits_source" > "$gpt_sovits_checksum"
fi
export AIPET_MACOS_GPT_SOVITS_SOURCE="$gpt_sovits_source"
export AIPET_MACOS_GPT_SOVITS_CHECKSUM="$gpt_sovits_checksum"
overlay_binary="$build_root/aipet-fullscreen-overlay"
clang -framework Cocoa -framework CoreGraphics \
  "$project_root/aipet/platforms/macos/fullscreen_overlay.m" \
  -o "$overlay_binary"
export AIPET_MACOS_FULLSCREEN_OVERLAY="$overlay_binary"
export AIPET_MACOS_VERSION=${AIPET_MACOS_VERSION:-"2.0.4-macos.1"}
"$venv_root/bin/python" -m PyInstaller \
  --noconfirm \
  --clean \
  --workpath "$build_root/pyinstaller" \
  --distpath "$dist_root" \
  "$script_dir/AIpet-macOS.spec"

app_path="$dist_root/AIpet-Murasame.app"
codesign --force --sign - \
  "$app_path/Contents/Frameworks/tools/uv"
codesign --force --sign - \
  "$app_path/Contents/Frameworks/aipet-fullscreen-overlay/aipet-fullscreen-overlay"
codesign --force --deep --sign - "$app_path"

dmg_path="$dist_root/AIpet-Murasame.dmg"
dmg_root=$(mktemp -d "$build_root/dmg.XXXXXX")
trap 'rm -rf "$dmg_root"' EXIT
ditto "$app_path" "$dmg_root/AIpet-Murasame.app"
ln -s /Applications "$dmg_root/Applications"
hdiutil create \
  -volname "AIpet-Murasame" \
  -srcfolder "$dmg_root" \
  -format UDZO \
  -ov \
  "$dmg_path"

codesign --verify --deep --strict "$app_path"
echo "Created $dmg_path"
