$ErrorActionPreference='Stop'
$workspace='C:/Users/playdata2/Documents/final_workspace'
$task=Join-Path $workspace '.tmp/map-direction-20261012-v4'
$repo=Join-Path $workspace 'final_project_cs'
$mock=Join-Path $repo 'frontend/apps/web/mockups/map-reveal-continuity-2026-10-12-v4'
$record=Join-Path $repo 'wiki/records/evidence/2026-10-12_map-direction-v4-final'
if(Test-Path -LiteralPath $record){throw '기존 증거 폴더를 덮어쓰지 않습니다'}
New-Item -ItemType Directory -Path $record | Out-Null
$report=Get-Content (Join-Path $task 'browser-final-results.json') -Raw|ConvertFrom-Json
$rows=[Collections.Generic.List[object]]::new()
function Read-Suite($suite){
 foreach($spec in $suite.specs){
  foreach($test in $spec.tests){
   $result=$test.results[-1]
   $video=$result.attachments|Where-Object name -eq 'video'|Select-Object -First 1
   $dir=if($video){Split-Path $video.path}else{$null}
   $width=if($spec.title -match '1280px'){1280}else{375}
   $name=if($spec.title -like '*첫 마커부터*'){"first-$width.png"}elseif($spec.title -like '*서쪽 두 일정*'){"same-west-$width.png"}elseif($spec.title -like '*서쪽 1번·동쪽 2번*'){"third-$width.png"}else{$null}
   if($name){
    $png=@(Get-ChildItem -LiteralPath $dir -File -Filter '*.png')
    if($png.Count -ne 1){throw "촬영 파일 수가 예상과 다릅니다: $($spec.title)"}
    Copy-Item -LiteralPath $png[0].FullName -Destination (Join-Path $mock $name)
    if($name -like 'third-*'){Copy-Item -LiteralPath $video.path -Destination (Join-Path $mock "reveal-$width.webm")}
   }
   $proofs=@()
   foreach($attachment in $result.attachments|Where-Object contentType -eq 'application/json'){
    $decoded=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($attachment.body))|ConvertFrom-Json
    $proofs+=@{name=$attachment.name;data=$decoded}
   }
   $rows.Add(@{title=$spec.title;status=$result.status;proofs=$proofs;image=$name})
  }
 }
 foreach($child in $suite.suites){Read-Suite $child}
}
foreach($suite in $report.suites){Read-Suite $suite}
$rows|ConvertTo-Json -Depth 15|Set-Content (Join-Path $record 'frame-proofs.json') -Encoding utf8
foreach($file in @('before-unit.log','after-unit.log','unit-results.json','unit.log','type.log','lint.log','build.log','check-status.json','build-live.log','build-live-status.json','browser-final-results.json','browser-final.log','browser.log','static-final-status.json','type-final.log','lint-final.log','check.ps1','build-live.ps1','browser.ps1')){Copy-Item -LiteralPath (Join-Path $task $file) -Destination $record}
$sourceFiles=@('frontend/apps/web/src/features/map/map-geometry.ts','frontend/apps/web/src/features/map/map-geometry.test.ts','frontend/apps/web/tests/live/uiux-sonnet-map-reveal-20261012.spec.ts')
$hashes=foreach($relative in $sourceFiles){
 $rootFile=Join-Path $repo $relative
 $snapshotFile=Join-Path $workspace ('.tmp/uiux-visual-20261012-v1/'+$relative.Replace('frontend/apps/web/',''))
 $hash=(Get-FileHash -LiteralPath $rootFile).Hash
 $snapshotHash=(Get-FileHash -LiteralPath $snapshotFile).Hash
 if($hash -ne $snapshotHash){throw "검사 사본과 다른 지도 파일: $relative"}
 $dest=Join-Path $record ('source/'+$relative)
 New-Item -ItemType Directory -Path (Split-Path $dest) -Force|Out-Null
 Copy-Item -LiteralPath $rootFile -Destination $dest
 @{path=$relative;rootHash=$hash;testedHash=$snapshotHash}
}
$hashes|ConvertTo-Json -Depth 4|Set-Content (Join-Path $record 'source-match.json') -Encoding utf8
Copy-Item -LiteralPath (Join-Path $task 'backup') -Destination (Join-Path $record '_backup/2026-10-12_before-direction-fix') -Recurse
$media=Get-ChildItem -LiteralPath $mock -File|Where-Object Extension -in '.png','.webm'|ForEach-Object{@{file=$_.Name;bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName).Hash}}
$media|ConvertTo-Json -Depth 4|Set-Content (Join-Path $mock 'capture-manifest.json') -Encoding utf8
Write-Output "RESULTS=$($rows.Count) MEDIA=$($media.Count) SOURCE_MATCH=$($hashes.Count)"

