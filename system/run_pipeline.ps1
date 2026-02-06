param(
  [ValidateSet("notebooks","cli")]
  [string]$Mode = "notebooks",
  [ValidateSet("all","1","2","3","4","5")]
  [string]$Step = "all",
  [string]$ArticleId = "",
  [switch]$DryRun,
  [switch]$Force,
  [switch]$RunQA,
  [switch]$SyncMapping,
  [switch]$Consolidate,
  [switch]$Stats,
  [switch]$NoActivate,
  [switch]$Interactive,
  [switch]$Log
)

$ErrorActionPreference = "Stop"

function Ensure-Venv {
  if ($NoActivate) { return }
  $venvPath = Join-Path $PSScriptRoot ".venv"
  if (-not (Test-Path $venvPath)) {
    Write-Host "[INFO] Criando .venv..."
    python -m venv $venvPath
  }
  $activate = Join-Path $venvPath "Scripts\Activate.ps1"
  if (Test-Path $activate) {
    Write-Host "[INFO] Ativando .venv..."
    . $activate
  } else {
    Write-Host "[WARN] Não foi possível ativar .venv. Continuando..."
  }
}

function Ensure-Deps {
  Write-Host "[INFO] Instalando dependências..."
  python -m pip install --upgrade pip | Out-Null
  pip install -r (Join-Path $PSScriptRoot "requirements.txt") | Out-Null
}

function Run-CLI {
  $args = @()
  if ($Step -eq "all") {
    $args += "--all"
  } else {
    $args += "--step"; $args += $Step
  }
  if ($ArticleId) { $args += "--article"; $args += $ArticleId }
  if ($DryRun) { $args += "--dry-run" }
  if ($Force) { $args += "--force" }

  Write-Host "[INFO] Executando CLI: python main.py $($args -join ' ')"
  python (Join-Path $PSScriptRoot "main.py") @args
}

function Run-QA {
  Write-Host "[INFO] Rodando QA e exportando qa_report..."
  $code = @'
from qa_guideline import run_qa
df, path = run_qa(threshold=80, export=True)
print("qa_report:", path)
print("rows:", len(df))
'@
  $code | python -
}

function Run-SyncMapping {
  Write-Host "[INFO] Sincronizando mapping.csv (valid + QA OK)..."
  $code = @'
from pathlib import Path
from config import paths
from mapping_sync import sync_mapping_with_validation_and_qa

# use o QA report mais recente
qa_reports = sorted(paths.CONSOLIDATED.glob("qa_report_*.csv"))
if not qa_reports:
    raise SystemExit("Nenhum qa_report encontrado em outputs/consolidated")
qa_path = qa_reports[-1]

preview = sync_mapping_with_validation_and_qa(
    mapping_path=paths.MAPPING_CSV,
    yamls_dir=paths.YAMLS,
    qa_report_path=qa_path,
    dry_run=False,
)
print("sync rows:", len(preview))
'@
  $code | python -
}

function Run-Consolidate {
  Write-Host "[INFO] Rodando consolidação (05)..."
  $args = @("--step","5")
  python (Join-Path $PSScriptRoot "main.py") @args
}

function Run-Stats {
  Write-Host "[INFO] Gerando estatísticas do último Excel..."
  $code = @'
from pathlib import Path
import pandas as pd
from config import paths
from consolidate import generate_statistics, print_statistics

excels = sorted(paths.CONSOLIDATED.glob("*.xlsx"))
if not excels:
    raise SystemExit("Nenhum Excel encontrado em outputs/consolidated")

path = excels[-1]
df = pd.read_excel(path, sheet_name="Extrações")
stats = generate_statistics(df)
print_statistics(stats)
'@
  $code | python -
}

function Run-Checks {
  Write-Host "[INFO] Verificando ambiente e chaves..."
  $code = @'
from config import paths, llm_config
print("Project root:", paths.PROJECT_ROOT)
print("Articles dir:", paths.ARTICLES, "exists:", paths.ARTICLES.exists())
print("Extraction dir:", paths.EXTRACTION, "exists:", paths.EXTRACTION.exists())
print("Outputs dir:", paths.OUTPUTS, "exists:", paths.OUTPUTS.exists())
print("Keys:", llm_config.get_masked_keys())
errs = llm_config.validate()
print("Config errors:", errs if errs else "none")
'@
  $code | python -
}

