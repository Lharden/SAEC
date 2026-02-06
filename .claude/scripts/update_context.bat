@echo off
cd /d "%~dp0..\.."
python .claude\scripts\generate_context.py
echo.
echo Contexto atualizado! Inicie nova sessao do Claude Code para carregar.
pause
