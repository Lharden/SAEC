@echo off
title SAEC-OG - Jupyter

echo ============================================
echo  SAEC-OG - Iniciando Jupyter
echo ============================================
echo.

cd /d "%~dp0"

if not exist ".venv" (
    echo [ERRO] Ambiente virtual nao encontrado.
    echo        Execute setup.bat primeiro.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [AVISO] Arquivo .env nao encontrado.
    echo         Execute setup.bat primeiro.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

echo Abrindo Jupyter Notebook...
echo.
echo  Ordem de execucao:
echo    1. 01_Configuracao.ipynb
echo    2. 02_Ingestao.ipynb
echo    3. 03_Extracao_LLM.ipynb
echo    4. 04_Validacao.ipynb (opcional)
echo    5. 05_Consolidacao.ipynb
echo.
echo  Pressione Ctrl+C para encerrar.
echo ============================================
echo.

jupyter notebook notebooks/
