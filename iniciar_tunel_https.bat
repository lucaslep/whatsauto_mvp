@echo off
chcp 65001 >nul
title WhatsAuto - Tunel HTTPS Local (Para Meta Webhook)
cd /d "%~dp0"

echo ======================================================================
echo   TUNEL HTTPS LOCAL PARA WEBHOOK DA META (OPCIONAL)
echo ======================================================================
echo Nota: Se voce estiver usando a conexao por QR Code (Aba 2 do Painel),
echo NAO precisa deste tunel! O modo QR Code funciona 100%% direto.
echo.
echo Use este tunel apenas se quiser conectar via API Oficial da Meta.
echo Copie o link https://... gerado abaixo e adicione /webhook no final.
echo ======================================================================
echo.

npx --yes localtunnel --port 5000
pause

