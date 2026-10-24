# Build dist\BoiDryTwin.exe (one file; Windows). Usage: powershell -File scripts\build_exe.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
uv sync --extra web --group build
uv run --extra web --group build pyinstaller --noconfirm --clean --distpath dist --workpath build packaging\BoiDryTwin.spec
Write-Output "built: $(Resolve-Path dist\BoiDryTwin.exe)"
