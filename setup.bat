@echo off
echo ========================================
echo KuruSwap Telegram Bot Setup (Windows)
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo Python found!
echo.

REM Run the setup script
echo Running setup script...
python setup.py

if errorlevel 1 (
    echo.
    echo Setup failed! Please check the errors above.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Setup completed successfully!
echo ========================================
echo.
echo To start the bot, run: start_bot.bat
echo Or manually: python start_bot.py
echo.
pause