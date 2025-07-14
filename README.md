# KuruSwap Telegram Bot

A powerful Telegram bot that allows multiple users to create wallets, deposit MON tokens, and swap them to any valid token address using the KuruSwap protocol on Monad Testnet.

## Features

🔐 **Wallet Management**
- Create secure wallets for each user
- Store wallet information securely in SQLite database
- Check MON balance

💰 **Token Swapping**
- Swap MON tokens to any valid ERC-20 token
- Automatic pool discovery via KuruSwap API
- Real-time price calculation
- Configurable slippage protection (15% default)

📊 **Transaction Tracking**
- Log all swap transactions
- View transaction history
- Direct links to Monad Explorer

🛡️ **Security Features**
- Private keys encrypted in database
- Input validation for all user inputs
- Error handling and recovery

## Prerequisites

- Python 3.8 or higher
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Internet connection for Monad Testnet access

## Quick Start

### Option 1: Automated Setup (Recommended)

**For Windows users:**
```cmd
# Run the setup script
setup.bat

# Start the bot
start_bot.bat
```

**For Linux/Mac users:**
```bash
# Run the setup script
python setup.py

# Start the bot
python start_bot.py
```

### Option 2: Manual Installation

#### 1. Clone or Download

```bash
git clone <repository-url>
cd kuru-swap-python
```

#### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 3. Create Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` command
3. Follow the instructions to create your bot
4. Copy the bot token

#### 4. Configure Environment

1. Copy the example environment file:
   ```bash
   copy .env.example .env    # Windows
   cp .env.example .env      # Linux/Mac
   ```

2. Edit `.env` file and add your bot token:
   ```
   BOT_TOKEN=your_actual_bot_token_here
   ```

#### 5. Test Your Setup

```bash
python test_integration.py
```

This will verify that all components are working correctly.

## Usage

### Starting the Bot

**Using the launcher (recommended):**
```bash
python start_bot.py
```

**Direct start:**
```bash
python telegram_bot.py
```

You should see:
```
🚀 KuruSwap Telegram Bot is starting...
🌐 Network: Monad Testnet (10143)
🔗 RPC: https://testnet-rpc.monad.xyz
✅ Bot is ready!
```

### Available Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `setup.py` | Automated setup and configuration | `python setup.py` |
| `start_bot.py` | Bot launcher with pre-flight checks | `python start_bot.py` |
| `test_integration.py` | Test all bot components | `python test_integration.py` |
| `telegram_bot.py` | Main bot application | `python telegram_bot.py` |
| `setup.bat` | Windows setup script | `setup.bat` |
| `start_bot.bat` | Windows launcher | `start_bot.bat` |

### Bot Commands

Users can interact with your bot using these features:

#### 1. **Create Wallet** 🔐
- Creates a new Ethereum wallet
- Provides wallet address and private key
- Stores securely in database

#### 2. **Import Wallet** 📥
- Import existing wallet using private key
- Validates private key format and authenticity
- Securely stores imported wallet
- Automatically deletes private key message for security

#### 3. **Check Balance** 💰
- Shows current MON balance
- Displays wallet address
- Links to Monad Explorer

#### 4. **Swap Tokens** 🔄
- Enter target token contract address
- Specify amount of MON to swap
- Automatic pool discovery
- Real-time price calculation
- Transaction confirmation

#### 5. **Transaction History** 📊
- View recent swaps
- Transaction status tracking
- Explorer links

## How It Works

### Wallet Creation
1. Bot generates a new Ethereum private key
2. Derives wallet address from private key
3. Stores both securely in SQLite database
4. Returns wallet info to user

### Wallet Import
1. **Security First**: User's private key message is automatically deleted
2. **Validation**: Checks private key format (64 chars, starts with 0x)
3. **Authentication**: Validates private key by creating account
4. **Storage**: Securely stores wallet in database
5. **Confirmation**: Provides wallet address confirmation

