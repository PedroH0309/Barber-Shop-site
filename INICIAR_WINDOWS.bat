@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Execute INSTALAR_WINDOWS.bat antes de iniciar.
 pause
 exit /b 1
)
echo.
echo Site: http://127.0.0.1:5500/
echo Agenda: http://127.0.0.1:5500/agendar
echo Admin: http://127.0.0.1:5500/admin
echo.
echo Mantenha esta janela aberta enquanto usar o sistema.
start "" "http://127.0.0.1:5500/"
.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 5500
pause
