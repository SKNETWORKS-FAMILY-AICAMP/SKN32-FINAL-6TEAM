param([string]$Docx,[string]$Pdf)
# Word(COM)로 docx 를 PDF 로 바꾼다. 원본은 읽기 전용으로 연다.
$w = New-Object -ComObject Word.Application
$w.Visible = $false
$w.DisplayAlerts = 0
try {
  $d = $w.Documents.Open($Docx, $false, $true)
  $d.ExportAsFixedFormat($Pdf, 17)
  $d.Close($false)
} finally { $w.Quit() }
