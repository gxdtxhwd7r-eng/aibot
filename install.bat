@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m venv .venv
if errorlevel 1 goto error
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 goto error
if not exist .env copy .env.example .env >nul
echo.
echo Готово. Откройте .env, добавьте OPENAI_API_KEY и запустите run.bat
pause
exit /b 0
:error
echo Ошибка установки. Проверьте, что Python 3.11 или новее установлен и добавлен в PATH.
pause
exit /b 1
