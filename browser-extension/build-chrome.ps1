$ErrorActionPreference = "Stop"
if (Test-Path dist-chrome) { Remove-Item -Recurse -Force dist-chrome }
Copy-Item -Recurse cennik dist-chrome
Copy-Item manifest.chrome.json dist-chrome/manifest.json
Copy-Item sw.js dist-chrome/sw.js
$polyfill = '<script src="../lib/browser-polyfill.min.js"></script>'
$i18n = '<script src="../lib/i18n.js"></script>'
$both = $polyfill + "`n" + $i18n
foreach ($f in @("popup/popup.html", "page/index.html")) {
  $path = Join-Path dist-chrome $f
  $html = Get-Content $path -Raw
  $html = $html.Replace($i18n, $both)
  Set-Content -Path $path -Value $html -NoNewline
}
Write-Host "dist-chrome ready"
