#!/bin/sh
set -e
rm -rf dist-chrome
mkdir dist-chrome
cp -r _locales icons lib content popup page background.js dist-chrome/
cp manifest.chrome.json dist-chrome/manifest.json
cp sw.js dist-chrome/sw.js
cp ../licenses/Cennik.LICENSE dist-chrome/LICENSE
cp NOTICE.md dist-chrome/NOTICE.md
# Chrome-only: polyfill in popup/page (Firefox keeps native browser.*)
for f in popup/popup.html page/index.html; do
  sed -i 's|<script src="../lib/i18n.js"></script>|<script src="../lib/browser-polyfill.min.js"></script>\n<script src="../lib/i18n.js"></script>|' "dist-chrome/$f"
done
