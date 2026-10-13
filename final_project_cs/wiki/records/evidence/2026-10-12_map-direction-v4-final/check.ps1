$ErrorActionPreference='Stop'
$env:NODE_OPTIONS='--max-old-space-size=768'
$env:TEMP=[IO.Path]::GetFullPath('../map-direction-20261012-v4/temp')
$env:TMP=$env:TEMP
& 'C:/Program Files/nodejs/node.exe' 'node_modules/typescript/bin/tsc' --noEmit *> '../map-direction-20261012-v4/type.log'
$type=$LASTEXITCODE
& 'C:/Program Files/nodejs/node.exe' 'node_modules/eslint/bin/eslint.js' src/features/map/map-geometry.ts src/features/map/map-geometry.test.ts tests/live/uiux-sonnet-map-reveal-20261012.spec.ts *> '../map-direction-20261012-v4/lint.log'
$lint=$LASTEXITCODE
& 'C:/Program Files/nodejs/node.exe' 'node_modules/vitest/vitest.mjs' run src/features/map --maxWorkers=1 --reporter=json --outputFile=../map-direction-20261012-v4/unit-results.json *> '../map-direction-20261012-v4/unit.log'
$unit=$LASTEXITCODE
& '../map-direction-20261012-v4/build-live.ps1'
$build=$LASTEXITCODE
@{type=$type;lint=$lint;unit=$unit;build=$build}|ConvertTo-Json|Set-Content '../map-direction-20261012-v4/check-status.json'
Get-Content '../map-direction-20261012-v4/check-status.json'
exit ([int]($type -ne 0 -or $lint -ne 0 -or $unit -ne 0 -or $build -ne 0))
