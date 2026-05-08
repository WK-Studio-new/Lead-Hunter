@echo off
chcp 65001 >nul
title LeadHunter · Backend
cd /d "%~dp0"
echo.
echo  ^^ LeadHunter Pro - Backend
echo  -------------------------------
pip install -r requirements.txt -q
echo.
echo  Backend em http://localhost:5000
echo  Deixe esta janela aberta.
echo  -------------------------------
echo.
python server.py
pause
