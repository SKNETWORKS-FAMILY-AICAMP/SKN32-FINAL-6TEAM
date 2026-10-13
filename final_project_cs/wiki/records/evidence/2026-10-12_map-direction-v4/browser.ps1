$ErrorActionPreference='Stop'
$env:STUB_PORT='8187'
$env:LIVE_PORT='3187'
$env:PLAYWRIGHT_CHANNEL='chrome'
$env:NODE_OPTIONS='--max-old-space-size=768'
$env:LIVE_SKIP_BUILD='1'
$env:REVEAL_CAPTURE='1'
& 'C:/Program Files/nodejs/node.exe' 'node_modules/@playwright/test/cli.js' test -c playwright.direction-v4.config.ts uiux-sonnet-map-reveal-20261012.spec.ts checking-read-list-20261012.spec.ts map-reveal-continuity-20261012.spec.ts *> '../map-direction-20261012-v4/browser.log'
$taskExit=$LASTEXITCODE
Write-Output "BROWSER_EXIT=$taskExit"
exit $taskExit
