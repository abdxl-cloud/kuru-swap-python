#!/usr/bin/env python3
"""
KuruSwap Telegram Bot Launcher

Simple launcher script with pre-flight checks.
"""

import os
import sys
import subprocess

def check_requirements():
    """Check if all requirements are met."""
    print("🔍 Checking requirements...")
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        print("Run 'python setup.py' first to set up the bot.")
        return False
    
    # Check if bot token is set
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        bot_token = os.getenv('BOT_TOKEN')
        if not bot_token or bot_token == 'YOUR_BOT_TOKEN_HERE':
            print("❌ Bot token not set!")
            print("Please update your .env file with a valid BOT_TOKEN.")
            return False
        
        print("✅ Bot token found")
    except ImportError:
        print("⚠️ python-dotenv not installed, using environment variables")
    
    # Check if required packages are installed
    required_packages = [
        'telegram',
        'web3',
        'requests',
        'eth_account'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing packages: {', '.join(missing_packages)}")
        print("Run 'pip install -r requirements.txt' to install them.")
        return False
    
    print("✅ All required packages installed")
    return True

def test_network_connection():
    """Test connection to Monad testnet."""
    print("🌐 Testing network connection...")
    try:
        import requests
        response = requests.get("https://testnet-rpc.monad.xyz", timeout=5)
        if response.status_code in [200, 405]:  # 405 is also OK for RPC endpoints
            print("✅ Network connection OK")
            return True
        else:
            print(f"⚠️ Network response: {response.status_code}")
            return True  # Continue anyway
    except Exception as e:
        print(f"⚠️ Network test failed: {e}")
        print("Continuing anyway...")
        return True  # Don't block on network issues

def start_bot():
    """Start the telegram bot."""
    print("🚀 Starting KuruSwap Telegram Bot...")
    print("Press Ctrl+C to stop the bot")
    print("-" * 40)
    
    try:
        # Import and run the bot
        from telegram_bot import main
        main()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot crashed: {e}")
        print("Check the logs above for more details.")
        return False
    
    return True

def main():
    """Main launcher function."""
    print("🤖 KuruSwap Telegram Bot Launcher")
    print("=" * 40)
    
    # Run pre-flight checks
    if not check_requirements():
        print("\n❌ Pre-flight checks failed!")
        print("Please fix the issues above and try again.")
        return False
    
    if not test_network_connection():
        print("\n⚠️ Network issues detected, but continuing...")
    
    print("\n✅ All checks passed!")
    print("\n" + "=" * 40)
    
    # Start the bot
    return start_bot()

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Launcher stopped")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Launcher failed: {e}")
        sys.exit(1)