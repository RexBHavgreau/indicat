@echo off
setlocal
cd /d "%~dp0"
echo ==============================================
echo  Indicat - build the .exe
echo ==============================================

rem Prefer the Python launcher (py) if it is installed.
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY goto :nopython
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" || goto :nopython

if not exist ".venv\Scripts\python.exe" (
    echo Creating a private Python environment in .venv ...
    %PY% -m venv .venv || goto :fail
)
set "VPY=.venv\Scripts\python.exe"

echo Installing requirements ...
"%VPY%" -m pip install --upgrade pip >nul
"%VPY%" -m pip install -r requirements.txt pyinstaller || goto :fail

echo Building ...
"%VPY%" -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name Indicat ^
    --icon "indicat\assets\indicat.ico" ^
    --collect-data docx ^
    --add-data "indicat\js;indicat\js" ^
    --add-data "indicat\data;indicat\data" ^
    --add-data "indicat\assets;indicat\assets" ^
    --hidden-import win32com.client ^
    --hidden-import pythoncom ^
    run_app.py || goto :fail

echo.
echo Done:  dist\Indicat.exe
echo.
pause
exit /b 0

:nopython
echo Python 3.10 or newer is required to build the .exe.
echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
pause
exit /b 1

:fail
echo.
echo The build failed. Scroll up for the error message.
pause
exit /b 1
