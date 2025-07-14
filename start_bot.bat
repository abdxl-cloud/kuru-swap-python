@echo off
echo ========================================
echo KuruSwap Telegram Bot Launcher (Windows)
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

REM Check if setup was run
if not exist ".env" (
    echo Error: .env file not found!
    echo Please run setup.bat first to configure the bot.
    pause
    exit /b 1
)

echo Starting KuruSwap Telegram Bot...
echo Press Ctrl+C to stop the bot
echo.

REM Start the bot
python start_bot.py

echo.
echo Bot stopped.
pause