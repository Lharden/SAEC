param(
  [string]$ProjectRoot = "",
  [switch]$Quiet
)

$ErrorActionPreference = "Stop"

function Resolve-ProjectRoot {
  param([string]$Override)

  if (-not [string]::IsNullOrWhiteSpace($Override)) {
    return (Resolve-Path -LiteralPath $Override).Path
  }

  return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
}

function Ensure-Directory {
  param([string]$PathValue)

  if (-not (Test-Path -LiteralPath $PathValue)) {
    New-Item -ItemType Directory -Path $PathValue -Force | Out-Null
  }
}

function Test-ReadWriteAccess {
  param([string]$PathValue)

  $probe = Join-Path $PathValue "__saec_rw_probe_$PID.tmp"
  try {
    Set-Content -LiteralPath $probe -Value "ok" -Encoding UTF8
    $null = Get-Content -LiteralPath $probe -Encoding UTF8
    Remove-Item -LiteralPath $probe -Force
  }
  catch {
    try {
      if (Test-Path -LiteralPath $probe) {
        Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
      }
    }
    catch {}
    throw @"
Permission check failed for '$PathValue'. $($_.Exception.Message)
Suggested recovery (targeted path only):
  takeown /f "$PathValue" /r /d y
  icacls "$PathValue" /grant "${env:USERNAME}:F" /t
  icacls "$PathValue" /inheritance:e /t
"@
  }
}

function Add-OptionIfMissing {
  param(
    [string]$Current,
    [string]$Option
  )

  if ([string]::IsNullOrWhiteSpace($Current)) {
    return $Option
  }
  if ($Current.Contains($Option)) {
    return $Current
  }
  return "$Current $Option"
}

function Write-PermissionBaseline {
  param(
    [string]$ProjectRootPath,
    [string]$LogDir
  )

  Ensure-Directory -PathValue $LogDir
  $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
  $baselinePath = Join-Path $LogDir "permission-baseline-$stamp.txt"

  $targets = @(
    (Join-Path $ProjectRootPath ".pytest_cache"),
    (Join-Path $ProjectRootPath "system\.pytest_tmp"),
    (Join-Path $ProjectRootPath "system\tmp_pytest_run")
  )

  $lines = [System.Collections.Generic.List[string]]::new()
  $lines.Add("SAEC permission baseline")
  $lines.Add("Generated: $(Get-Date -Format o)")
  $lines.Add("")

  foreach ($target in $targets) {
    $lines.Add("=== $target ===")
    if (-not (Test-Path -LiteralPath $target)) {
      $lines.Add("missing")
      $lines.Add("")
      continue
    }

    try {
      $item = Get-Item -LiteralPath $target -Force
      $lines.Add("Attributes : $($item.Attributes)")
      $lines.Add("Mode       : $($item.Mode)")
      $lines.Add("LastWrite  : $($item.LastWriteTime.ToString("o"))")
    }
    catch {
      $lines.Add("Get-Item failed: $($_.Exception.Message)")
    }

    try {
      $aclOutput = icacls $target 2>&1
      foreach ($row in $aclOutput) {
        $lines.Add([string]$row)
      }
    }
    catch {
      $lines.Add("icacls failed: $($_.Exception.Message)")
    }
    $lines.Add("")
  }

  Set-Content -LiteralPath $baselinePath -Value $lines -Encoding UTF8
  return $baselinePath
}

$resolvedProjectRoot = Resolve-ProjectRoot -Override $ProjectRoot
$runtimeRoot = Join-Path $resolvedProjectRoot ".runtime"
$tmpDir = Join-Path $runtimeRoot "tmp"
$pytestTempDir = Join-Path $runtimeRoot "pytest"
$pytestCacheDir = Join-Path $runtimeRoot "pytest_cache"
$pipCacheDir = Join-Path $runtimeRoot "pip-cache"

foreach ($pathValue in @($runtimeRoot, $tmpDir, $pytestTempDir, $pytestCacheDir, $pipCacheDir)) {
  Ensure-Directory -PathValue $pathValue
  Test-ReadWriteAccess -PathValue $pathValue
}

$env:SAEC_RUNTIME_ROOT = $runtimeRoot
$env:TEMP = $tmpDir
$env:TMP = $tmpDir
$env:PIP_CACHE_DIR = $pipCacheDir

$pytestOpts = $env:PYTEST_ADDOPTS
if ($pytestOpts -notmatch "--basetemp=") {
  $pytestOpts = Add-OptionIfMissing -Current $pytestOpts -Option "--basetemp=""$pytestTempDir"""
}
if ($pytestOpts -notmatch "cache_dir=") {
  $pytestOpts = Add-OptionIfMissing -Current $pytestOpts -Option "-o cache_dir=""$pytestCacheDir"""
}
if ($null -eq $pytestOpts) {
  $pytestOpts = ""
}
$env:PYTEST_ADDOPTS = $pytestOpts.Trim()

$logDir = Join-Path $resolvedProjectRoot "system\logs"
$baseline = Write-PermissionBaseline -ProjectRootPath $resolvedProjectRoot -LogDir $logDir

if (-not $Quiet) {
  Write-Host "[runtime] Project root : $resolvedProjectRoot"
  Write-Host "[runtime] Runtime root : $runtimeRoot"
  Write-Host "[runtime] TEMP/TMP     : $tmpDir"
  Write-Host "[runtime] PIP cache    : $pipCacheDir"
  Write-Host "[runtime] PYTEST opts  : $($env:PYTEST_ADDOPTS)"
  Write-Host "[runtime] Baseline log : $baseline"
}

