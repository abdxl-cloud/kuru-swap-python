#!/usr/bin/env python3
"""
KuruSwap Telegram Bot Setup Script

This script helps you set up the KuruSwap Telegram Bot quickly.
"""

import os
import sys
import subprocess

def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required.")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version.split()[0]}")
    return True

def install_requirements():
    """Install required packages."""
    print("📦 Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ All packages installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing packages: {e}")
        return False

def setup_environment():
    """Set up environment file."""
    env_file = ".env"
    example_file = ".env.example"
    
    if os.path.exists(env_file):
        print(f"✅ {env_file} already exists.")
        return True
    
    if not os.path.exists(example_file):
        print(f"❌ {example_file} not found.")
        return False
    
    # Copy example to .env
    with open(example_file, 'r') as f:
        content = f.read()
    
    with open(env_file, 'w') as f:
        f.write(content)
    
    print(f"✅ Created {env_file} from {example_file}")
    return True

def get_bot_token():
    """Get bot token from user."""
    print("\n🤖 Telegram Bot Setup")
    print("To create a Telegram bot:")
    print("1. Message @BotFather on Telegram")
    print("2. Send /newbot command")
    print("3. Follow the instructions")
    print("4. Copy the bot token")
    
    token = input("\nEnter your bot token (or press Enter to skip): ").strip()
    
    if token:
        # Update .env file
        env_file = ".env"
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                content = f.read()
            
            # Replace the token line
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.startswith('BOT_TOKEN='):
                    lines[i] = f'BOT_TOKEN={token}'
                    break
            
            with open(env_file, 'w') as f:
                f.write('\n'.join(lines))
            
            print("✅ Bot token saved to .env file")
            return True
    
    print("⚠️ Bot token not set. You'll need to update the .env file manually.")
    return False

def test_connection():
    """Test connection to Monad testnet."""
    print("\n🌐 Testing connection to Monad Testnet...")
    try:
        import requests
        response = requests.post(
            "https://testnet-rpc.monad.xyz",
            json={"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            chain_id = int(data.get('result', '0x0'), 16)
            if chain_id == 10143:
                print("✅ Successfully connected to Monad Testnet")
                return True
        print("❌ Failed to connect to Monad Testnet")
        return False
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def main():
    """Main setup function."""
    print("🚀 KuruSwap Telegram Bot Setup")
    print("=" * 40)
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Install requirements
    if not install_requirements():
        return False
    
    # Setup environment
    if not setup_environment():
        return False
    
    # Get bot token
    get_bot_token()
    
    # Test connection
    test_connection()
    
    print("\n🎉 Setup Complete!")
    print("\nNext steps:")
    print("1. Make sure your bot token is set in the .env file")
    print("2. Run the bot: python telegram_bot.py")
    print("3. Start chatting with your bot on Telegram!")
    
    print("\n📚 For more information, check the README.md file.")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n❌ Setup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)