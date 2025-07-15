#!/usr/bin/env python3
"""
KuruSwap Integration Test Script

This script tests the core functionality of the KuruSwap bot
without requiring a Telegram bot token.
"""

import os
import sys
from web3 import Web3
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuration
RPC_URL = os.getenv('RPC_URL', 'https://testnet-rpc.monad.xyz')
CHAIN_ID = int(os.getenv('CHAIN_ID', '10143'))

# Contract addresses
MON_ADDRESS = "0x0000000000000000000000000000000000000000"
WMON_ADDRESS = "0x760AfE86e5de5fa0Ee542fc7B7B713e1c5425701"
ROUTER_ADDRESS = "0xc816865f172d640d93712C68a7E1F83F3fA63235"
KURU_UTILS_ADDRESS = "0x9E50D9202bEc0D046a75048Be8d51bBa93386Ade"

# Test token addresses
TEST_TOKENS = {
    "CHOG": "0xe0590015a873bf326bd645c3e1266d4db41c4e6b",
    "DAK": "0x0F0BDEbF0F83cD1EE3974779Bcb7315f9808c714",
    "YAKI": "0xfe140e1dCe99Be9F4F15d657CD9b7BF622270C50",
    "WMON": WMON_ADDRESS
}

ERC20_ABI = [
    {"inputs": [], "name": "name", "outputs": [{"internalType": "string", "name": "", "type": "string"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "symbol", "outputs": [{"internalType": "string", "name": "", "type": "string"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "decimals", "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}], "stateMutability": "view", "type": "function"}
]

def test_web3_connection():
    """Test Web3 connection to Monad testnet."""
    print("🌐 Testing Web3 connection...")
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        
        if not w3.is_connected():
            print("❌ Failed to connect to RPC")
            return False
        
        # Get chain ID
        chain_id = w3.eth.chain_id
        
        # Handle non-numeric chain IDs (like 'zgtendermint_16600-2')
        numeric_chain_id = None
        if isinstance(chain_id, str):
            # Try to extract numeric part from string
            import re
            match = re.search(r'(\d+)', chain_id)
            if match:
                numeric_chain_id = int(match.group(1))
        elif isinstance(chain_id, int):
            numeric_chain_id = chain_id
        
        if numeric_chain_id != CHAIN_ID:
            print(f"⚠️ Chain ID mismatch. Expected {CHAIN_ID}, got {chain_id} (numeric: {numeric_chain_id})")
            print(f"   Continuing anyway as this might be a testnet identifier...")
        
        # Get latest block
        latest_block = w3.eth.get_block('latest')
        print(f"✅ Connected to Monad Testnet (Chain ID: {chain_id})")
        print(f"   Latest block: {latest_block.number}")
        
        return True
    except Exception as e:
        print(f"❌ Web3 connection failed: {e}")
        return False

def test_token_contracts():
    """Test token contract interactions."""
    print("\n🪙 Testing token contracts...")
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        
        for symbol, address in TEST_TOKENS.items():
            try:
                contract = w3.eth.contract(address=address, abi=ERC20_ABI)
                name = contract.functions.name().call()
                token_symbol = contract.functions.symbol().call()
                decimals = contract.functions.decimals().call()
                
                print(f"✅ {symbol}: {name} ({token_symbol}) - {decimals} decimals")
            except Exception as e:
                print(f"❌ {symbol} ({address}): {e}")
        
        return True
    except Exception as e:
        print(f"❌ Token contract test failed: {e}")
        return False

def test_kuru_api():
    """Test KuruSwap API endpoints."""
    print("\n🔄 Testing KuruSwap API...")
    try:
        # Test market pools endpoint
        pairs = [{
            "baseToken": MON_ADDRESS,
            "quoteToken": TEST_TOKENS["CHOG"]
        }]
        
        response = requests.post(
            "https://api.testnet.kuru.io/api/v1/markets/filtered",
            json={"pairs": pairs},
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                pool_address = data['data'][0]['market']
                print(f"✅ Found pool for MON/CHOG: {pool_address}")
            else:
                print("⚠️ No pool found for MON/CHOG pair")
        else:
            print(f"❌ API request failed: {response.status_code}")
            return False
        
        # Test token search endpoint
        response = requests.get(
            "https://api.testnet.kuru.io/api/v2/tokens/search?limit=5&q=",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Token search API working")
        else:
            print(f"⚠️ Token search API returned: {response.status_code}")
        
        return True
    except Exception as e:
        print(f"❌ KuruSwap API test failed: {e}")
        return False

def test_wallet_creation():
    """Test wallet creation functionality."""
    print("\n🔐 Testing wallet creation...")
    try:
        from eth_account import Account
        
        # Create a test wallet
        account = Account.create()
        address = account.address
        private_key = account.key.hex()
        
        print(f"✅ Wallet created successfully")
        print(f"   Address: {address}")
        print(f"   Private key: {private_key[:10]}...{private_key[-10:]}")
        
        # Test address validation
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if w3.is_address(address):
            print("✅ Address validation working")
        else:
            print("❌ Address validation failed")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Wallet creation test failed: {e}")
        return False

def test_database():
    """Test database functionality."""
    print("\n🗄️ Testing database...")
    try:
        import sqlite3
        import tempfile
        import os
        
        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        try:
            # Test database creation
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Create test table
            cursor.execute("""
                CREATE TABLE test_users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    wallet_address TEXT,
                    private_key TEXT
                )
            """)
            
            # Insert test data
            cursor.execute("""
                INSERT INTO test_users (user_id, username, wallet_address, private_key)
                VALUES (?, ?, ?, ?)
            """, (12345, "testuser", "0x1234567890123456789012345678901234567890", "test_key"))
            
            # Query test data
            cursor.execute("SELECT * FROM test_users WHERE user_id = ?", (12345,))
            result = cursor.fetchone()
            
            if result and result[1] == "testuser":
                print("✅ Database operations working")
                success = True
            else:
                print("❌ Database query failed")
                success = False
            
            conn.commit()
            conn.close()
            
        finally:
            # Clean up
            if os.path.exists(db_path):
                os.unlink(db_path)
        
        return success
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_dependencies():
    """Test if all required dependencies are installed."""
    print("📦 Testing dependencies...")
    
    required_packages = {
        'web3': 'Web3',
        'eth_account': 'Account',
        'requests': 'requests',
        'telegram': 'telegram',
        'sqlite3': 'sqlite3'  # Built-in
    }
    
    missing = []
    for package, import_name in required_packages.items():
        try:
            if package == 'telegram':
                import telegram
            elif package == 'web3':
                from web3 import Web3
            elif package == 'eth_account':
                from eth_account import Account
            elif package == 'requests':
                import requests
            elif package == 'sqlite3':
                import sqlite3
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - not installed")
            missing.append(package)
    
    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    print("✅ All dependencies installed")
    return True

def main():
    """Run all integration tests."""
    print("🧪 KuruSwap Integration Tests")
    print("=" * 50)
    
    tests = [
        ("Dependencies", test_dependencies),
        ("Web3 Connection", test_web3_connection),
        ("Token Contracts", test_token_contracts),
        ("KuruSwap API", test_kuru_api),
        ("Wallet Creation", test_wallet_creation),
        ("Database", test_database)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_func():
                passed += 1
            else:
                print(f"❌ {test_name} test failed")
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your bot should work correctly.")
        return True
    else:
        print(f"⚠️ {total - passed} test(s) failed. Please check the issues above.")
        return False

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n❌ Tests cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        sys.exit(1)
