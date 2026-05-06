@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "PYTHON_EXE=C:\Users\Administrator\AppData\Local\Programs\Python\Python314-32\python.exe"

cd /d "%PROJECT_DIR%"
"%PYTHON_EXE%" "%PROJECT_DIR%\build_exe.py"

endlocal
