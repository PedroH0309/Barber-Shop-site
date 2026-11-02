@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Ambiente virtual nao encontrado. Execute INSTALAR_WINDOWS.bat primeiro.
 pause
 exit /b 1
)
echo ==========================================
echo   PRECISION AGENDA - ACESSO DO BARBEIRO
echo ==========================================
echo Usuario padrao sugerido: barbeiro
echo Senha: voce escolhe, com pelo menos 12 caracteres.
echo Nenhuma reserva sera apagada.
echo.
".venv\Scripts\python.exe" manage.py create-admin
if errorlevel 1 (
 echo Nao foi possivel definir o login.
 pause
 exit /b 1
)
echo.
echo Credenciais configuradas. Entre em http://127.0.0.1:5500/admin
pause
