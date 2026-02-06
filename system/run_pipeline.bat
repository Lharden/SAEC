@echo off
setlocal

REM Wrapper simples para run_pipeline.ps1 (modo cli)
REM Exemplo:
REM   run_pipeline.bat --mode cli --step all --runqa --syncmapping --consolidate --stats

set SCRIPT_DIR=%~dp0
set PS_SCRIPT=%SCRIPT_DIR%run_pipeline.ps1

if not exist "%PS_SCRIPT%" (
  echo [ERRO] Arquivo nao encontrado: %PS_SCRIPT%
  exit /b 1
)

if "%~1"=="" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" -Interactive
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*
)
