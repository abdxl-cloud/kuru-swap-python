#!/usr/bin/env python3
"""
KuruSwap Telegram Bot

A Telegram bot that allows users to:
1. Create wallets
2. Deposit MON tokens
3. Swap MON to any valid token address using KuruSwap

Requires:
- python-telegram-bot
- web3
- requests
- sqlite3 (built-in)
"""

import logging
import sqlite3
import json
import asyncio
import os
from typing import Dict, Optional, Tuple, List
from decimal import Decimal

import requests
from web3 import Web3
from eth_account import Account
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional

# Enable logging
log_level = logging.DEBUG if os.getenv('DEBUG', 'false').lower() == 'true' else logging.INFO
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=log_level
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
    logger.error("Please set your BOT_TOKEN in the .env file or environment variables")
    exit(1)
RPC_URL = os.getenv('RPC_URL', 'https://testnet-rpc.monad.xyz')
CHAIN_ID = int(os.getenv('CHAIN_ID', '10143'))
TX_EXPLORER = os.getenv('TX_EXPLORER', 'https://testnet.monadexplorer.com/tx/')
DATABASE_PATH = os.getenv('DATABASE_PATH', 'kuruswap_bot.db')

# Contract addresses
MON_ADDRESS = "0x0000000000000000000000000000000000000000"
WMON_ADDRESS = "0x760AfE86e5de5fa0Ee542fc7B7B713e1c5425701"
ROUTER_ADDRESS = "0xc816865f172d640d93712C68a7E1F83F3fA63235"
KURU_UTILS_ADDRESS = "0x9E50D9202bEc0D046a75048Be8d51bBa93386Ade"

