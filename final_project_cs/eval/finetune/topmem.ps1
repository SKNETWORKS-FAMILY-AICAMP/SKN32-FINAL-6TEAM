Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 ProcessName, Id, @{Name='MB';Expression={[math]::Round($_.WorkingSet64/1MB)}} | Format-Table -AutoSize
