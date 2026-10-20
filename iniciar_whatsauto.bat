@echo off
chcp 65001 >nul
title WhatsAuto Empresarial - Inicializador
cd /d "%~dp0"

echo ========================================================
echo   Iniciando WhatsAuto Empresarial...
echo ========================================================
echo.

netstat -ano | findstr ":5000 " | findstr "LISTENING" >nul
if errorlevel 1 goto start_server
echo [1/3] Servidor de regras ja esta rodando na porta 5000.
goto check_bridge

:start_server
echo [1/3] Iniciando servidor de regras [server.py]...
start "WhatsAuto - Servidor" /min "%~dp0.venv\Scripts\python.exe" "%~dp0server.py"
timeout /t 2 /nobreak >nul

:check_bridge
netstat -ano | findstr ":5001 " | findstr "LISTENING" >nul
if errorlevel 1 goto start_bridge
echo [2/3] Ponte WhatsApp QR Code ja esta rodando na porta 5001.
goto start_panel

:start_bridge
echo [2/3] Iniciando ponte WhatsApp QR Code [whatsapp_qr_bridge.js]...
start "WhatsAuto - Ponte QR Code" /min node "%~dp0whatsapp_qr_bridge.js"
timeout /t 2 /nobreak >nul

:start_panel
echo [3/3] Abrindo o Painel de Atendimento na sua tela...
echo.
echo Mantenha o painel aberto para gerenciar suas regras e ler o QR Code.
"%~dp0.venv\Scripts\python.exe" "%~dp0panel.py"
pause