### Token Swapping Process
1. **Token Validation**: Verifies the target token contract
2. **Pool Discovery**: Finds trading pool via KuruSwap API
3. **Price Calculation**: Gets current exchange rate
4. **Transaction Building**: Constructs swap transaction
5. **Execution**: Signs and broadcasts transaction
6. **Confirmation**: Provides transaction hash and explorer link

### Supported Networks
- **Monad Testnet** (Chain ID: 10143)
- RPC: `https://testnet-rpc.monad.xyz`
- Explorer: `https://testnet.monadexplorer.com`

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|----------|
| `BOT_TOKEN` | Telegram bot token | Required |
| `DATABASE_PATH` | SQLite database file | `kuruswap_bot.db` |
| `RPC_URL` | Monad RPC endpoint | `https://testnet-rpc.monad.xyz` |
| `DEBUG` | Enable debug logging | `false` |

### Contract Addresses (Monad Testnet)

```python
MON_ADDRESS = "0x0000000000000000000000000000000000000000"  # Native MON
WMON_ADDRESS = "0x760AfE86e5de5fa0Ee542fc7B7B713e1c5425701"  # Wrapped MON
ROUTER_ADDRESS = "0xc816865f172d640d93712C68a7E1F83F3fA63235"  # KuruSwap Router
KURU_UTILS_ADDRESS = "0x9E50D9202bEc0D046a75048Be8d51bBa93386Ade"  # Utilities
```

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    wallet_address TEXT,
    private_key TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Transactions Table
```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    tx_hash TEXT,
    tx_type TEXT,
    amount TEXT,
    token_address TEXT,
    status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);
```

## Security Considerations

⚠️ **Important Security Notes:**

1. **Private Key Storage**: Private keys are stored in the local SQLite database. In production, consider using encrypted storage or hardware security modules.

2. **Wallet Import Security**: When importing wallets, private key messages are automatically deleted from Telegram for security. Always use the bot in private chats, never in groups.

3. **Testnet Only**: This bot is designed for Monad Testnet. Do not use with mainnet tokens.

4. **Bot Token Security**: Keep your Telegram bot token secure and never commit it to version control.

5. **Database Security**: Protect the SQLite database file as it contains private keys.

6. **Server Security**: Run the bot on a secure server with proper access controls.

## Troubleshooting

### Common Issues

**Bot doesn't respond:**
- Check if bot token is correct
- Verify bot is running without errors
- Ensure internet connection

**Swap fails:**
- Check if token address is valid
- Verify sufficient MON balance
- Ensure trading pool exists for the token pair
- Check network connectivity

**"No pool found" error:**
- The token might not be listed on KuruSwap
- Try a different token address
- Verify the token is on Monad Testnet

### Debug Mode

Enable debug logging by setting `DEBUG=true` in your `.env` file:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Example Token Addresses (Monad Testnet)

For testing, you can use these token addresses:

```
CHOG: 0xe0590015a873bf326bd645c3e1266d4db41c4e6b
DAK:  0x0F0BDEbF0F83cD1EE3974779Bcb7315f9808c714
YAKI: 0xfe140e1dCe99Be9F4F15d657CD9b7BF622270C50
WMON: 0x760AfE86e5de5fa0Ee542fc7B7B713e1c5425701
```

## API Integration

The bot integrates with:

- **KuruSwap API**: `https://api.testnet.kuru.io`
  - Market pool discovery
  - Token information
  - Price calculations

- **Monad RPC**: `https://testnet-rpc.monad.xyz`
  - Blockchain interactions
  - Transaction broadcasting
  - Balance queries

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source and available under the [MIT License](LICENSE).

## Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review the logs for error messages

## Disclaimer

⚠️ **This software is provided "as is" without warranty. Use at your own risk. This bot is designed for Monad Testnet only and should not be used with real funds on mainnet.**

---

**Happy Swapping! 🚀**