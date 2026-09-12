@echo off
REM clipbin launcher for Windows (Command Prompt).
REM   run.bat            start server + clipboard watcher
REM   run.bat server     server only
REM   run.bat watch      clipboard watcher only
REM Extra flags pass straight to run.py, e.g. run.bat --port 9000
cd /d "%~dp0"

where python >nul 2>nul && (set "PY=python") || (
  where py >nul 2>nul && (set "PY=py") || (
    echo Python 3 is required but was not found. Install it from https://python.org
    exit /b 1
  )
)

%PY% run.py %*
