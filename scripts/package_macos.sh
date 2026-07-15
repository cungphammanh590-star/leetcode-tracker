#!/usr/bin/env bash
# 打包 macOS 发行包：解压后仅含「LeetCode Tracker.app」+「extension」
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(python3 -c "from leetcode_tracker import __version__; print(__version__)" 2>/dev/null || echo "0.1.1")"
STAGE="$ROOT/release/stage"
OUT_DIR="$ROOT/release"
DIST_NAME="LeetCode-Tracker-macOS-v${VERSION}"
BUNDLE="$STAGE/$DIST_NAME"
APP_NAME="LeetCode Tracker"

cd "$ROOT"

echo "==> 安装打包依赖"
python3 -m pip install -e '.[app,packaging]' -q

echo "==> 清理旧产物"
rm -rf "$STAGE" "$ROOT/build" "$ROOT/dist"
mkdir -p "$BUNDLE"

echo "==> PyInstaller 构建 .app"
# 避开 conda 环境里误卷入的 Qt/PyQt（pywebview 在 macOS 用 Cocoa/WebKit 即可）
python3 -m PyInstaller \
  --noconfirm \
  --windowed \
  --name "$APP_NAME" \
  --paths "$ROOT" \
  --hidden-import webview \
  --hidden-import leetcode_tracker \
  --collect-submodules webview \
  --exclude-module PyQt5 \
  --exclude-module PyQt6 \
  --exclude-module PySide2 \
  --exclude-module PySide6 \
  --exclude-module qtpy \
  --exclude-module PyQt5.QtCore \
  --exclude-module PyQt5.QtWidgets \
  --exclude-module PyQt5.QtWebEngineWidgets \
  --add-data "$ROOT/leetcode_tracker/static:leetcode_tracker/static" \
  "$ROOT/desktop_entry.py"

APP_SRC="$ROOT/dist/${APP_NAME}.app"
if [[ ! -d "$APP_SRC" ]]; then
  echo "未找到 $APP_SRC" >&2
  exit 1
fi

echo "==> 组装发行目录（不含 openspec / node_modules / 源码树）"
cp -R "$APP_SRC" "$BUNDLE/"
mkdir -p "$BUNDLE/extension"
rsync -a --delete \
  --exclude '.DS_Store' \
  "$ROOT/extension/" "$BUNDLE/extension/"

cat > "$BUNDLE/使用说明.txt" << EOF
LeetCode Tracker v${VERSION}（仅支持 leetcode.cn）

解压后你会看到两项：
  1) LeetCode Tracker.app  — 本机服务 + 桌面仪表盘
  2) extension/            — Chrome / Edge 浏览器扩展

使用步骤：
  1. 双击打开「LeetCode Tracker.app」
     （若系统提示无法验证开发者：右键 → 打开）
  2. 浏览器打开 chrome://extensions（或 edge://extensions）
     开启「开发者模式」→「加载已解压的扩展程序」→ 选择本目录下的 extension 文件夹
  3. 打开 leetcode.cn 题目页正常提交；扩展会写入本机，桌面窗口可看进度

数据保存在本机：
  库：~/.local/share/leetcode-tracker/leetcode.db
  配置：~/.config/leetcode-tracker/config.json
  日报：~/leetcode-reports/

本压缩包不含 openspec 等开发文件。
EOF

echo "==> 打 zip"
mkdir -p "$OUT_DIR"
ZIP="$OUT_DIR/${DIST_NAME}.zip"
rm -f "$ZIP"
(
  cd "$STAGE"
  zip -qry "$ZIP" "$DIST_NAME"
)

echo "==> 完成: $ZIP"
echo "内容预览:"
find "$BUNDLE" -maxdepth 2 \( -name '*.app' -o -type d -o -name '*.txt' \) | head -20
