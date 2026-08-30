Get-Process | Where-Object { $_.ProcessName -like '*python*' -or $_.ProcessName -like '*vmmem*' } |
    Select-Object Id, ProcessName, @{Name='MB';Expression={[math]::Round($_.WorkingSet64/1MB)}} |
    Format-Table -AutoSize
