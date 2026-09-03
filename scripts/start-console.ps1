$Root = Split-Path -Parent $PSScriptRoot

Set-Location $Root

& "$Root\.venv\Scripts\python.exe" `
    "$Root\app.py"
