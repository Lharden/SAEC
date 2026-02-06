param(
  [string]$Version = (Get-Date -Format "yyyy.MM.dd-HHmm"),
  [switch]$SkipExeBuild
)

$ErrorActionPreference = "Stop"

function Resolve-IsccPath {
  $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }

  $candidates = @(
    (Join-Path $Env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
  )
  foreach ($path in $candidates) {
    if (Test-Path $path) { return $path }
  }
  return $null
}

function Ensure-Artifact([string]$PathValue) {
  if (-not (Test-Path $PathValue)) {
    throw "Arquivo obrigatorio ausente: $PathValue"
  }
}

Write-Host "============================================"
Write-Host " SAEC-OG - Build Installer"
Write-Host "============================================"

Set-Location $PSScriptRoot

if (-not $SkipExeBuild) {
  Write-Host "[1/4] Gerando executaveis (.exe)..."
  & .\build_exe.bat
}
else {
  Write-Host "[1/4] Pulando build de executaveis (--SkipExeBuild)"
}

Ensure-Artifact ".\dist\SAEC-OG.exe"
Ensure-Artifact ".\dist\SAEC-OG-CLI.exe"

$iscc = Resolve-IsccPath
if ($iscc) {
  Write-Host "[2/4] Inno Setup encontrado: $iscc"
  Write-Host "[3/4] Gerando instalador .exe..."
  & $iscc "/DMyAppVersion=$Version" ".\installer\SAEC-OG.iss"

  Write-Host "[4/4] Instalador pronto em .\dist\installer"
  Get-ChildItem .\dist\installer | Select-Object Name, Length, LastWriteTime
  exit 0
}

Write-Warning "Inno Setup (ISCC.exe) nao encontrado. Gerando pacote portatil .zip como fallback."
Write-Host "[2/4] Criando pasta de release..."

$portableDir = ".\dist\installer\SAEC-OG-portable-$Version"
if (Test-Path $portableDir) { Remove-Item $portableDir -Recurse -Force }
New-Item -ItemType Directory -Path $portableDir | Out-Null

Copy-Item .\dist\SAEC-OG.exe $portableDir
Copy-Item .\dist\SAEC-OG-CLI.exe $portableDir
Copy-Item .\README.md $portableDir
Copy-Item .\.env.template $portableDir
Copy-Item .\prompts "$portableDir\prompts" -Recurse

Write-Host "[3/4] Compactando pacote..."
$zipPath = ".\dist\installer\SAEC-OG-portable-$Version.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path "$portableDir\*" -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host "[4/4] Fallback pronto: $zipPath"
Write-Host "Para gerar instalador .exe, instale Inno Setup 6 e rode novamente este script."
