param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$bootstrap = Join-Path $PSScriptRoot "scripts\bootstrap_runtime.ps1"
if (-not (Test-Path -LiteralPath $bootstrap)) {
  throw "Bootstrap script nao encontrado: $bootstrap"
}
& $bootstrap -ProjectRoot $projectRoot

$pythonExe = ""
if (Test-Path -LiteralPath ".venv\Scripts\python.exe") {
  $pythonExe = (Resolve-Path -LiteralPath ".venv\Scripts\python.exe").Path
}
elseif (Test-Path -LiteralPath "..\.venv\Scripts\python.exe") {
  $pythonExe = (Resolve-Path -LiteralPath "..\.venv\Scripts\python.exe").Path
}
else {
  throw "Ambiente virtual nao encontrado em system\.venv ou ..\.venv. Execute setup.bat primeiro."
}

function Test-HasPytestTarget {
  param(
    [string[]]$ArgsList
  )

  if (-not $ArgsList -or $ArgsList.Count -eq 0) {
    return $false
  }

  $optionsWithValue = @(
    "-k",
    "-m",
    "-o",
    "-c",
    "--maxfail",
    "--durations",
    "--basetemp",
    "--cache-dir",
    "--rootdir",
    "--confcutdir",
    "--override-ini",
    "--ignore",
    "--ignore-glob"
  )

  $skipNext = $false
  foreach ($arg in $ArgsList) {
    if ($skipNext) {
      $skipNext = $false
      continue
    }

    if ($optionsWithValue -contains $arg) {
      $skipNext = $true
      continue
    }

    if ($arg.StartsWith("--") -and $arg.Contains("=")) {
      continue
    }

    if ($arg.StartsWith("-")) {
      continue
    }

    $normalized = $arg.Replace('\', '/')
    if (
      $normalized.Contains("/") -or
      $normalized.Contains("::") -or
      $normalized.EndsWith(".py") -or
      $normalized -eq "system" -or
      $normalized -eq "tests"
    ) {
      return $true
    }
  }

  return $false
}

if ($PytestArgs -and $PytestArgs.Count -gt 0) {
  $args = @("-m", "pytest")
  if (-not (Test-HasPytestTarget -ArgsList $PytestArgs)) {
    $args += "system/tests"
  }
  $args += $PytestArgs
}
else {
  $args = @("-m", "pytest", "system/tests")
}

Set-Location $projectRoot
& $pythonExe @args
exit $LASTEXITCODE
