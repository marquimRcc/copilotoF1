@echo off
title Copiloto F1 - HUD Always On Top
cd /d "%~dp0"

echo ============================================================
echo   🏎️ INICIANDO COPILOTO F1 - HUD DE TELEMETRIA
echo   📡 Escutando telemetria UDP do F1 na porta 20777...
echo ============================================================

python src\hud\overlay.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ⚠️ Ocorreu um erro ao executar o HUD. Verifique se o Python esta instalado.
    pause
)
