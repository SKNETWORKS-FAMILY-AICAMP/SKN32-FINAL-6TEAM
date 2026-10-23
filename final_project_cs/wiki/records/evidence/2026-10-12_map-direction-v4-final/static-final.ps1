$ErrorActionPreference='Stop'
$env:NODE_OPTIONS='--max-old-space-size=768'
& 'C:/Program Files/nodejs/node.exe' 'node_modules/typescript/bin/tsc' --noEmit *> '../map-direction-20261012-v4/type-final.log'
$type=$LASTEXITCODE
& 'C:/Program Files/nodejs/node.exe' 'node_modules/eslint/bin/eslint.js' src/features/map/map-geometry.ts src/features/map/map-geometry.test.ts tests/live/uiux-sonnet-map-reveal-20261012.spec.ts *> '../map-direction-20261012-v4/lint-final.log'
$lint=$LASTEXITCODE
@{type=$type;lint=$lint}|ConvertTo-Json|Set-Content '../map-direction-20261012-v4/static-final-status.json'
Get-Content '../map-direction-20261012-v4/static-final-status.json'
exit ([int]($type -ne 0 -or $lint -ne 0))