# Contract ABIs
ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "address[]", "name": "_marketAddresses", "type": "address[]"},
            {"internalType": "bool[]", "name": "_isBuy", "type": "bool[]"},
            {"internalType": "bool[]", "name": "_nativeSend", "type": "bool[]"},
            {"internalType": "address", "name": "_debitToken", "type": "address"},
            {"internalType": "address", "name": "_creditToken", "type": "address"},
            {"internalType": "uint256", "name": "_amount", "type": "uint256"},
            {"internalType": "uint256", "name": "_minAmountOut", "type": "uint256"}
        ],
        "name": "anyToAnySwap",
        "outputs": [{"internalType": "uint256", "name": "_amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    }
]

KURU_UTILS_ABI = [
    {
        "inputs": [
            {"internalType": "address[]", "name": "route", "type": "address[]"},
            {"internalType": "bool[]", "name": "isBuy", "type": "bool[]"}
        ],
        "name": "calculatePriceOverRoute",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

ERC20_ABI = [
    {"inputs": [{"internalType": "address", "name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "name", "outputs": [{"internalType": "string", "name": "", "type": "string"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "symbol", "outputs": [{"internalType": "string", "name": "", "type": "string"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "decimals", "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "spender", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}], "name": "approve", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"}
]

# Conversation states
AWAITING_TOKEN_ADDRESS, AWAITING_SWAP_AMOUNT, AWAITING_PRIVATE_KEY, AWAITING_WALLET_NAME = range(4)

# Initialize Web3
try:
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    # Test connection and handle non-standard chain IDs
    if w3.is_connected():
        try:
            chain_id = w3.eth.chain_id
            # Handle non-numeric chain IDs gracefully
            if isinstance(chain_id, str):
                logger.info(f"Connected to network with chain ID: {chain_id}")
            else:
                logger.info(f"Connected to network with chain ID: {chain_id}")
        except Exception as e:
            logger.warning(f"Could not get chain ID: {e}")
    else:
        logger.error("Failed to connect to Web3 provider")
except Exception as e:
    logger.error(f"Error initializing Web3: {e}")
    w3 = None

def ensure_web3_connected():
    """Ensure Web3 is connected and available."""
    global w3
    if w3 is None:
        try:
            w3 = Web3(Web3.HTTPProvider(RPC_URL))
        except Exception as e:
            logger.error(f"Failed to reinitialize Web3: {e}")
            return False
    
    if not w3.is_connected():
        logger.error("Web3 is not connected")
        return False
    
    return True

class DatabaseManager:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DATABASE_PATH
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create users table (basic user info)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                active_wallet_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create wallets table (multiple wallets per user)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                wallet_name TEXT,
                wallet_address TEXT,
                private_key TEXT,
                is_active BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                wallet_id INTEGER,
                tx_hash TEXT,
                tx_type TEXT,
                amount TEXT,
                token_address TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (wallet_id) REFERENCES wallets (id)
            )
        """)
        
        # Migrate existing data if needed
        self._migrate_existing_data(cursor)
        
        conn.commit()
        conn.close()
    
    def _migrate_existing_data(self, cursor):
        """Migrate existing single-wallet data to multi-wallet schema."""
        try:
            # Check if old schema exists
            cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'wallet_address' in columns:
                # Migrate existing users to new schema
                cursor.execute("SELECT user_id, username, wallet_address, private_key FROM users WHERE wallet_address IS NOT NULL")
                old_users = cursor.fetchall()
                
                for user_id, username, wallet_address, private_key in old_users:
                    # Create wallet entry
                    cursor.execute("""
                        INSERT OR IGNORE INTO wallets (user_id, wallet_name, wallet_address, private_key, is_active)
                        VALUES (?, ?, ?, ?, 1)
                    """, (user_id, "Main Wallet", wallet_address, private_key))
                    
                    # Get wallet ID
                    cursor.execute("SELECT id FROM wallets WHERE user_id = ? AND wallet_address = ?", (user_id, wallet_address))
                    wallet_id = cursor.fetchone()[0]
                    
                    # Update user with active wallet
                    cursor.execute("""
                        UPDATE users SET active_wallet_id = ? WHERE user_id = ?
                    """, (wallet_id, user_id))
                
                # Remove old columns (SQLite doesn't support DROP COLUMN, so we recreate)
                cursor.execute("""
                    CREATE TABLE users_new (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        active_wallet_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    INSERT INTO users_new (user_id, username, active_wallet_id, created_at)
                    SELECT user_id, username, active_wallet_id, created_at FROM users
                """)
                
                cursor.execute("DROP TABLE users")
                cursor.execute("ALTER TABLE users_new RENAME TO users")
                
        except Exception as e:
            logger.error(f"Error migrating data: {e}")
    
    def create_user(self, user_id: int, username: str) -> bool:
        """Create a new user."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR IGNORE INTO users (user_id, username)
                VALUES (?, ?)
            """, (user_id, username))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return False
    
    def create_wallet(self, user_id: int, wallet_name: str, wallet_address: str, private_key: str) -> bool:
        """Create a new wallet for a user."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Deactivate other wallets if this is the first one
            cursor.execute("SELECT COUNT(*) FROM wallets WHERE user_id = ?", (user_id,))
            wallet_count = cursor.fetchone()[0]
            is_active = wallet_count == 0
            
            cursor.execute("""
                INSERT INTO wallets (user_id, wallet_name, wallet_address, private_key, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, wallet_name, wallet_address, private_key, is_active))
            
            wallet_id = cursor.lastrowid
            
            # Set as active wallet if it's the first one
            if is_active:
                cursor.execute("""
                    UPDATE users SET active_wallet_id = ? WHERE user_id = ?
                """, (wallet_id, user_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error creating wallet: {e}")
            return False
    
    def get_user_wallets(self, user_id: int) -> List[Dict]:
        """Get all wallets for a user."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, wallet_name, wallet_address, is_active
                FROM wallets WHERE user_id = ?
                ORDER BY created_at ASC
            """, (user_id,))
            
            results = cursor.fetchall()
            conn.close()
            
            return [{
                'id': result[0],
                'name': result[1],
                'address': result[2],
                'is_active': bool(result[3])
            } for result in results]
        except Exception as e:
            logger.error(f"Error getting user wallets: {e}")
            return []
    
    def get_active_wallet(self, user_id: int) -> Optional[Dict]:
        """Get the active wallet for a user."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT w.id, w.wallet_name, w.wallet_address, w.private_key
                FROM wallets w
                JOIN users u ON w.id = u.active_wallet_id
                WHERE u.user_id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'id': result[0],
                    'name': result[1],
                    'address': result[2],
                    'private_key': result[3]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting active wallet: {e}")
            return None
    
    def set_active_wallet(self, user_id: int, wallet_id: int) -> bool:
        """Set the active wallet for a user."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Verify wallet belongs to user
            cursor.execute("SELECT id FROM wallets WHERE id = ? AND user_id = ?", (wallet_id, user_id))
            if not cursor.fetchone():
                return False
            
            # Update active wallet
            cursor.execute("""
                UPDATE users SET active_wallet_id = ? WHERE user_id = ?
            """, (wallet_id, user_id))
            
            # Update wallet active status
            cursor.execute("UPDATE wallets SET is_active = 0 WHERE user_id = ?", (user_id,))
            cursor.execute("UPDATE wallets SET is_active = 1 WHERE id = ?", (wallet_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error setting active wallet: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user information with active wallet."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT u.user_id, u.username, w.wallet_address, w.private_key
                FROM users u
                LEFT JOIN wallets w ON u.active_wallet_id = w.id
                WHERE u.user_id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'user_id': result[0],
                    'username': result[1],
                    'wallet_address': result[2],
                    'private_key': result[3]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None
    
    def log_transaction(self, wallet_id: int, tx_hash: str, tx_type: str, amount: str, token_address: str, status: str):
        """Log a transaction."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO transactions (wallet_id, tx_hash, tx_type, amount, token_address, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (wallet_id, tx_hash, tx_type, amount, token_address, status))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error logging transaction: {e}")

class KuruSwapBot:
    def __init__(self):
        self.db = DatabaseManager()
    
    def create_wallet(self) -> Tuple[str, str]:
        """Create a new wallet and return address and private key."""
        account = Account.create()
        return account.address, account.key.hex()
    
    def get_mon_balance(self, address: str) -> float:
        """Get MON balance for an address."""
        try:
            if not ensure_web3_connected():
                logger.error("Web3 not available for balance check")
                return 0.0
            
            balance_wei = w3.eth.get_balance(address)
            return float(w3.from_wei(balance_wei, 'ether'))
        except Exception as e:
            logger.error(f"Error getting MON balance: {e}")
            return 0.0
    
    def get_token_info(self, token_address: str) -> Optional[Dict]:
        """Get token information (name, symbol, decimals)."""
        try:
            if not ensure_web3_connected():
                logger.error("Web3 not available for token info")
                return None
                
            if not w3.is_address(token_address):
                return None
            
            contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
            name = contract.functions.name().call()
            symbol = contract.functions.symbol().call()
            decimals = contract.functions.decimals().call()
            
            return {
                'name': name,
                'symbol': symbol,
                'decimals': decimals,
                'address': token_address
            }
        except Exception as e:
            logger.error(f"Error getting token info: {e}")
            return None
    
    def filter_market_pools(self, base_token: str, quote_token: str) -> Optional[str]:
        """Find market pool for token pair."""
        try:
            pairs = [{
                "baseToken": base_token,
                "quoteToken": quote_token
            }]
            
            response = requests.post(
                "https://api.testnet.kuru.io/api/v1/markets/filtered",
                json={"pairs": pairs},
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data') and len(data['data']) > 0:
                    return data['data'][0]['market']
            
            # Try inverted pair
            pairs = [{
                "baseToken": quote_token,
                "quoteToken": base_token
            }]
            
            response = requests.post(
                "https://api.testnet.kuru.io/api/v1/markets/filtered",
                json={"pairs": pairs},
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data') and len(data['data']) > 0:
                    return data['data'][0]['market']
            
            return None
        except Exception as e:
            logger.error(f"Error filtering market pools: {e}")
            return None
    
    def calculate_swap_output(self, pool_address: str, is_buy: bool) -> Optional[int]:
        """Calculate expected swap output."""
        try:
            kuru_utils = w3.eth.contract(address=KURU_UTILS_ADDRESS, abi=KURU_UTILS_ABI)
            price = kuru_utils.functions.calculatePriceOverRoute([pool_address], [is_buy]).call()
            return price
        except Exception as e:
            logger.error(f"Error calculating swap output: {e}")
            return None
    
    def perform_swap(self, private_key: str, token_address: str, amount_mon: float) -> Optional[str]:
        """Perform the actual swap transaction."""
        try:
            account = Account.from_key(private_key)
            
            # Find pool
            pool_address = self.filter_market_pools(MON_ADDRESS, token_address)
            if not pool_address:
                return None
            
            # Calculate expected output
            price = self.calculate_swap_output(pool_address, False)  # MON -> TOKEN
            if not price:
                return None
            
            amount_wei = w3.to_wei(amount_mon, 'ether')
            expected_out = (amount_wei * price) // (10**18)
            min_amount_out = (expected_out * 85) // 100  # 15% slippage
            
            # Prepare transaction
            router = w3.eth.contract(address=ROUTER_ADDRESS, abi=ROUTER_ABI)
            
            # Get gas price
            gas_price = w3.eth.gas_price
            
            # Build transaction
            transaction = router.functions.anyToAnySwap(
                [pool_address],  # market addresses
                [True],          # is buy
                [True],          # native send
                MON_ADDRESS,     # debit token
                token_address,   # credit token
                amount_wei,      # amount
                min_amount_out   # min amount out
            ).build_transaction({
                'from': account.address,
                'value': amount_wei,
                'gas': 250000,
                'gasPrice': gas_price,
                'nonce': w3.eth.get_transaction_count(account.address)
            })
            
            # Sign and send transaction
            signed_txn = w3.eth.account.sign_transaction(transaction, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            return tx_hash.hex()
        except Exception as e:
            logger.error(f"Error performing swap: {e}")
            return None

# Initialize bot
kuru_bot = KuruSwapBot()

# Helper functions for keyboards
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔐 Create Wallet", callback_data="create_wallet")],
        [InlineKeyboardButton("📥 Import Wallet", callback_data="import_wallet")],
        [InlineKeyboardButton("👛 Manage Wallets", callback_data="manage_wallets")],
        [InlineKeyboardButton("💰 Check Balance", callback_data="check_balance")],
        [InlineKeyboardButton("🔄 Swap Tokens", callback_data="start_swap")],
        [InlineKeyboardButton("📊 Transaction History", callback_data="tx_history")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_to_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🏠 Back to Menu", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard():
    keyboard = [
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
        [InlineKeyboardButton("🏠 Back to Menu", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Bot command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler."""
    user = update.effective_user
    
    reply_markup = get_main_keyboard()
    
    welcome_text = f"""
🚀 **Welcome to KuruSwap Bot!** 🚀

Hello {user.first_name}! I'm your personal KuruSwap assistant on Monad Testnet.

**What I can do:**
• Create secure wallets for you
• Check your MON balance
• Swap MON tokens to any valid token address
• Track your transaction history

**Getting Started:**
1. Create a wallet first
2. Deposit some MON tokens
3. Start swapping!

⚠️ **Important:** This bot operates on Monad Testnet. Use only testnet tokens!
    """
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "create_wallet":
        await create_wallet_handler(query, context)
    elif data == "import_wallet":
        await import_wallet_handler(query, context)
    elif data == "manage_wallets":
        await manage_wallets_handler(query, context)
    elif data == "check_balance":
        await check_balance_handler(query, context)
    elif data == "start_swap":
        await start_swap_handler(query, context)
    elif data == "tx_history":
        await tx_history_handler(query, context)
    elif data == "back_to_menu":
        await back_to_menu_handler(query, context)
    elif data == "cancel":
        await cancel_operation_handler(query, context)
    elif data.startswith("select_wallet_"):
        wallet_id = int(data.split("_")[-1])
        await select_wallet_handler(query, context, wallet_id)
    elif data.startswith("switch_wallet_"):
        wallet_id = int(data.split("_")[-1])
        await switch_wallet_handler(query, context, wallet_id)

async def create_wallet_handler(query, context):
    """Handle wallet creation."""
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    
    # Ensure user exists in database
    kuru_bot.db.create_user(user_id, username)
    
    # Set conversation state
    context.user_data['state'] = AWAITING_WALLET_NAME
    context.user_data['action'] = 'create'
    
    await query.edit_message_text(
        "🔐 **Create New Wallet**\n\n"
        "Please send a name for your new wallet.\n\n"
        "Examples: `Main Wallet`, `Trading Wallet`, `Savings`",
        reply_markup=get_cancel_keyboard(),
        parse_mode='Markdown'
    )
    
    return AWAITING_WALLET_NAME

async def import_wallet_handler(query, context):
    """Handle wallet import."""
    user_id = query.from_user.id
    username = query.from_user.username or f"user_{user_id}"
    
    # Ensure user exists in database
    kuru_bot.db.create_user(user_id, username)
    
    # Set conversation state
    context.user_data['state'] = AWAITING_WALLET_NAME
    context.user_data['action'] = 'import'
    context.user_data['username'] = username
    
    await query.edit_message_text(
        "📥 **Import Existing Wallet**\n\n"
        "Please send a name for your imported wallet.\n\n"
        "Examples: `Imported Wallet`, `MetaMask Wallet`, `Hardware Wallet`",
        reply_markup=get_cancel_keyboard(),
        parse_mode='Markdown'
    )
    
    return AWAITING_WALLET_NAME

async def manage_wallets_handler(query, context):
    """Handle wallet management."""
    user_id = query.from_user.id
    
    wallets = kuru_bot.db.get_user_wallets(user_id)
    if not wallets:
        await query.edit_message_text(
            "👛 **No wallets found!**\n\n"
            "Create or import a wallet first.",
            reply_markup=get_back_to_menu_keyboard()
        )
        return
    
    keyboard = []
    for wallet in wallets:
        status = "🟢 Active" if wallet['is_active'] else "⚪ Inactive"
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {wallet['name']}", 
                callback_data=f"select_wallet_{wallet['id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🏠 Back to Menu", callback_data="back_to_menu")])
    
    await query.edit_message_text(
        "👛 **Your Wallets**\n\n"
        "Select a wallet to view details or switch to it:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def select_wallet_handler(query, context, wallet_id):
    """Handle wallet selection for details."""
    user_id = query.from_user.id
    
    wallets = kuru_bot.db.get_user_wallets(user_id)
    selected_wallet = next((w for w in wallets if w['id'] == wallet_id), None)
    
    if not selected_wallet:
        await query.edit_message_text(
            "❌ **Wallet not found!**",
            reply_markup=get_back_to_menu_keyboard()
        )
        return
    
    try:
        balance = kuru_bot.get_mon_balance(selected_wallet['address'])
        status = "🟢 **Active Wallet**" if selected_wallet['is_active'] else "⚪ Inactive"
        
        keyboard = []
        if not selected_wallet['is_active']:
            keyboard.append([InlineKeyboardButton(
                "🔄 Switch to this wallet", 
                callback_data=f"switch_wallet_{wallet_id}"
            )])
        
        keyboard.extend([
            [InlineKeyboardButton("👛 Back to Wallets", callback_data="manage_wallets")],
            [InlineKeyboardButton("🏠 Back to Menu", callback_data="back_to_menu")]
        ])
        
        await query.edit_message_text(
            f"👛 **{selected_wallet['name']}**\n\n"
            f"{status}\n\n"
            f"**Address:** `{selected_wallet['address']}`\n"
            f"**Balance:** `{balance:.6f} MON`\n\n"
            f"🔗 [View on Explorer](https://testnet.monadexplorer.com/address/{selected_wallet['address']})",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in select_wallet_handler: {e}")
        await query.edit_message_text(
            "❌ **Error loading wallet details.**",
            reply_markup=get_back_to_menu_keyboard()
        )

async def switch_wallet_handler(query, context, wallet_id):
    """Handle switching active wallet."""
    user_id = query.from_user.id
    
    success = kuru_bot.db.set_active_wallet(user_id, wallet_id)
    if success:
        wallets = kuru_bot.db.get_user_wallets(user_id)
        switched_wallet = next((w for w in wallets if w['id'] == wallet_id), None)
        
        await query.edit_message_text(
            f"✅ **Wallet switched successfully!**\n\n"
            f"Active wallet is now: **{switched_wallet['name']}**\n\n"
            f"**Address:** `{switched_wallet['address']}`",
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text(
            "❌ **Error switching wallet.**",
            reply_markup=get_back_to_menu_keyboard()
        )

async def check_balance_handler(query, context):
    """Handle balance checking."""
    user_id = query.from_user.id
    
    active_wallet = kuru_bot.db.get_active_wallet(user_id)
    if not active_wallet:
        await query.edit_message_text(
            "❌ **No active wallet found!** Please create a wallet first.",
            reply_markup=get_back_to_menu_keyboard()
        )
        return
    
    try:
        balance = kuru_bot.get_mon_balance(active_wallet['address'])
        
        await query.edit_message_text(
            f"💰 **Balance - {active_wallet['name']}**\n\n"
            f"**Address:** `{active_wallet['address']}`\n"
            f"**MON Balance:** `{balance:.6f} MON`\n\n"
            f"🔗 **Explorer:** [View on Explorer](https://testnet.monadexplorer.com/address/{active_wallet['address']})",
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error checking balance: {e}")
        await query.edit_message_text(
            "❌ **Error checking balance.** Please try again later.",
            reply_markup=get_back_to_menu_keyboard()
        )

async def start_swap_handler(query, context):
    """Start the swap process."""
    user_id = query.from_user.id
    
    active_wallet = kuru_bot.db.get_active_wallet(user_id)
    if not active_wallet:
        await query.edit_message_text(
            "❌ **No active wallet found!** Please create a wallet first.",
            reply_markup=get_back_to_menu_keyboard()
        )
        return
    
    balance = kuru_bot.get_mon_balance(active_wallet['address'])
    if balance <= 0:
        await query.edit_message_text(
            f"❌ **Insufficient Balance!**\n\n"
            f"**Wallet:** {active_wallet['name']}\n"
            f"**Balance:** `{balance:.6f} MON`\n\n"
            f"Please deposit some MON tokens to your wallet first.",
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode='Markdown'
        )
        return
    
    await query.edit_message_text(
        f"🔄 **Start Token Swap**\n\n"
        f"**Active Wallet:** {active_wallet['name']}\n"
        f"**Balance:** `{balance:.6f} MON`\n\n"
        f"Please send me the **token contract address** you want to swap to.\n\n"
        f"Example: `0xe0590015a873bf326bd645c3e1266d4db41c4e6b`",
        reply_markup=get_cancel_keyboard(),
        parse_mode='Markdown'
    )
    
    return AWAITING_TOKEN_ADDRESS

async def tx_history_handler(query, context):
    """Show transaction history."""
    await query.edit_message_text(
        "📊 **Transaction History**\n\n"
        "This feature will show your recent swaps and transactions.\n"
        "(Coming soon in next update!)",
        reply_markup=get_back_to_menu_keyboard()
    )

async def handle_token_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle token address input."""
    user_id = update.effective_user.id
    token_address = update.message.text.strip()
    
    # Validate token address
    if not w3.is_address(token_address):
        await update.message.reply_text(
            "❌ **Invalid token address!** Please send a valid Ethereum address.",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_TOKEN_ADDRESS
    
    # Get token info
    token_info = kuru_bot.get_token_info(token_address)
    if not token_info:
        await update.message.reply_text(
            "❌ **Invalid token!** Could not fetch token information. "
            "Please make sure the address is correct.",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_TOKEN_ADDRESS
    
    # Check if pool exists
    pool_address = kuru_bot.filter_market_pools(MON_ADDRESS, token_address)
    if not pool_address:
        await update.message.reply_text(
            f"❌ **No trading pool found!**\n\n"
            f"Token: **{token_info['name']} ({token_info['symbol']})**\n"
            f"Address: `{token_address}`\n\n"
            f"This token cannot be traded on KuruSwap yet.",
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    # Store token info in context
    context.user_data['token_info'] = token_info
    context.user_data['pool_address'] = pool_address
    
    active_wallet = kuru_bot.db.get_active_wallet(user_id)
    balance = kuru_bot.get_mon_balance(active_wallet['address'])
    
    await update.message.reply_text(
        f"✅ **Token Found!**\n\n"
        f"**Token:** {token_info['name']} ({token_info['symbol']})\n"
        f"**Address:** `{token_address}`\n"
        f"**Pool:** `{pool_address}`\n\n"
        f"**Active Wallet:** {active_wallet['name']}\n"
        f"**MON Balance:** `{balance:.6f} MON`\n\n"
        f"💡 **How much MON do you want to swap?**\n"
        f"Please enter the amount (e.g., 0.1, 1.5, 10):",
        parse_mode='Markdown'
    )
    
    return AWAITING_SWAP_AMOUNT

async def handle_swap_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle swap amount input."""
    user_id = update.effective_user.id
    amount_text = update.message.text.strip()
    
    try:
        amount = float(amount_text)
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except ValueError:
        await update.message.reply_text(
            "❌ **Invalid amount!** Please enter a valid positive number.",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_SWAP_AMOUNT
    
    active_wallet = kuru_bot.db.get_active_wallet(user_id)
    balance = kuru_bot.get_mon_balance(active_wallet['address'])
    
    if amount > balance:
        await update.message.reply_text(
            f"❌ **Insufficient balance!**\n\n"
            f"**Wallet:** {active_wallet['name']}\n"
            f"**You want to swap:** `{amount} MON`\n"
            f"**Your balance:** `{balance:.6f} MON`\n\n"
            f"Please enter a smaller amount.",
            reply_markup=get_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return AWAITING_SWAP_AMOUNT
    
    token_info = context.user_data['token_info']
    
    # Confirm swap
    keyboard = [
        [InlineKeyboardButton("✅ Confirm Swap", callback_data=f"confirm_swap_{amount}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_swap")],
        [InlineKeyboardButton("🏠 Back to Menu", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🔄 **Confirm Your Swap**\n\n"
        f"**From:** `{amount} MON`\n"
        f"**To:** {token_info['name']} ({token_info['symbol']})\n"
        f"**Token Address:** `{token_info['address']}`\n\n"
        f"⚠️ **Slippage:** 15% (for safety)\n"
        f"💰 **Estimated Gas:** ~0.01 MON\n\n"
        f"**Are you sure you want to proceed?**",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

async def handle_wallet_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle wallet name input."""
    user_id = update.effective_user.id
    wallet_name = update.message.text.strip()
    
    if len(wallet_name) < 1 or len(wallet_name) > 50:
        await update.message.reply_text(
            "❌ **Invalid wallet name!**\n\n"
            "Wallet name must be between 1 and 50 characters.\n\n"
            "Please try again:",
            reply_markup=get_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return AWAITING_WALLET_NAME
    
    action = context.user_data.get('action')
    
    if action == 'create':
        # Create new wallet
        try:
            address, private_key = kuru_bot.create_wallet()
            success = kuru_bot.db.create_wallet(user_id, wallet_name, address, private_key)
            
            if success:
                await update.message.reply_text(
                    f"🎉 **Wallet Created Successfully!**\n\n"
                    f"**Name:** {wallet_name}\n"
                    f"**Address:** `{address}`\n\n"
                    f"🔑 **Private Key:** `{private_key}`\n\n"
                    f"⚠️ **IMPORTANT:** Save your private key securely! "
                    f"I'll remember it for you, but you should back it up.\n\n"
                    f"💰 **Next Step:** Send some MON tokens to your address to start swapping!",
                    reply_markup=get_back_to_menu_keyboard(),
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    "❌ **Error creating wallet.** Please try again later.",
                    reply_markup=get_back_to_menu_keyboard()
                )
        except Exception as e:
            logger.error(f"Error creating wallet: {e}")
            await update.message.reply_text(
                "❌ **Error creating wallet.** Please try again later.",
                reply_markup=get_back_to_menu_keyboard()
            )
        return ConversationHandler.END
    
    elif action == 'import':
        # Store wallet name and proceed to private key input
        context.user_data['wallet_name'] = wallet_name
        context.user_data['state'] = AWAITING_PRIVATE_KEY
        
        await update.message.reply_text(
            f"📥 **Import Wallet: {wallet_name}**\n\n"
            "Now please send your private key (64 characters starting with 0x).\n\n"
            "⚠️ **Security Warning**: Make sure you're in a private chat and the message will be auto-deleted.\n\n"
            "Example format: `0x1234567890abcdef...`",
            reply_markup=get_cancel_keyboard(),
            parse_mode='Markdown'
        )
        
        return AWAITING_PRIVATE_KEY
    
    return ConversationHandler.END

async def handle_private_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle private key input for wallet import."""
    user_id = update.effective_user.id
    private_key = update.message.text.strip()
    wallet_name = context.user_data.get('wallet_name')
    
    # Delete the user's message for security
    try:
        await update.message.delete()
    except:
        pass  # Ignore if we can't delete the message
    
    # Validate private key format
    if not private_key.startswith('0x') or len(private_key) != 66:
        await update.message.reply_text(
            "❌ **Invalid private key format!**\n\n"
            "Private key must be 64 characters long and start with '0x'.\n\n"
            "Example: `0x1234567890abcdef...`\n\n"
            "Please try again:",
            reply_markup=get_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return AWAITING_PRIVATE_KEY
    
    try:
        # Validate private key by creating account
        account = Account.from_key(private_key)
        address = account.address
        
        # Create wallet
        success = kuru_bot.db.create_wallet(user_id, wallet_name, address, private_key)
        
        if success:
            await update.message.reply_text(
                f"🎉 **Wallet Imported Successfully!**\n\n"
                f"**Name:** {wallet_name}\n"
                f"**Address:** `{address}`\n\n"
                f"✅ Your wallet has been imported and is ready to use.\n\n"
                f"💰 **Next Step:** Check your balance or start swapping!",
                reply_markup=get_back_to_menu_keyboard(),
                parse_mode='Markdown'
            )
            
            # Clear conversation state
            context.user_data.clear()
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                "❌ **Error importing wallet.** Please try again later.",
                reply_markup=get_cancel_keyboard()
            )
            return AWAITING_PRIVATE_KEY
            
    except Exception as e:
        logger.error(f"Error importing wallet: {e}")
        await update.message.reply_text(
            "❌ **Invalid private key!**\n\n"
            "The private key you provided is not valid. Please check and try again:",
            reply_markup=get_cancel_keyboard(),
            parse_mode='Markdown'
        )
        return AWAITING_PRIVATE_KEY

async def confirm_swap_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle swap confirmation."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data.startswith("confirm_swap_"):
        amount = float(query.data.split("_")[-1])
        
        await query.edit_message_text(
            f"⏳ **Processing your swap...**\n\n"
            f"Swapping `{amount} MON` to tokens...\n"
            f"Please wait, this may take a few moments."
        )
        
        active_wallet = kuru_bot.db.get_active_wallet(user_id)
        token_info = context.user_data.get('token_info')
        
        if not active_wallet:
            await query.edit_message_text(
                "❌ **Error:** No active wallet found. Please create a wallet first.",
                reply_markup=get_back_to_menu_keyboard()
            )
            return
        
        if not token_info:
            await query.edit_message_text(
                "❌ **Error:** Token information not found. Please start over.",
                reply_markup=get_back_to_menu_keyboard()
            )
            return
        
        # Perform swap
        tx_hash = kuru_bot.perform_swap(
            active_wallet['private_key'],
            token_info['address'],
            amount
        )
        
        if tx_hash:
            # Log transaction
            kuru_bot.db.log_transaction(
                active_wallet['id'], tx_hash, "swap", str(amount), token_info['address'], "pending"
            )
            
            await query.edit_message_text(
                f"🎉 **Swap Transaction Sent!**\n\n"
                f"**Amount:** `{amount} MON`\n"
                f"**Token:** {token_info['name']} ({token_info['symbol']})\n"
                f"**Transaction Hash:** `{tx_hash}`\n\n"
                f"🔗 [View on Explorer]({TX_EXPLORER}{tx_hash})\n\n"
                f"⏳ **Status:** Pending confirmation...",
                reply_markup=get_back_to_menu_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                f"❌ **Swap Failed!**\n\n"
                f"The transaction could not be processed. Possible reasons:\n"
                f"• Insufficient gas\n"
                f"• Network congestion\n"
                f"• Pool liquidity issues\n\n"
                f"Please try again later.",
                reply_markup=get_back_to_menu_keyboard()
            )
    
    elif query.data == "cancel_swap":
        await query.edit_message_text(
            "❌ **Swap Cancelled**\n\n"
            "Your swap has been cancelled. No tokens were exchanged.",
            reply_markup=get_back_to_menu_keyboard()
        )

async def back_to_menu_handler(query, context):
    """Handle back to menu button."""
    user = query.from_user
    
    welcome_text = f"""
🚀 **Welcome to KuruSwap Bot!** 🚀

Hello {user.first_name}! I'm your personal KuruSwap assistant on Monad Testnet.

**What I can do:**
• Create secure wallets for you
• Check your MON balance
• Swap MON tokens to any valid token address
• Track your transaction history

**Getting Started:**
1. Create a wallet first
2. Deposit some MON tokens
3. Start swapping!

⚠️ **Important:** This bot operates on Monad Testnet. Use only testnet tokens!
    """
    
    await query.edit_message_text(welcome_text, reply_markup=get_main_keyboard(), parse_mode='Markdown')

async def cancel_operation_handler(query, context):
    """Handle cancel operation button."""
    await query.edit_message_text(
        "❌ **Operation cancelled.**\n\n"
        "What would you like to do next?",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation."""
    await update.message.reply_text(
        "❌ **Operation cancelled.**\n\n"
        "Use /start to begin again.",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

def main():
    """Start the bot."""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add conversation handler for swaps
    swap_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^start_swap$")],
        states={
            AWAITING_TOKEN_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_token_address)],
            AWAITING_SWAP_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_swap_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
    )
    
    # Add conversation handler for wallet operations
    wallet_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_handler, pattern="^(create_wallet|import_wallet)$")
        ],
        states={
            AWAITING_WALLET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet_name)],
            AWAITING_PRIVATE_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_private_key)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(swap_conv_handler)
    application.add_handler(wallet_conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CallbackQueryHandler(confirm_swap_handler, pattern="^(confirm_swap_|cancel_swap)"))
    
    # Start the bot
    print("🚀 KuruSwap Telegram Bot is starting...")
    print(f"🌐 Network: Monad Testnet ({CHAIN_ID})")
    print(f"🔗 RPC: {RPC_URL}")
    print("✅ Bot is ready!")
    
    application.run_polling()

if __name__ == '__main__':
    main()
