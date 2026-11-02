@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================
echo   PRECISION AGENDA - INSTALACAO
 echo ==========================================
py -3.13 --version >nul 2>&1
if errorlevel 1 (
 echo Python 3.13 nao encontrado. Instale Python 3.13 para Windows 64 bits.
 pause
 exit /b 1
)
if exist ".venv\Scripts\python.exe" (
 ".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 13) else 1)"
 if errorlevel 1 (
  echo Ambiente antigo com outra versao do Python detectado.
  echo Removendo somente .venv. Seus dados e reservas serao mantidos.
  rmdir /s /q ".venv"
 )
)
if not exist ".venv\Scripts\python.exe" (
 py -3.13 -m venv .venv
 if errorlevel 1 (
  echo Falha ao criar ambiente Python 3.13.
  pause
  exit /b 1
 )
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
 echo Erro ao instalar dependencias.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" -c "from zoneinfo import ZoneInfo; import fastapi,pydantic_core; ZoneInfo('America/Sao_Paulo')"
if errorlevel 1 (
 echo Erro de compatibilidade. Confirme Python 3.13 e tzdata.
 pause
 exit /b 1
)
echo.
echo Configure agora o acesso do barbeiro.
".venv\Scripts\python.exe" manage.py create-admin
if errorlevel 1 (
 pause
 exit /b 1
)
echo.
echo Pronto! Agora execute INICIAR_WINDOWS.bat
pause