function Prompt-YesNo($message, $defaultYes=$true) {
  $suffix = $defaultYes ? " [Y/n]" : " [y/N]"
  $ans = Read-Host ($message + $suffix)
  if ([string]::IsNullOrWhiteSpace($ans)) { return $defaultYes }
  return ($ans.Trim().ToLower() -in @("y","yes","s","sim"))
}

function Prompt-Choice($message, $choices, $defaultIndex=0) {
  Write-Host $message
  for ($i=0; $i -lt $choices.Count; $i++) {
    $mark = ($i -eq $defaultIndex) ? "*" : " "
    Write-Host ("  {0}{1}. {2}" -f $mark, ($i+1), $choices[$i])
  }
  $ans = Read-Host "Selecione (1-$($choices.Count))"
  if ([string]::IsNullOrWhiteSpace($ans)) { return $choices[$defaultIndex] }
  $idx = [int]$ans - 1
  if ($idx -lt 0 -or $idx -ge $choices.Count) { return $choices[$defaultIndex] }
  return $choices[$idx]
}

# =========================
# Logging
# =========================
function Start-RunLog {
  if (-not $Log) { return $null }
  $logDir = Join-Path $PSScriptRoot "logs"
  if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
  $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
  $logPath = Join-Path $logDir "run_$stamp.log"
  Start-Transcript -Path $logPath | Out-Null
  return $logPath
}

function Stop-RunLog {
  if ($Log) { Stop-Transcript | Out-Null }
}

# =========================
# Modo Interativo
# =========================
if ($Interactive) {
  Write-Host "=== MODO INTERATIVO ==="
  $Mode = (Prompt-Choice "Modo de execução:" @("cli","notebooks") 0)

  $doChecks = Prompt-YesNo "Rodar checagens de ambiente/chaves antes?" $true
  if ($doChecks) { Ensure-Venv; Ensure-Deps; Run-Checks }

  $runBatch = Prompt-YesNo "Rodar pipeline completo em batch?" $true
  if ($runBatch) {
    $Step = "all"
  } else {
    $Step = (Prompt-Choice "Escolha etapa:" @("1","2","3","4","5") 2)
  }

  $useArticle = Prompt-YesNo "Executar para artigo específico?" $false
  if ($useArticle) {
    $ArticleId = Read-Host "Informe o ArtigoID (ex: ART_001)"
  }

  $DryRun = Prompt-YesNo "Dry-run (simular)?" $false
  $Force = Prompt-YesNo "Forçar reprocessamento?" $false

  $RunQA = Prompt-YesNo "Gerar QA report?" $true
  $SyncMapping = Prompt-YesNo "Sincronizar mapping.csv (valid + QA OK)?" $true
  $Consolidate = Prompt-YesNo "Consolidar em Excel (05)?" $true
  $Stats = Prompt-YesNo "Gerar estatísticas do último Excel?" $false

  # Resumo + confirmação final
  Write-Host ""
  Write-Host "=== RESUMO DA EXECUCAO ==="
  Write-Host ("Modo: {0}" -f $Mode)
  Write-Host ("Step: {0}" -f $Step)
  Write-Host ("Artigo: {0}" -f ($ArticleId -ne "" ? $ArticleId : "todos"))
  Write-Host ("DryRun: {0}" -f $DryRun)
  Write-Host ("Force: {0}" -f $Force)
  Write-Host ("RunQA: {0}" -f $RunQA)
  Write-Host ("SyncMapping: {0}" -f $SyncMapping)
  Write-Host ("Consolidate: {0}" -f $Consolidate)
  Write-Host ("Stats: {0}" -f $Stats)
  Write-Host ("Log: {0}" -f $Log)
  $proceed = Prompt-YesNo "Confirmar e executar?" $true
  if (-not $proceed) {
    Write-Host "[INFO] Execucao cancelada pelo usuario."
    exit 0
  }
}

# =========================
# Execução
# =========================
Set-Location $PSScriptRoot
if (-not $Log) { $Log = $true }
$logPath = Start-RunLog
Ensure-Venv
Ensure-Deps

if ($Mode -eq "cli") {
  Run-CLI
} else {
  Write-Host "[INFO] Modo notebooks: abra os .ipynb em ordem 01→05"
  Write-Host "       Use -Mode cli para execução automática."
}

if ($RunQA) { Run-QA }
if ($SyncMapping) { Run-SyncMapping }
if ($Consolidate) { Run-Consolidate }
if ($Stats) { Run-Stats }

if ($logPath) {
  Write-Host ("[INFO] Log salvo em: {0}" -f $logPath)
}
Stop-RunLog
