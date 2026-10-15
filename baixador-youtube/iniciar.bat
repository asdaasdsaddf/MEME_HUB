@echo off
rem Prepara o ambiente na primeira vez, atualiza o yt-dlp e abre a janela.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Preparando o ambiente pela primeira vez, aguarde...
    py -3 -m venv .venv 2>nul || python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Python nao encontrado. Instale em https://www.python.org/downloads/
    echo e marque a opcao "Add python.exe to PATH" durante a instalacao.
    pause
    exit /b 1
)

echo Verificando atualizacoes do yt-dlp...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -U -r requirements.txt
if errorlevel 1 (
    echo.
    echo Nao foi possivel instalar/atualizar as dependencias. Verifique a internet.
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" baixar_youtube.py
