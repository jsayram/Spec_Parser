@echo off
REM Windows batch script to verify environment
REM For cross-platform support, use verify_env.py instead

echo === Spec Parser Environment Verification ===
echo.

cd /d "%~dp0"
echo Project directory: %CD%
echo.

if not exist ".venv" (
    echo Virtual environment not found!
    echo Run: python -m venv .venv
    exit /b 1
)

echo Virtual environment: %CD%\.venv
echo.

REM Activate venv and run Python verification script
call .venv\Scripts\activate.bat
python verify_env.py
