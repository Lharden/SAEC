@echo off
title SAEC-OG - Setup

echo ============================================
echo  SAEC-OG - Configuracao Inicial
echo ============================================
echo.

cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Instale Python 3.10+
    pause
    exit /b 1
)

if not exist ".venv" (
    echo [1/4] Criando ambiente virtual...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar ambiente virtual.
        pause
        exit /b 1
    )
    echo       OK
) else (
    echo [1/4] Ambiente virtual ja existe.
)

echo [2/4] Ativando ambiente virtual...
call .venv\Scripts\activate.bat

echo [3/4] Instalando dependencias...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias.
    pause
    exit /b 1
)
echo       OK

if not exist ".env" (
    echo [4/4] Criando arquivo .env...
    copy .env.template .env >nul
    echo.
    echo ============================================
    echo  IMPORTANTE: Configure suas chaves de API
    echo ============================================
    echo.
    echo  Abrindo .env para edicao...
    echo  Preencha ANTHROPIC_API_KEY e OPENAI_API_KEY
    echo.
    notepad .env
) else (
    echo [4/4] Arquivo .env ja existe.
)

echo.
echo ============================================
echo  Setup concluido!
echo ============================================
echo.
echo  Proximo passo: execute run.bat para iniciar
echo.
pause
