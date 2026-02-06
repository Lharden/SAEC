@echo off
setlocal

title SAEC-OG - Build EXE

cd /d "%~dp0"

echo ============================================
echo  SAEC-OG - Build executavel (.exe)
echo ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    if exist "..\.venv\Scripts\python.exe" (
        set "VENV_DIR=..\.venv"
    ) else (
        echo [ERRO] Ambiente virtual nao encontrado em system\.venv ou ..\.venv
        echo        Execute setup.bat primeiro.
        exit /b 1
    )
) else (
    set "VENV_DIR=.venv"
)

call "%VENV_DIR%\Scripts\activate.bat"

python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [1/3] Instalando PyInstaller...
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo [ERRO] Falha ao instalar PyInstaller.
        exit /b 1
    )
) else (
    echo [1/3] PyInstaller ja instalado.
)

echo [2/3] Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/4] Gerando SAEC-OG.exe (GUI Win98, perfil otimizado)...
python -m PyInstaller --noconfirm --clean SAEC-OG.spec

if errorlevel 1 (
    echo [ERRO] Build GUI falhou.
    exit /b 1
)

echo [4/4] Gerando SAEC-OG-CLI.exe (perfil otimizado)...
python -m PyInstaller --noconfirm --clean SAEC-OG-CLI.spec

if errorlevel 1 (
    echo [ERRO] Build CLI falhou.
    exit /b 1
)

echo.
echo [OK] Build concluido:
echo   dist\SAEC-OG.exe      (GUI)
echo   dist\SAEC-OG-CLI.exe  (CLI)
echo.
echo Para executar:
echo   dist\SAEC-OG.exe
echo   dist\SAEC-OG-CLI.exe --status
echo   dist\SAEC-OG-CLI.exe --all
echo.

endlocal
