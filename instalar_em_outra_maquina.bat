@echo off
chcp 65001 >nul
title WhatsAuto Empresarial - Instalador para Nova Maquina
cd /d "%~dp0"

echo ==================================================================
echo   INSTALADOR DO WHATSAUTO EMPRESARIAL (NOVA MAQUINA)
echo ==================================================================
echo.

:: 1. Verifica se o Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado nesta maquina!
    echo Baixe e instale o Python em: https://www.python.org/downloads/
    echo IMPORTANTE: Na instalacao do Python, marque a opcao "Add python.exe to PATH".
    pause
    exit /b 1
)

:: 2. Verifica se o Node.js esta instalado
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Node.js nao encontrado nesta maquina!
    echo Baixe e instale o Node.js LTS em: https://nodejs.org/
    pause
    exit /b 1
)

echo [1/3] Preparando ambiente limpo (.venv e sessao WhatsApp) para esta maquina...
if exist ".venv" rmdir /s /q ".venv"
if exist "wa_session" rmdir /s /q "wa_session"
python -m venv .venv
if errorlevel 1 (
    echo [ERRO] Falha ao criar o ambiente virtual Python.
    pause
    exit /b 1
)

echo [2/3] Instalando bibliotecas Python...
"%~dp0.venv\Scripts\python.exe" -m pip install --upgrade pip
"%~dp0.venv\Scripts\python.exe" -m pip install -r requirements.txt

echo [3/3] Instalando bibliotecas da ponte WhatsApp (Node.js)...
call npm install --no-audit --no-fund

echo.
echo ==================================================================
echo   INSTALACAO CONCLUIDA COM SUCESSO!
echo   Agora basta abrir o arquivo: iniciar_whatsauto.bat
echo ==================================================================
pause

