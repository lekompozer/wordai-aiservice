# USDT Cryptocurrency Payment Integration Analysis

**Version:** 2.0
**Last Updated:** December 2, 2025
**Supported Networks:** BEP-20 (BSC), TRC-20 (Tron)
**Exchange Rate:** 1 USDT ≈ 26,000 VND (dynamic)

---

## Executive Summary

This document provides a comprehensive technical analysis for integrating USDT (Tether) cryptocurrency payments into WordAI, supporting both **BEP-20 (Binance Smart Chain)** and **TRC-20 (Tron)** networks. Users can purchase subscription plans and points using crypto wallets while the system automatically converts and validates transactions.

### Supported Networks

| Network | Token Standard | Avg Fee | Confirmation Time | Security | Recommendation |
|---------|---------------|---------|-------------------|----------|----------------|
| **BSC** | BEP-20 | $0.10-$0.50 | 3 seconds | High | ⭐ Primary (Fast + Cheap) |
| **Tron** | TRC-20 | $0.50-$2.00 | 3-10 seconds | High | ⭐ Alternative (Popular) |

**Why these networks?**
- ✅ **Low fees:** Both networks have negligible transaction costs compared to Ethereum ($20-$100)
- ✅ **Fast confirmation:** 3-10 seconds vs 1-15 minutes on Ethereum
- ✅ **High adoption:** Most crypto users have wallets supporting these networks
- ✅ **USDT liquidity:** Both have deep USDT liquidity on exchanges

### Key Benefits
- ✅ **0.1-2% transaction fees** (vs 2-4% for traditional gateways)
- ✅ **Instant settlement** (3-10 seconds confirmation)
- ✅ **Global accessibility** (no banking restrictions)
- ✅ **No chargebacks** (blockchain finality)
- ✅ **Automated processing** (smart contract + monitoring)

### Key Challenges
- ⚠️ **Exchange rate volatility** (solved by rate-locking mechanism)
- ⚠️ **Network selection UX** (users must choose correct network)
- ⚠️ **Gas fees education** (users need native tokens: BNB/TRX)
- ⚠️ **Transaction monitoring complexity** (requires blockchain indexing)

---

---

## 🏗️ System Architecture

### High-Level Architecture

```
┌─────────────────────┐         ┌──────────────────────┐         ┌─────────────────────┐
│   User Browser      │         │   Backend API        │         │   Blockchain        │
│   (Web3 Wallet)     │         │   (Python)           │         │   BSC / Tron        │
└──────────┬──────────┘         └──────────┬───────────┘         └──────────┬──────────┘
           │                               │                                │
           │ 1. Select Network (BSC/Tron) │                                │
           ├─────────────────────────────>│                                │
           │                               │                                │
           │ 2. Create Payment Intent      │                                │
           │    (amount, network)          │                                │
           ├─────────────────────────────>│                                │
           │                               │                                │
           │ 3. Return Payment Info        │                                │
           │    (address, amount, timeout) │                                │
           │<──────────────────────────────┤                                │
           │                               │                                │
           │ 4. Connect Wallet             │                                │
           │    (MetaMask/TronLink)        │                                │
           │                               │                                │
           │ 5. Sign & Broadcast TX        │                                │
           ├───────────────────────────────┼───────────────────────────────>│
           │                               │                                │
           │                               │ 6. Monitor Address             │
           │                               │    (WebSocket/Polling)         │
           │                               │<───────────────────────────────┤
           │                               │                                │
           │                               │ 7. Detect TX                   │
           │                               │<───────────────────────────────┤
           │                               │                                │
           │                               │ 8. Verify:                     │
           │                               │    - Correct amount            │
           │                               │    - Correct address           │
           │                               │    - Min confirmations         │
           │                               │                                │
           │                               │ 9. Credit Points/Subscription  │
           │                               │    (Update Database)           │
           │                               │                                │
           │ 10. WebSocket Notification    │                                │
           │<──────────────────────────────┤                                │
           │     "Payment Confirmed!"      │                                │
           │                               │                                │
```

### Component Breakdown

#### 1. Frontend (React/Next.js)
- **Wallet Connection:** Web3Modal, WalletConnect
- **Network Switching:** Detect and prompt user to switch networks
- **Transaction Signing:** Use wallet's built-in signing
- **Real-time Updates:** WebSocket for payment status

#### 2. Backend (Python FastAPI)
- **Payment Intent Creation:** Generate unique payment addresses
- **Transaction Monitoring:** Blockchain scanners (BSCScan API, TronGrid API)
- **Validation Logic:** Verify amount, sender, confirmations
- **Database Updates:** Credit points/subscriptions after confirmation

#### 3. Blockchain Monitoring Services
- **BSC Monitor:** Web3.py + BSCScan API
- **Tron Monitor:** TronPy + TronGrid API
- **Webhook Support:** Optional instant notifications from blockchain explorers

---

## 🔐 Wallet & Network Configuration

### BEP-20 (Binance Smart Chain)

**Network Details:**
```json
{
  "chainId": "0x38",
  "chainIdDecimal": 56,
  "chainName": "Binance Smart Chain Mainnet",
  "nativeCurrency": {
    "name": "BNB",
    "symbol": "BNB",
    "decimals": 18
  },
  "rpcUrls": [
    "https://bsc-dataseed.binance.org/",
    "https://bsc-dataseed1.defibit.io/",
    "https://bsc-dataseed1.ninicoin.io/"
  ],
  "blockExplorerUrls": ["https://bscscan.com"]
}
```

**USDT Token Contract:**
- **Address:** `0x55d398326f99059fF775485246999027B3197955`
- **Decimals:** 18
- **Symbol:** USDT
- **Gas Fee:** ~0.0002-0.0005 BNB ($0.10-$0.30)
- **Confirmation Time:** ~3 seconds (1 block)

### TRC-20 (Tron Network)

**Network Details:**
```json
{
  "chainId": "0x2b6653dc",
  "chainName": "Tron Mainnet",
  "nativeCurrency": {
    "name": "TRX",
    "symbol": "TRX",
    "decimals": 6
  },
  "rpcUrls": ["https://api.trongrid.io"],
  "blockExplorerUrls": ["https://tronscan.org"]
}
```

**USDT Token Contract:**
- **Address:** `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`
- **Decimals:** 6
- **Symbol:** USDT
- **Gas Fee:** ~5-15 TRX ($0.50-$2.00)
- **Confirmation Time:** ~3 seconds (1 block)

---

## 🔍 Transaction Monitoring & Verification System

### Overview

The transaction monitoring system is the **most critical component** for crypto payments. It must reliably detect, validate, and confirm USDT transfers to prevent fraud while providing a smooth user experience.

### Monitoring Architecture Options

#### Option 1: Dedicated Hot Wallet (Recommended)
Each payment uses the **same hot wallet address**. System monitors incoming transactions to this address.

**Pros:**
- ✅ Simple implementation
- ✅ Easy balance management
- ✅ Lower monitoring overhead
- ✅ Standard practice for exchanges

**Cons:**
- ⚠️ Requires payment_id in transaction memo/data (not all wallets support)
- ⚠️ Manual reconciliation if memo missing

#### Option 2: Unique Address Per Payment
Generate a **new deposit address** for each payment intent.

**Pros:**
- ✅ Automatic payment matching (no memo needed)
- ✅ Better privacy
- ✅ Easier reconciliation

**Cons:**
- ⚠️ Complex address generation (HD wallets)
- ⚠️ Must monitor many addresses simultaneously
- ⚠️ Higher infrastructure cost

**Recommendation:** Use **Option 1 (Hot Wallet)** with optional memo field. Fall back to manual matching via amount + timestamp for wallets without memo support.

---

### BSC (BEP-20) Transaction Monitoring

#### Method 1: BSCScan API (Recommended)

**Advantages:**
- ✅ Free tier: 5 calls/second
- ✅ Historical transaction data
- ✅ No blockchain node required
- ✅ Well-documented

**API Endpoint:**
```
https://api.bscscan.com/api
?module=account
&action=tokentx
&contractaddress=0x55d398326f99059fF775485246999027B3197955
&address={YOUR_WALLET_ADDRESS}
&startblock=0
&endblock=99999999
&sort=desc
&apikey={YOUR_API_KEY}
```

**Python Implementation:**

```python
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class BSCTransactionMonitor:
    """Monitor USDT BEP-20 transactions on Binance Smart Chain"""

    BSC_API_URL = "https://api.bscscan.com/api"
    USDT_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"
    MIN_CONFIRMATIONS = 12  # ~36 seconds on BSC

    def __init__(self, api_key: str, wallet_address: str):
        self.api_key = api_key
        self.wallet_address = wallet_address
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_recent_transactions(
        self,
        since_timestamp: Optional[int] = None
    ) -> List[Dict]:
        """
        Fetch recent USDT transactions to monitored address

        Args:
            since_timestamp: Unix timestamp to fetch transactions after

        Returns:
            List of transaction dictionaries
        """
        params = {
            "module": "account",
            "action": "tokentx",
            "contractaddress": self.USDT_CONTRACT,
            "address": self.wallet_address,
            "startblock": 0,
            "endblock": 99999999,
            "sort": "desc",
            "apikey": self.api_key
        }

        try:
            response = await self.client.get(self.BSC_API_URL, params=params)
            data = response.json()

            if data["status"] != "1":
                raise Exception(f"BSCScan API error: {data.get('message')}")

            transactions = data["result"]

            # Filter by timestamp if provided
            if since_timestamp:
                transactions = [
                    tx for tx in transactions
                    if int(tx["timeStamp"]) >= since_timestamp
                ]

            return transactions

        except Exception as e:
            print(f"❌ Error fetching BSC transactions: {e}")
            return []

    async def verify_transaction(
        self,
        tx_hash: str,
        expected_amount: float,
        expected_recipient: str,
        tolerance: float = 0.01
    ) -> Dict[str, any]:
        """
        Verify a specific transaction meets payment requirements

        Args:
            tx_hash: Transaction hash to verify
            expected_amount: Expected USDT amount
            expected_recipient: Expected recipient address
            tolerance: Acceptable amount deviation (default 1%)

        Returns:
            Verification result with status and details
        """
        params = {
            "module": "proxy",
            "action": "eth_getTransactionReceipt",
            "txhash": tx_hash,
            "apikey": self.api_key
        }

        try:
            response = await self.client.get(self.BSC_API_URL, params=params)
            data = response.json()

            if not data.get("result"):
                return {
                    "verified": False,
                    "reason": "Transaction not found"
                }

            receipt = data["result"]

            # Check if transaction succeeded
            if receipt.get("status") != "0x1":
                return {
                    "verified": False,
                    "reason": "Transaction failed on blockchain"
                }

            # Get transaction details
            tx_details = await self._get_transaction_details(tx_hash)

            # Verify recipient
            if tx_details["to"].lower() != expected_recipient.lower():
                return {
                    "verified": False,
                    "reason": f"Wrong recipient: {tx_details['to']}"
                }

            # Verify amount (USDT has 18 decimals on BSC)
            actual_amount = int(tx_details["value"]) / 1e18
            amount_diff = abs(actual_amount - expected_amount)

            if amount_diff > (expected_amount * tolerance):
                return {
                    "verified": False,
                    "reason": f"Amount mismatch: expected {expected_amount}, got {actual_amount}"
                }

            # Check confirmations
            current_block = await self._get_current_block()
            tx_block = int(receipt["blockNumber"], 16)
            confirmations = current_block - tx_block

            if confirmations < self.MIN_CONFIRMATIONS:
                return {
                    "verified": False,
                    "reason": f"Insufficient confirmations: {confirmations}/{self.MIN_CONFIRMATIONS}",
                    "confirmations": confirmations
                }

            # All checks passed
            return {
                "verified": True,
                "tx_hash": tx_hash,
                "from": tx_details["from"],
                "to": tx_details["to"],
                "amount": actual_amount,
                "confirmations": confirmations,
                "timestamp": int(receipt["timestamp"], 16) if "timestamp" in receipt else None,
                "block_number": tx_block
            }

        except Exception as e:
            return {
                "verified": False,
                "reason": f"Verification error: {str(e)}"
            }

    async def _get_transaction_details(self, tx_hash: str) -> Dict:
        """Get detailed transaction information"""
        params = {
            "module": "proxy",
            "action": "eth_getTransactionByHash",
            "txhash": tx_hash,
            "apikey": self.api_key
        }

        response = await self.client.get(self.BSC_API_URL, params=params)
        return response.json()["result"]

    async def _get_current_block(self) -> int:
        """Get current block number"""
        params = {
            "module": "proxy",
            "action": "eth_blockNumber",
            "apikey": self.api_key
        }

        response = await self.client.get(self.BSC_API_URL, params=params)
        return int(response.json()["result"], 16)

    async def monitor_payment(
        self,
        payment_id: str,
        expected_amount: float,
        timeout_minutes: int = 30
    ) -> Optional[Dict]:
        """
        Monitor for a specific payment with timeout

        Args:
            payment_id: Unique payment identifier
            expected_amount: Expected USDT amount
            timeout_minutes: How long to wait for payment

        Returns:
            Transaction details if found and verified, None otherwise
        """
        start_time = datetime.utcnow()
        timeout = timedelta(minutes=timeout_minutes)
        check_interval = 10  # Check every 10 seconds

        print(f"🔍 Monitoring BSC for payment {payment_id}: {expected_amount} USDT")

        while datetime.utcnow() - start_time < timeout:
            # Fetch recent transactions
            since_timestamp = int((start_time - timedelta(minutes=5)).timestamp())
            transactions = await self.get_recent_transactions(since_timestamp)

            # Check each transaction
            for tx in transactions:
                tx_amount = int(tx["value"]) / 1e18

                # Amount match with 1% tolerance
                if abs(tx_amount - expected_amount) <= (expected_amount * 0.01):
                    # Verify the transaction
                    verification = await self.verify_transaction(
                        tx["hash"],
                        expected_amount,
                        self.wallet_address
                    )

                    if verification["verified"]:
                        print(f"✅ Payment {payment_id} verified: {tx['hash']}")
                        return verification

            # Wait before next check
            await asyncio.sleep(check_interval)

        print(f"⏰ Payment {payment_id} monitoring timeout")
        return None
```

#### Method 2: Web3.py Direct Node Connection

**Use when:**
- Need real-time updates (<1 second)
- High transaction volume
- Want full control

**Python Implementation:**

```python
from web3 import Web3
import json

class BSCWeb3Monitor:
    """Direct blockchain monitoring using Web3.py"""

    BSC_RPC = "https://bsc-dataseed.binance.org/"
    USDT_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"

    # USDT ABI (Transfer event signature)
    TRANSFER_EVENT_SIGNATURE = Web3.keccak(text="Transfer(address,address,uint256)").hex()

    def __init__(self, wallet_address: str):
        self.w3 = Web3(Web3.HTTPProvider(self.BSC_RPC))
        self.wallet_address = Web3.to_checksum_address(wallet_address)
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.USDT_CONTRACT),
            abi=self._get_usdt_abi()
        )

    def get_latest_block(self) -> int:
        """Get current block number"""
        return self.w3.eth.block_number

    def get_usdt_balance(self, address: str) -> float:
        """Get USDT balance for address"""
        balance = self.contract.functions.balanceOf(
            Web3.to_checksum_address(address)
        ).call()
        return balance / 1e18  # 18 decimals

    def get_transfer_events(
        self,
        from_block: int,
        to_block: int = 'latest'
    ) -> List[Dict]:
        """
        Get USDT transfer events to monitored address

        Args:
            from_block: Starting block number
            to_block: Ending block (default: latest)

        Returns:
            List of transfer events
        """
        # Filter for Transfer events to our address
        transfer_filter = self.contract.events.Transfer.create_filter(
            fromBlock=from_block,
            toBlock=to_block,
            argument_filters={'to': self.wallet_address}
        )

        events = transfer_filter.get_all_entries()

        return [
            {
                "tx_hash": event["transactionHash"].hex(),
                "from": event["args"]["from"],
                "to": event["args"]["to"],
                "amount": event["args"]["value"] / 1e18,
                "block_number": event["blockNumber"],
                "timestamp": self.w3.eth.get_block(event["blockNumber"])["timestamp"]
            }
            for event in events
        ]

    def _get_usdt_abi(self) -> List:
        """Minimal USDT ABI for Transfer events"""
        return [
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "name": "from", "type": "address"},
                    {"indexed": True, "name": "to", "type": "address"},
                    {"indexed": False, "name": "value", "type": "uint256"}
                ],
                "name": "Transfer",
                "type": "event"
            },
            {
                "constant": True,
                "inputs": [{"name": "who", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            }
        ]
```

---

### Tron (TRC-20) Transaction Monitoring

#### Method 1: TronGrid API (Recommended)

**Advantages:**
- ✅ Free tier available
- ✅ Official Tron Foundation API
- ✅ Real-time updates
- ✅ No node required

**API Endpoint:**
```
https://api.trongrid.io/v1/accounts/{address}/transactions/trc20
?only_to=true
&limit=20
&contract_address=TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t
```

**Python Implementation:**

```python
import httpx
import base58
from typing import List, Dict, Optional
from datetime import datetime, timedelta

class TronTransactionMonitor:
    """Monitor USDT TRC-20 transactions on Tron network"""

    TRON_API_URL = "https://api.trongrid.io"
    USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    MIN_CONFIRMATIONS = 19  # ~57 seconds on Tron (19 blocks * 3 sec)

    def __init__(self, api_key: str, wallet_address: str):
        self.api_key = api_key
        self.wallet_address = wallet_address
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"TRON-PRO-API-KEY": api_key} if api_key else {}
        )

    async def get_recent_transactions(
        self,
        only_to: bool = True,
        limit: int = 20
    ) -> List[Dict]:
        """
        Fetch recent USDT TRC-20 transactions

        Args:
            only_to: Only get incoming transactions
            limit: Maximum number of transactions

        Returns:
            List of transaction dictionaries
        """
        endpoint = f"{self.TRON_API_URL}/v1/accounts/{self.wallet_address}/transactions/trc20"

        params = {
            "only_to": str(only_to).lower(),
            "limit": limit,
            "contract_address": self.USDT_CONTRACT
        }

        try:
            response = await self.client.get(endpoint, params=params)
            data = response.json()

            if not data.get("success", True):
                raise Exception(f"TronGrid API error: {data}")

            return data.get("data", [])

        except Exception as e:
            print(f"❌ Error fetching Tron transactions: {e}")
            return []

    async def verify_transaction(
        self,
        tx_id: str,
        expected_amount: float,
        expected_recipient: str,
        tolerance: float = 0.01
    ) -> Dict[str, any]:
        """
        Verify a specific Tron transaction

        Args:
            tx_id: Transaction ID to verify
            expected_amount: Expected USDT amount
            expected_recipient: Expected recipient address
            tolerance: Acceptable amount deviation

        Returns:
            Verification result
        """
        endpoint = f"{self.TRON_API_URL}/wallet/gettransactioninfobyid"

        try:
            # Get transaction info
            response = await self.client.post(
                endpoint,
                json={"value": tx_id}
            )
            tx_info = response.json()

            if not tx_info:
                return {
                    "verified": False,
                    "reason": "Transaction not found"
                }

            # Check if transaction succeeded
            if tx_info.get("receipt", {}).get("result") != "SUCCESS":
                return {
                    "verified": False,
                    "reason": "Transaction failed on blockchain"
                }

            # Get transaction details
            tx_response = await self.client.post(
                f"{self.TRON_API_URL}/wallet/gettransactionbyid",
                json={"value": tx_id}
            )
            tx_details = tx_response.json()

            # Parse contract parameters
            if "raw_data" not in tx_details:
                return {
                    "verified": False,
                    "reason": "Invalid transaction format"
                }

            contract = tx_details["raw_data"]["contract"][0]
            parameter = contract["parameter"]["value"]

            # Verify recipient
            to_address = self._hex_to_base58(parameter["to"])
            if to_address != expected_recipient:
                return {
                    "verified": False,
                    "reason": f"Wrong recipient: {to_address}"
                }

            # Verify amount (USDT has 6 decimals on Tron)
            actual_amount = int(parameter["amount"]) / 1e6
            amount_diff = abs(actual_amount - expected_amount)

            if amount_diff > (expected_amount * tolerance):
                return {
                    "verified": False,
                    "reason": f"Amount mismatch: expected {expected_amount}, got {actual_amount}"
                }

            # Check confirmations
            current_block = await self._get_current_block()
            tx_block = tx_info.get("blockNumber", 0)
            confirmations = current_block - tx_block

            if confirmations < self.MIN_CONFIRMATIONS:
                return {
                    "verified": False,
                    "reason": f"Insufficient confirmations: {confirmations}/{self.MIN_CONFIRMATIONS}",
                    "confirmations": confirmations
                }

            # All checks passed
            return {
                "verified": True,
                "tx_id": tx_id,
                "from": self._hex_to_base58(parameter["owner_address"]),
                "to": to_address,
                "amount": actual_amount,
                "confirmations": confirmations,
                "timestamp": tx_info.get("blockTimeStamp", 0) // 1000,
                "block_number": tx_block,
                "energy_fee": tx_info.get("receipt", {}).get("energy_fee", 0) / 1e6,
                "energy_usage": tx_info.get("receipt", {}).get("energy_usage_total", 0)
            }

        except Exception as e:
            return {
                "verified": False,
                "reason": f"Verification error: {str(e)}"
            }

    async def _get_current_block(self) -> int:
        """Get current block height"""
        response = await self.client.post(
            f"{self.TRON_API_URL}/wallet/getnowblock"
        )
        data = response.json()
        return data.get("block_header", {}).get("raw_data", {}).get("number", 0)

    def _hex_to_base58(self, hex_address: str) -> str:
        """Convert hex address to Base58 Tron address"""
        if hex_address.startswith("41"):
            hex_address = hex_address[2:]

        # Add Tron prefix (0x41)
        address_bytes = bytes.fromhex("41" + hex_address)
        return base58.b58encode_check(address_bytes).decode()

    async def monitor_payment(
        self,
        payment_id: str,
        expected_amount: float,
        timeout_minutes: int = 30
    ) -> Optional[Dict]:
        """
        Monitor for a specific payment with timeout

        Args:
            payment_id: Unique payment identifier
            expected_amount: Expected USDT amount
            timeout_minutes: How long to wait for payment

        Returns:
            Transaction details if found and verified
        """
        start_time = datetime.utcnow()
        timeout = timedelta(minutes=timeout_minutes)
        check_interval = 5  # Check every 5 seconds (Tron is faster)

        print(f"🔍 Monitoring Tron for payment {payment_id}: {expected_amount} USDT")

        while datetime.utcnow() - start_time < timeout:
            # Fetch recent transactions
            transactions = await self.get_recent_transactions()

            # Check each transaction
            for tx in transactions:
                # Amount is in smallest unit (6 decimals for USDT)
                tx_amount = float(tx["value"]) / 1e6

                # Amount match with 1% tolerance
                if abs(tx_amount - expected_amount) <= (expected_amount * 0.01):
                    # Verify the transaction
                    verification = await self.verify_transaction(
                        tx["transaction_id"],
                        expected_amount,
                        self.wallet_address
                    )

                    if verification["verified"]:
                        print(f"✅ Payment {payment_id} verified: {tx['transaction_id']}")
                        return verification

            # Wait before next check
            await asyncio.sleep(check_interval)

        print(f"⏰ Payment {payment_id} monitoring timeout")
        return None
```

---

### Unified Payment Monitor Service

**Integration of both BSC and Tron monitoring:**

```python
import asyncio
from enum import Enum
from typing import Optional, Dict

class BlockchainNetwork(str, Enum):
    BSC = "bsc"
    TRON = "tron"

class CryptoPaymentMonitor:
    """Unified monitor for both BSC and Tron USDT payments"""

    def __init__(
        self,
        bsc_api_key: str,
        tron_api_key: str,
        bsc_wallet: str,
        tron_wallet: str
    ):
        self.bsc_monitor = BSCTransactionMonitor(bsc_api_key, bsc_wallet)
        self.tron_monitor = TronTransactionMonitor(tron_api_key, tron_wallet)

    async def monitor_payment(
        self,
        payment_id: str,
        network: BlockchainNetwork,
        expected_amount: float,
        timeout_minutes: int = 30
    ) -> Optional[Dict]:
        """
        Monitor payment on specified network

        Args:
            payment_id: Unique payment identifier
            network: Which blockchain to monitor (BSC or Tron)
            expected_amount: Expected USDT amount
            timeout_minutes: How long to wait

        Returns:
            Verified transaction details or None
        """
        if network == BlockchainNetwork.BSC:
            return await self.bsc_monitor.monitor_payment(
                payment_id,
                expected_amount,
                timeout_minutes
            )
        elif network == BlockchainNetwork.TRON:
            return await self.tron_monitor.monitor_payment(
                payment_id,
                expected_amount,
                timeout_minutes
            )
        else:
            raise ValueError(f"Unsupported network: {network}")

    async def verify_transaction(
        self,
        network: BlockchainNetwork,
        tx_hash: str,
        expected_amount: float,
        expected_recipient: str
    ) -> Dict:
        """Verify transaction on specified network"""
        if network == BlockchainNetwork.BSC:
            return await self.bsc_monitor.verify_transaction(
                tx_hash,
                expected_amount,
                expected_recipient
            )
        elif network == BlockchainNetwork.TRON:
            return await self.tron_monitor.verify_transaction(
                tx_hash,
                expected_amount,
                expected_recipient
            )
        else:
            raise ValueError(f"Unsupported network: {network}")
```

---

### Background Monitoring Service (Celery Task)

**For production deployment, run monitoring as background tasks:**

```python
from celery import Celery
from datetime import datetime

celery_app = Celery('crypto_payments', broker='redis://localhost:6379/0')

@celery_app.task(bind=True, max_retries=3)
def monitor_crypto_payment_task(
    self,
    payment_id: str,
    network: str,
    expected_amount: float,
    user_id: str,
    timeout_minutes: int = 30
):
    """
    Background task to monitor crypto payment

    This runs independently and updates database when payment is confirmed
    """
    try:
        # Initialize monitor
        monitor = CryptoPaymentMonitor(
            bsc_api_key=settings.BSC_API_KEY,
            tron_api_key=settings.TRON_API_KEY,
            bsc_wallet=settings.BSC_WALLET_ADDRESS,
            tron_wallet=settings.TRON_WALLET_ADDRESS
        )

        # Monitor payment (blocking call with timeout)
        result = asyncio.run(
            monitor.monitor_payment(
                payment_id,
                BlockchainNetwork(network),
                expected_amount,
                timeout_minutes
            )
        )

        if result and result["verified"]:
            # Payment confirmed - credit user account
            credit_user_payment(
                user_id=user_id,
                payment_id=payment_id,
                amount_usdt=expected_amount,
                tx_hash=result["tx_hash"] if network == "bsc" else result["tx_id"],
                network=network,
                confirmations=result["confirmations"]
            )

            # Send notification
            send_payment_success_notification(user_id, payment_id)

            return {"status": "success", "tx": result}
        else:
            # Payment timeout or failed
            mark_payment_timeout(payment_id)
            send_payment_timeout_notification(user_id, payment_id)

            return {"status": "timeout"}

    except Exception as e:
        # Retry on error
        raise self.retry(exc=e, countdown=60)
```

---

### Verification Checklist

Before crediting user account, verify:

1. ✅ **Correct Recipient:** Transaction sent to our wallet address
2. ✅ **Correct Amount:** Matches expected amount (±1% tolerance)
3. ✅ **Correct Token:** USDT contract address (not other tokens)
4. ✅ **Sufficient Confirmations:**
   - BSC: 12 confirmations (~36 seconds)
   - Tron: 19 confirmations (~57 seconds)
5. ✅ **Transaction Success:** Receipt status = SUCCESS
6. ✅ **Not Already Processed:** Check database for duplicate tx_hash
7. ✅ **Within Timeout:** Transaction timestamp < payment expiry time

---

## 🔧 Technology Stack

### Frontend Libraries:

#### 1. **Web3.js / Ethers.js**
```bash
npm install ethers@6
```

**Purpose:** Interact với Ethereum-compatible blockchains (bao gồm cả Tron qua adapters)

**Key Features:**
- Connect to wallet providers (Metamask, WalletConnect)
- Sign transactions
- Check wallet balance
- Estimate gas fees
- Send USDT transfers

**Example Usage:**
```typescript
import { ethers } from 'ethers';

// Connect to Metamask
const provider = new ethers.BrowserProvider(window.ethereum);
const signer = await provider.getSigner();
const address = await signer.getAddress();

// Get USDT balance
const usdtContract = new ethers.Contract(
  USDT_CONTRACT_ADDRESS,
  USDT_ABI,
  signer
);
const balance = await usdtContract.balanceOf(address);
```

#### 2. **TronWeb**
```bash
npm install tronweb
```

**Purpose:** Interact với Tron blockchain (TRC20)

**Key Features:**
- Connect to TronLink wallet
- Send TRC20 USDT
- Check transaction status
- Lower-level control cho Tron network

**Example Usage:**
```typescript
import TronWeb from 'tronweb';

// Connect to TronLink
const tronWeb = window.tronWeb;
const address = tronWeb.defaultAddress.base58;

// Send USDT
const contract = await tronWeb.contract().at(USDT_TRC20_ADDRESS);
const tx = await contract.transfer(
  RECIPIENT_ADDRESS,
  amount
).send();
```

#### 3. **WalletConnect v2**
```bash
npm install @walletconnect/web3-provider
npm install @walletconnect/modal
```

**Purpose:** Support mobile wallets (Trust Wallet, Rainbow, etc.)

**Key Features:**
- QR code connection
- Deep linking to mobile apps
- Multi-wallet support
- Better mobile UX

**Example Usage:**
```typescript
import { WalletConnectModal } from '@walletconnect/modal';
import { EthereumProvider } from '@walletconnect/ethereum-provider';

const provider = await EthereumProvider.init({
  projectId: 'YOUR_PROJECT_ID',
  chains: [1, 137], // Ethereum, Polygon
  showQrModal: true
});

await provider.connect();
```

#### 4. **RainbowKit** (Optional - Enhanced UX)
```bash
npm install @rainbow-me/rainbowkit wagmi viem
```

**Purpose:** Beautiful, pre-built wallet connection UI

**Key Features:**
- Pre-designed wallet selection modal
- Built-in wallet icons and branding
- Responsive design
- Support 100+ wallets
- Recent transactions display

**Pros:**
- ✅ Professional UI out of the box
- ✅ Handle edge cases (wrong network, disconnection)
- ✅ Active maintenance
- ✅ TypeScript support

**Cons:**
- ❌ Larger bundle size
- ❌ Less customization
- ❌ Learning curve với wagmi/viem

---

## 💻 Frontend Implementation

### Component Structure:

```
src/
├── components/
│   └── CryptoPayment/
│       ├── CryptoPaymentModal.tsx          # Main modal
│       ├── WalletConnectionButton.tsx      # Connect wallet button
│       ├── NetworkSelector.tsx             # TRC20/ERC20 selection
│       ├── PaymentConfirmation.tsx         # Review before send
│       ├── TransactionStatus.tsx           # Tracking TX status
│       └── WalletBalance.tsx               # Show user's USDT balance
├── hooks/
│   ├── useWallet.ts                        # Wallet connection logic
│   ├── useCryptoPayment.ts                 # Payment flow logic
│   └── useTransactionMonitor.ts            # Monitor TX status
├── services/
│   ├── web3Service.ts                      # Ethers.js wrapper
│   ├── tronService.ts                      # TronWeb wrapper
│   └── cryptoPaymentService.ts             # Backend API calls
└── constants/
    └── contracts.ts                        # Contract addresses & ABIs
```

---

## 📝 Step-by-Step Implementation

### Phase 1: Wallet Connection (Week 1)

#### 1.1 Install Dependencies
```bash
npm install ethers@6 tronweb @walletconnect/ethereum-provider
npm install -D @types/tronweb
```

#### 1.2 Create Wallet Service (`src/services/web3Service.ts`)

```typescript
import { ethers } from 'ethers';

export class Web3Service {
  private provider: ethers.BrowserProvider | null = null;
  private signer: ethers.Signer | null = null;

  async connectMetamask(): Promise<string> {
    if (!window.ethereum) {
      throw new Error('Metamask not installed');
    }

    this.provider = new ethers.BrowserProvider(window.ethereum);

    // Request account access
    await window.ethereum.request({ method: 'eth_requestAccounts' });

    this.signer = await this.provider.getSigner();
    const address = await this.signer.getAddress();

    return address;
  }

  async getBalance(tokenAddress: string, walletAddress: string): Promise<string> {
    if (!this.provider) throw new Error('Provider not initialized');

    const contract = new ethers.Contract(
      tokenAddress,
      ['function balanceOf(address) view returns (uint256)'],
      this.provider
    );

    const balance = await contract.balanceOf(walletAddress);
    return ethers.formatUnits(balance, 6); // USDT has 6 decimals
  }

  async sendUSDT(
    tokenAddress: string,
    recipientAddress: string,
    amount: string
  ): Promise<string> {
    if (!this.signer) throw new Error('Signer not initialized');

    const contract = new ethers.Contract(
      tokenAddress,
      [
        'function transfer(address to, uint256 amount) returns (bool)',
        'function allowance(address owner, address spender) view returns (uint256)',
        'function approve(address spender, uint256 amount) returns (bool)'
      ],
      this.signer
    );

    const amountInWei = ethers.parseUnits(amount, 6);

    // Send transaction
    const tx = await contract.transfer(recipientAddress, amountInWei);

    return tx.hash;
  }

  async waitForTransaction(txHash: string): Promise<boolean> {
    if (!this.provider) throw new Error('Provider not initialized');

    const receipt = await this.provider.waitForTransaction(txHash, 1);
    return receipt?.status === 1;
  }
}

export const web3Service = new Web3Service();
```

#### 1.3 Create Tron Service (`src/services/tronService.ts`)

```typescript
import TronWeb from 'tronweb';

export class TronService {
  private tronWeb: any;

  async connectTronLink(): Promise<string> {
    if (!window.tronWeb) {
      throw new Error('TronLink not installed');
    }

    // Wait for TronLink to inject
    let attempts = 0;
    while (!window.tronWeb.ready && attempts < 50) {
      await new Promise(resolve => setTimeout(resolve, 100));
      attempts++;
    }

    if (!window.tronWeb.ready) {
      throw new Error('TronLink not ready');
    }

    this.tronWeb = window.tronWeb;
    return this.tronWeb.defaultAddress.base58;
  }

  async getUSDTBalance(walletAddress: string): Promise<string> {
    const contract = await this.tronWeb.contract().at(
      'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t' // USDT TRC20 address
    );

    const balance = await contract.balanceOf(walletAddress).call();
    return (balance.toNumber() / 1e6).toString(); // USDT has 6 decimals
  }

  async sendUSDT(recipientAddress: string, amount: string): Promise<string> {
    const contract = await this.tronWeb.contract().at(
      'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t'
    );

    const amountInSun = Math.floor(parseFloat(amount) * 1e6);

    const tx = await contract.transfer(
      recipientAddress,
      amountInSun
    ).send();

    return tx;
  }

  async getTransactionInfo(txId: string): Promise<any> {
    return await this.tronWeb.trx.getTransactionInfo(txId);
  }
}

export const tronService = new TronService();
```

#### 1.4 Create useWallet Hook (`src/hooks/useWallet.ts`)

```typescript
import { useState, useEffect } from 'react';
import { web3Service } from '@/services/web3Service';
import { tronService } from '@/services/tronService';

type WalletType = 'metamask' | 'tronlink' | 'walletconnect' | null;
type NetworkType = 'erc20' | 'trc20';

export function useWallet() {
  const [walletType, setWalletType] = useState<WalletType>(null);
  const [network, setNetwork] = useState<NetworkType>('trc20');
  const [address, setAddress] = useState<string | null>(null);
  const [balance, setBalance] = useState<string>('0');
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connectWallet = async (type: WalletType) => {
    setIsConnecting(true);
    setError(null);

    try {
      let walletAddress: string;

      if (type === 'metamask') {
        walletAddress = await web3Service.connectMetamask();
        setNetwork('erc20');
      } else if (type === 'tronlink') {
        walletAddress = await tronService.connectTronLink();
        setNetwork('trc20');
      } else {
        throw new Error('Unsupported wallet type');
      }

      setAddress(walletAddress);
      setWalletType(type);

      // Fetch balance
      await fetchBalance(walletAddress);
    } catch (err: any) {
      console.error('Wallet connection error:', err);
      setError(err.message || 'Failed to connect wallet');
    } finally {
      setIsConnecting(false);
    }
  };

  const fetchBalance = async (walletAddress?: string) => {
    const addr = walletAddress || address;
    if (!addr) return;

    try {
      let bal: string;
      if (network === 'erc20') {
        bal = await web3Service.getBalance(
          '0xdac17f958d2ee523a2206206994597c13d831ec7', // USDT ERC20
          addr
        );
      } else {
        bal = await tronService.getUSDTBalance(addr);
      }
      setBalance(bal);
    } catch (err) {
      console.error('Failed to fetch balance:', err);
    }
  };

  const disconnectWallet = () => {
    setAddress(null);
    setWalletType(null);
    setBalance('0');
  };

  return {
    walletType,
    network,
    address,
    balance,
    isConnecting,
    error,
    connectWallet,
    disconnectWallet,
    fetchBalance
  };
}
```

---

### Phase 2: Payment Flow (Week 2)

#### 2.1 Create Payment Service (`src/services/cryptoPaymentService.ts`)

```typescript
import { logger } from '@/lib/logger';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://ai.wordai.pro';

export interface CryptoPaymentIntent {
  payment_id: string;
  recipient_address: string; // Our wallet address
  amount_usdt: number;
  amount_vnd: number;
  points: number;
  network: 'trc20' | 'erc20';
  expires_at: string;
}

export interface CryptoPaymentConfirmation {
  success: boolean;
  transaction_id: string;
  status: 'pending' | 'confirming' | 'confirmed' | 'failed';
  confirmations: number;
  required_confirmations: number;
  points_credited: boolean;
}

export const cryptoPaymentService = {
  /**
   * Create payment intent
   */
  async createPaymentIntent(
    points: number,
    network: 'trc20' | 'erc20',
    walletAddress: string
  ): Promise<CryptoPaymentIntent> {
    logger.info('💰 Creating crypto payment intent', { points, network });

    const token = await getFirebaseToken();

    const response = await fetch(`${API_BASE_URL}/api/v1/payments/crypto/intent`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        points,
        network,
        wallet_address: walletAddress
      })
    });

    if (!response.ok) {
      throw new Error('Failed to create payment intent');
    }

    return await response.json();
  },

  /**
   * Submit transaction hash for verification
   */
  async submitTransaction(
    paymentId: string,
    txHash: string,
    network: 'trc20' | 'erc20'
  ): Promise<CryptoPaymentConfirmation> {
    logger.info('📝 Submitting crypto transaction', { paymentId, txHash });

    const token = await getFirebaseToken();

    const response = await fetch(`${API_BASE_URL}/api/v1/payments/crypto/submit`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        payment_id: paymentId,
        tx_hash: txHash,
        network
      })
    });

    if (!response.ok) {
      throw new Error('Failed to submit transaction');
    }

    return await response.json();
  },

  /**
   * Check transaction status
   */
  async checkTransactionStatus(
    paymentId: string
  ): Promise<CryptoPaymentConfirmation> {
    const token = await getFirebaseToken();

    const response = await fetch(
      `${API_BASE_URL}/api/v1/payments/crypto/status/${paymentId}`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    if (!response.ok) {
      throw new Error('Failed to check transaction status');
    }

    return await response.json();
  }
};

async function getFirebaseToken(): Promise<string> {
  const { wordaiAuth } = await import('@/lib/wordai-firebase');
  const user = wordaiAuth.currentUser;
  if (!user) throw new Error('Not authenticated');
  return await user.getIdToken();
}
```

#### 2.2 Create useCryptoPayment Hook (`src/hooks/useCryptoPayment.ts`)

```typescript
import { useState } from 'react';
import { web3Service } from '@/services/web3Service';
import { tronService } from '@/services/tronService';
import { cryptoPaymentService } from '@/services/cryptoPaymentService';
import { logger } from '@/lib/logger';

export function useCryptoPayment() {
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentStep, setCurrentStep] = useState<
    'idle' | 'creating' | 'signing' | 'submitting' | 'confirming' | 'completed' | 'failed'
  >('idle');
  const [txHash, setTxHash] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const processPayment = async (
    points: number,
    network: 'trc20' | 'erc20',
    walletAddress: string
  ) => {
    setIsProcessing(true);
    setError(null);
    setCurrentStep('creating');

    try {
      // Step 1: Create payment intent
      logger.info('Step 1: Creating payment intent');
      const intent = await cryptoPaymentService.createPaymentIntent(
        points,
        network,
        walletAddress
      );

      // Step 2: Sign and send transaction
      setCurrentStep('signing');
      logger.info('Step 2: Signing transaction');

      let hash: string;
      if (network === 'erc20') {
        hash = await web3Service.sendUSDT(
          '0xdac17f958d2ee523a2206206994597c13d831ec7', // USDT ERC20
          intent.recipient_address,
          intent.amount_usdt.toString()
        );
      } else {
        hash = await tronService.sendUSDT(
          intent.recipient_address,
          intent.amount_usdt.toString()
        );
      }

      setTxHash(hash);

      // Step 3: Submit to backend
      setCurrentStep('submitting');
      logger.info('Step 3: Submitting transaction to backend', { hash });

      await cryptoPaymentService.submitTransaction(
        intent.payment_id,
        hash,
        network
      );

      // Step 4: Wait for confirmation
      setCurrentStep('confirming');
      logger.info('Step 4: Waiting for blockchain confirmation');

      // Poll for status
      let confirmed = false;
      let attempts = 0;
      const maxAttempts = 60; // 5 minutes with 5s interval

      while (!confirmed && attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 5000));

        const status = await cryptoPaymentService.checkTransactionStatus(
          intent.payment_id
        );

        if (status.status === 'confirmed' && status.points_credited) {
          confirmed = true;
          setCurrentStep('completed');
          logger.info('✅ Payment completed successfully');
        } else if (status.status === 'failed') {
          throw new Error('Transaction failed');
        }

        attempts++;
      }

      if (!confirmed) {
        throw new Error('Transaction confirmation timeout');
      }

    } catch (err: any) {
      console.error('Payment error:', err);
      setError(err.message || 'Payment failed');
      setCurrentStep('failed');
    } finally {
      setIsProcessing(false);
    }
  };

  const reset = () => {
    setCurrentStep('idle');
    setTxHash(null);
    setError(null);
    setIsProcessing(false);
  };

  return {
    processPayment,
    isProcessing,
    currentStep,
    txHash,
    error,
    reset
  };
}
```

---

### Phase 3: UI Components (Week 3)

#### 3.1 Main Modal (`src/components/CryptoPayment/CryptoPaymentModal.tsx`)

```typescript
'use client';

import React, { useState } from 'react';
import { X } from 'lucide-react';
import { useWallet } from '@/hooks/useWallet';
import { useCryptoPayment } from '@/hooks/useCryptoPayment';
import { WalletConnectionButton } from './WalletConnectionButton';
import { NetworkSelector } from './NetworkSelector';
import { PaymentConfirmation } from './PaymentConfirmation';
import { TransactionStatus } from './TransactionStatus';

interface CryptoPaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  points: number;
  amountVND: number;
  isDark: boolean;
  language: 'vi' | 'en';
}

export const CryptoPaymentModal: React.FC<CryptoPaymentModalProps> = ({
  isOpen,
  onClose,
  points,
  amountVND,
  isDark,
  language
}) => {
  const t = (vi: string, en: string) => language === 'vi' ? vi : en;

  const {
    walletType,
    network,
    address,
    balance,
    isConnecting,
    error: walletError,
    connectWallet,
    disconnectWallet
  } = useWallet();

  const {
    processPayment,
    isProcessing,
    currentStep,
    txHash,
    error: paymentError,
    reset
  } = useCryptoPayment();

  const [showConfirmation, setShowConfirmation] = useState(false);

  if (!isOpen) return null;

  const handleConfirmPayment = async () => {
    if (!address) return;

    setShowConfirmation(false);
    await processPayment(points, network, address);
  };

  const handleClose = () => {
    if (currentStep === 'completed') {
      window.location.reload(); // Refresh to update points
    }
    onClose();
    reset();
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className={`w-full max-w-2xl rounded-xl shadow-2xl ${
        isDark ? 'bg-gray-800' : 'bg-white'
      } max-h-[90vh] overflow-hidden flex flex-col`}>
        {/* Header */}
        <div className={`px-6 py-4 border-b flex items-center justify-between ${
          isDark ? 'border-gray-700' : 'border-gray-200'
        }`}>
          <h2 className={`text-xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>
            {t('Thanh toán bằng Crypto', 'Crypto Payment')}
          </h2>
          <button onClick={handleClose} className="p-2 rounded-lg hover:bg-gray-700">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {!address ? (
            /* Step 1: Connect Wallet */
            <div>
              <h3 className="text-lg font-semibold mb-4">
                {t('Bước 1: Kết nối ví', 'Step 1: Connect Wallet')}
              </h3>
              <WalletConnectionButton
                onConnect={connectWallet}
                isConnecting={isConnecting}
                error={walletError}
                isDark={isDark}
                language={language}
              />
            </div>
          ) : currentStep === 'idle' || currentStep === 'creating' ? (
            /* Step 2: Review & Confirm */
            <PaymentConfirmation
              points={points}
              amountVND={amountVND}
              network={network}
              walletAddress={address}
              balance={balance}
              onConfirm={() => setShowConfirmation(true)}
              onDisconnect={disconnectWallet}
              isDark={isDark}
              language={language}
            />
          ) : (
            /* Step 3: Transaction Status */
            <TransactionStatus
              currentStep={currentStep}
              txHash={txHash}
              network={network}
              error={paymentError}
              isDark={isDark}
              language={language}
            />
          )}
        </div>
      </div>

      {/* Confirmation Dialog */}
      {showConfirmation && (
        <div className="fixed inset-0 bg-black/70 z-[60] flex items-center justify-center p-4">
          <div className={`p-6 rounded-xl ${isDark ? 'bg-gray-700' : 'bg-white'}`}>
            <h3 className="text-lg font-bold mb-4">
              {t('Xác nhận thanh toán?', 'Confirm payment?')}
            </h3>
            <div className="flex gap-4">
              <button
                onClick={() => setShowConfirmation(false)}
                className="px-6 py-2 rounded-lg bg-gray-600 hover:bg-gray-700 text-white"
              >
                {t('Hủy', 'Cancel')}
              </button>
              <button
                onClick={handleConfirmPayment}
                className="px-6 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white"
              >
                {t('Xác nhận', 'Confirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
```

---

## 🔐 Backend Implementation

### API Endpoints cần thiết:

#### 1. **POST /api/v1/payments/crypto/intent**
Create payment intent và return recipient address

**Request:**
```json
{
  "points": 100,
  "network": "trc20",
  "wallet_address": "TXx..."
}
```

**Response:**
```json
{
  "payment_id": "pay_123abc",
  "recipient_address": "TYourAddress...",
  "amount_usdt": 95.00,
  "amount_vnd": 95000,
  "points": 100,
  "network": "trc20",
  "exchange_rate": 1000,
  "expires_at": "2025-12-01T10:30:00Z"
}
```

#### 2. **POST /api/v1/payments/crypto/submit**
Submit transaction hash để backend verify

**Request:**
```json
{
  "payment_id": "pay_123abc",
  "tx_hash": "0x123...",
  "network": "trc20"
}
```

**Response:**
```json
{
  "success": true,
  "transaction_id": "tx_456def",
  "status": "pending",
  "confirmations": 0,
  "required_confirmations": 19
}
```

#### 3. **GET /api/v1/payments/crypto/status/:paymentId**
Check transaction confirmation status

**Response:**
```json
{
  "success": true,
  "transaction_id": "tx_456def",
  "status": "confirmed",
  "confirmations": 19,
  "required_confirmations": 19,
  "points_credited": true,
  "credited_at": "2025-12-01T10:35:00Z"
}
```

### Backend Technology Stack:

#### Option 1: **Node.js với Web3.js/TronWeb** (Recommended)
```typescript
import { ethers } from 'ethers';
import TronWeb from 'tronweb';

// Monitor blockchain
const provider = new ethers.JsonRpcProvider(ETHEREUM_RPC_URL);

provider.on('block', async (blockNumber) => {
  // Check for our transactions
  const block = await provider.getBlock(blockNumber);
  // Process transactions...
});
```

**Pros:**
- ✅ Same language as frontend
- ✅ Direct blockchain interaction
- ✅ Real-time monitoring
- ✅ No external dependencies

**Cons:**
- ❌ Need to run persistent process
- ❌ Handle RPC rate limits
- ❌ Complex error handling

#### Option 2: **Webhook từ Third-party Service** (Easier)

Services như **Tatum**, **Moralis**, **Alchemy** cung cấp webhook cho transaction monitoring:

```typescript
// Tatum webhook example
app.post('/webhook/tatum/transaction', async (req, res) => {
  const { txId, address, amount, confirmations } = req.body;

  // Find payment by recipient address
  const payment = await Payment.findOne({ recipient_address: address });

  if (payment && confirmations >= REQUIRED_CONFIRMATIONS) {
    // Credit points
    await creditPoints(payment.user_id, payment.points);
    payment.status = 'confirmed';
    await payment.save();
  }

  res.json({ success: true });
});
```

**Pros:**
- ✅ Easy to implement
- ✅ Reliable delivery
- ✅ Handle confirmations automatically
- ✅ Multi-chain support

**Cons:**
- ❌ Dependency on third-party
- ❌ Monthly fees (usually free tier available)
- ❌ Privacy concerns (they see all transactions)

---

## 💰 Pricing & Fee Structure

### USDT Exchange Rate:
```
1 USDT ≈ 24,000 VND (current rate)
1 Point = 1,000 VND
1 Point ≈ 0.042 USDT

Example:
100 points = 100,000 VND = 4.17 USDT
```

### Transaction Fees:

#### TRC20 (Tron):
- **Gas fee:** ~1-5 TRX (≈ $0.10 - $0.50)
- **Bandwidth:** Free if user has energy/bandwidth
- **Speed:** 1-3 minutes (19 confirmations)
- **Recommendation:** Best for small transactions

#### ERC20 (Ethereum):
- **Gas fee:** ~$2-10 USD (varies by network congestion)
- **Speed:** 30 seconds - 2 minutes (12 confirmations)
- **Recommendation:** Better for large transactions

### Fee Handling Options:

**Option 1:** User pays gas fee separately
```
User pays: 4.17 USDT + gas fee
We receive: 4.17 USDT
Points credited: 100 points
```

**Option 2:** Deduct gas fee from amount
```
User pays: 4.17 USDT (including gas)
We receive: 4.15 USDT (after 0.02 USDT gas)
Points credited: 99 points
```

**Option 3:** We absorb gas fee (most user-friendly)
```
User pays: 4.17 USDT
We receive: 4.15 USDT (we pay 0.02 USDT gas)
Points credited: 100 points
Our cost: 0.02 USDT
```

**Recommendation:** Option 3 for better UX, add small markup to cover gas

---

## 🔒 Security Considerations

### 1. **Address Validation**
```typescript
// Validate Ethereum address
function isValidEthAddress(address: string): boolean {
  return ethers.isAddress(address);
}

// Validate Tron address
function isValidTronAddress(address: string): boolean {
  return TronWeb.isAddress(address);
}
```

### 2. **Amount Verification**
```typescript
// Verify transaction matches payment intent
async function verifyTransaction(txHash: string, expectedAmount: number) {
  const tx = await provider.getTransaction(txHash);
  const receipt = await provider.getTransactionReceipt(txHash);

  // Check success
  if (receipt.status !== 1) {
    throw new Error('Transaction failed');
  }

  // Check amount
  const actualAmount = parseFloat(ethers.formatUnits(tx.value, 6));
  if (Math.abs(actualAmount - expectedAmount) > 0.01) {
    throw new Error('Amount mismatch');
  }

  return true;
}
```

### 3. **Double-spending Prevention**
```typescript
// Mark transaction as used
const payment = await Payment.findOne({ tx_hash: txHash });
if (payment) {
  throw new Error('Transaction already processed');
}

// Save transaction hash
await Payment.create({
  tx_hash: txHash,
  user_id: userId,
  amount: amount,
  status: 'processing'
});
```

### 4. **Timeout Handling**
```typescript
// Payment intent expires after 15 minutes
const INTENT_EXPIRY = 15 * 60 * 1000;

if (Date.now() - intent.created_at > INTENT_EXPIRY) {
  throw new Error('Payment intent expired');
}
```

---

## 📊 Database Schema

```typescript
// MongoDB Schema
interface CryptoPayment {
  _id: ObjectId;
  payment_id: string;              // Unique payment identifier
  user_id: string;                 // Firebase UID

  // Payment details
  points: number;                  // Points to credit
  amount_vnd: number;              // Amount in VND
  amount_usdt: number;             // Amount in USDT
  network: 'trc20' | 'erc20';      // Blockchain network

  // Wallet addresses
  wallet_address: string;          // User's wallet
  recipient_address: string;       // Our wallet

  // Transaction details
  tx_hash: string | null;          // Blockchain TX hash
  confirmations: number;           // Current confirmations
  required_confirmations: number;  // Required confirmations (19 for TRC20, 12 for ERC20)

  // Status tracking
  status: 'pending' | 'confirming' | 'confirmed' | 'failed' | 'expired';
  points_credited: boolean;        // Whether points were added to user account

  // Timestamps
  created_at: Date;                // When intent was created
  submitted_at: Date | null;       // When TX hash was submitted
  confirmed_at: Date | null;       // When TX was confirmed
  expires_at: Date;                // When intent expires
}
```

---

## 🧪 Testing Strategy

### 1. **Testnet Testing**
- Use Ethereum Goerli testnet for ERC20
- Use Tron Nile testnet for TRC20
- Get test USDT from faucets

### 2. **Mock Wallet for Development**
```typescript
// Mock wallet service for testing
class MockWalletService {
  async connectMetamask() {
    return '0xMockAddress...';
  }

  async sendUSDT() {
    return '0xMockTxHash...';
  }
}
```

### 3. **Manual Testing Checklist**
- [ ] Connect Metamask successfully
- [ ] Connect TronLink successfully
- [ ] Display correct USDT balance
- [ ] Switch between TRC20/ERC20
- [ ] Calculate correct USDT amount
- [ ] Send transaction and get TX hash
- [ ] Backend receives and verifies TX
- [ ] Points credited after confirmation
- [ ] Handle insufficient balance
- [ ] Handle user rejection
- [ ] Handle network errors
- [ ] Handle timeout scenarios

---

## 📈 Success Metrics

### Key Performance Indicators:
1. **Conversion Rate:** % users who complete crypto payment
2. **Average Transaction Time:** From connect wallet to points credited
3. **Network Distribution:** TRC20 vs ERC20 usage
4. **Failed Transactions:** % of failed payments and reasons
5. **User Satisfaction:** Feedback on crypto payment UX

### Target Goals (Month 1):
- Conversion rate: >80%
- Avg transaction time: <5 minutes
- Failed transactions: <5%
- User adoption: 10% of purchases via crypto

---

## 🚀 Launch Plan

### Pre-launch (Week 0):
- [ ] Complete backend API development
- [ ] Deploy smart contract listener or webhook integration
- [ ] Test on testnets (Goerli, Nile)
- [ ] Create user documentation
- [ ] Train support team

### Soft Launch (Week 1-2):
- [ ] Enable for beta users only (whitelist)
- [ ] Monitor all transactions manually
- [ ] Collect feedback
- [ ] Fix bugs and UX issues

### Public Launch (Week 3+):
- [ ] Enable for all users
- [ ] Add announcement banner
- [ ] Monitor metrics daily
- [ ] A/B test CTA buttons and messaging

---

## 💡 Future Enhancements

### Phase 2 Features:
1. **More Cryptocurrencies:** ETH, BTC, BNB support
2. **Cross-chain Bridge:** Swap tokens automatically
3. **Recurring Payments:** Subscribe with crypto
4. **Referral Rewards:** Earn crypto for referrals
5. **Stablecoin Options:** USDC, BUSD, DAI support
6. **Mobile Wallet Deep Linking:** Direct app integration

### Phase 3 Features:
1. **Web3 Identity:** Login with wallet (no email needed)
2. **NFT Rewards:** Earn NFT badges for achievements
3. **DAO Governance:** Token holders vote on features
4. **DeFi Integration:** Stake tokens for premium features

---

## 📚 Resources

### Documentation:
- **Ethers.js:** https://docs.ethers.org/v6/
- **TronWeb:** https://developers.tron.network/docs
- **WalletConnect:** https://docs.walletconnect.com/
- **USDT Contract:** https://tether.to/en/transparency/

### Tools:
- **Remix IDE:** Test smart contracts
- **Etherscan:** Monitor Ethereum transactions
- **Tronscan:** Monitor Tron transactions
- **Metamask:** Browser wallet extension
- **TronLink:** Tron wallet extension

### Libraries:
- **ethers:** `npm install ethers@6`
- **tronweb:** `npm install tronweb`
- **@walletconnect/ethereum-provider:** `npm install @walletconnect/ethereum-provider`
- **@rainbow-me/rainbowkit:** `npm install @rainbow-me/rainbowkit wagmi viem`

---

## ✅ Conclusion

Tích hợp crypto wallet payment là một feature phức tạp nhưng mang lại nhiều lợi ích:

**Pros:**
- ✅ Mở rộng customer base toàn cầu
- ✅ Tự động hóa payment processing
- ✅ Phí giao dịch thấp (đặc biệt TRC20)
- ✅ Settlement nhanh (không cần chờ ngân hàng)
- ✅ Trendy và modern (thu hút crypto users)

**Cons:**
- ❌ Technical complexity cao
- ❌ Cần monitor blockchain liên tục
- ❌ Volatility của USDT rate
- ❌ Support burden (users new to crypto)
- ❌ Regulatory uncertainty ở Việt Nam

**Recommendation:**
- Start với **TRC20 only** (simpler, cheaper)
- Use **third-party service** (Tatum/Moralis) cho webhook
- Implement **manual approval** đầu tiên, sau đó auto
- Prepare **detailed FAQ** và video tutorials
- Monitor closely trong 1-2 tháng đầu

**Estimated Development Time:**
- Frontend: 2-3 weeks
- Backend: 2-3 weeks
- Testing: 1-2 weeks
- **Total: 5-8 weeks**

**Estimated Cost:**
- Development: Included in team salary
- Third-party service: $0-100/month (free tier usually enough)
- Gas fees: ~$50-200/month (if we absorb fees)
- **Total: ~$150-300/month operational cost**

---

**Document End**


## Current Payment System Overview

### Existing Architecture

**Payment Flow (VND/SePay):**
```
Frontend → Payment Service (Node.js) → SePay Gateway → IPN Webhook →
Backend Python API (/api/v1/subscriptions/activate)
```

**Current Pricing Structure:**

| Plan | 3 Months (VND) | 12 Months (VND) | Points 3mo | Points 12mo |
|------|----------------|-----------------|------------|-------------|
| Free | ₫0 | ₫0 | 20 | 20 |
| Premium | ₫279,000 | ₫990,000 | 300 | 1,200 |
| Pro | ₫447,000 | ₫1,699,000 | 500 | 2,000 |
| VIP | ₫747,000 | ₫2,799,000 | 1,000 | 4,000 |

**Points Purchase Packages (Existing):**
- 100 points = ₫100,000 (₫1,000/point)
- 500 points = ₫450,000 (₫900/point - 10% discount)
- 1000 points = ₫800,000 (₫800/point - 20% discount)
- 2000 points = ₫1,500,000 (₫750/point - 25% discount)

---

## USDT Payment Architecture

### Proposed System Design

**Technology Stack:**
- **Blockchain:** Ethereum, Binance Smart Chain (BSC), or Tron
- **Token Standard:** ERC-20 (Ethereum), BEP-20 (BSC), TRC-20 (Tron)
- **Frontend:** Web3.js or ethers.js for wallet connection
- **Backend:** Python web3.py library for transaction verification
- **Database:** MongoDB (existing) for payment tracking

**Recommended Network: Binance Smart Chain (BSC)**
- ✅ Low gas fees (~$0.10-0.50 per transaction)
- ✅ Fast confirmations (3 seconds per block)
- ✅ USDT widely available on BSC
- ✅ Compatible with MetaMask, Trust Wallet
- ✅ High liquidity and adoption in SEA region

**Alternative Networks:**
- **Ethereum:** Higher security, but expensive gas fees ($5-50)
- **Tron:** Very low fees, but less adoption
- **Polygon:** Low fees, growing adoption

---

## Payment Flow Design

### Frontend Wallet Integration

**Step 1: Connect Wallet**
```
User clicks "Pay with USDT" →
Modal opens with wallet options (MetaMask, Trust Wallet, WalletConnect) →
User connects wallet →
Frontend detects wallet address and network
```

**Required Frontend Libraries:**
```javascript
// Install dependencies
npm install ethers wagmi viem

// React components
import { useAccount, useConnect, useDisconnect } from 'wagmi'
import { MetaMaskConnector } from 'wagmi/connectors/metaMask'
import { WalletConnectConnector } from 'wagmi/connectors/walletConnect'
```

**Step 2: Display Conversion**
```
User selects plan: Premium 3 months
VND Price: ₫279,000
Exchange Rate: 1 USDT = 26,000 VND
USDT Price: 10.73 USDT (279,000 ÷ 26,000)
+ Gas Fee: ~0.5 USDT (estimated)
Total: ~11.23 USDT
```

**Step 3: Transaction Execution**
```javascript
// Frontend sends transaction
const tx = await usdtContract.transfer(
  WORDAI_WALLET_ADDRESS,
  ethers.utils.parseUnits(amount.toString(), 6) // USDT has 6 decimals
);

// Wait for confirmation
const receipt = await tx.wait();

// Send transaction hash to backend
await api.post('/api/v1/crypto-payments/verify', {
  txHash: receipt.transactionHash,
  userId: user.uid,
  plan: 'premium',
  duration: 3
});
```

### Backend Verification System

**New Endpoint:** `POST /api/v1/crypto-payments/verify`

**Verification Flow:**
1. Receive transaction hash from frontend
2. Query blockchain using web3.py
3. Verify transaction details:
   - Sender address matches user's connected wallet
   - Recipient address is WordAI's wallet
   - Amount matches expected USDT value (with ±2% tolerance)
   - Transaction is confirmed (minimum 3 blocks)
4. If valid → Activate subscription via existing `/subscriptions/activate` endpoint
5. Store payment record in MongoDB

**Python Implementation Pseudocode:**
```python
from web3 import Web3
from decimal import Decimal

# Connect to BSC
w3 = Web3(Web3.HTTPProvider('https://bsc-dataseed.binance.org/'))

# USDT Contract on BSC
USDT_CONTRACT = '0x55d398326f99059fF775485246999027B3197955'
WORDAI_WALLET = os.getenv('WORDAI_CRYPTO_WALLET')

@router.post("/crypto-payments/verify")
async def verify_crypto_payment(
    tx_hash: str,
    user_id: str,
    plan: str,
    duration: int,
    user_wallet: str
):
    # Get transaction receipt
    receipt = w3.eth.get_transaction_receipt(tx_hash)

    # Verify confirmations
    if receipt.blockNumber + 3 > w3.eth.block_number:
        raise HTTPException(400, "Transaction not confirmed")

    # Decode USDT transfer logs
    transfer_event = parse_transfer_event(receipt)

    # Verify details
    if transfer_event['to'].lower() != WORDAI_WALLET.lower():
        raise HTTPException(400, "Invalid recipient")

    amount_usdt = Decimal(transfer_event['value']) / Decimal(10**6)
    expected_usdt = calculate_usdt_price(plan, duration)

    # Allow 2% tolerance for exchange rate fluctuation
    if not (expected_usdt * 0.98 <= amount_usdt <= expected_usdt * 1.02):
        raise HTTPException(400, "Amount mismatch")

    # Activate subscription
    return await activate_subscription_internal(
        user_id=user_id,
        plan=plan,
        duration_months=duration,
        payment_method="USDT-BSC",
        tx_hash=tx_hash,
        amount_usdt=float(amount_usdt)
    )
```

---

## Pricing Conversion Table

### Subscription Plans (USDT)

**Exchange Rate: 1 USDT = 26,000 VND**

| Plan | Duration | VND Price | USDT Price | Points Granted |
|------|----------|-----------|------------|----------------|
| Premium | 3 months | ₫279,000 | 10.73 USDT | 300 |
| Premium | 12 months | ₫990,000 | 38.08 USDT | 1,200 |
| Pro | 3 months | ₫447,000 | 17.19 USDT | 500 |
| Pro | 12 months | ₫1,699,000 | 65.35 USDT | 2,000 |
| VIP | 3 months | ₫747,000 | 28.73 USDT | 1,000 |
| VIP | 12 months | ₫2,799,000 | 107.65 USDT | 4,000 |

### Points Packages (USDT)

| Points | VND Price | USDT Price | Discount |
|--------|-----------|------------|----------|
| 100 | ₫100,000 | 3.85 USDT | 0% |
| 500 | ₫450,000 | 17.31 USDT | 10% |
| 1,000 | ₫800,000 | 30.77 USDT | 20% |
| 2,000 | ₫1,500,000 | 57.69 USDT | 25% |

**Display Strategy:**
- Show both VND and USDT prices on payment page
- USDT price calculated dynamically based on current exchange rate
- Add note: "USDT price may vary slightly due to exchange rate fluctuation"

---

## Exchange Rate Management

### Dynamic Rate Updates

**Challenges:**
- USDT/VND rate fluctuates (typically ±1-3% daily)
- Need to protect against arbitrage or losses
- Must balance user experience with business risk

**Recommended Strategy:**

1. **Fetch Rate from Multiple Sources:**
   ```python
   async def get_usdt_vnd_rate():
       # Average from multiple exchanges
       binance_rate = await fetch_binance_usdt_vnd()
       remitano_rate = await fetch_remitano_usdt_vnd()

       # Use conservative rate (slightly higher)
       rate = max(binance_rate, remitano_rate) * 1.01

       # Cache for 5 minutes
       cache.set('usdt_vnd_rate', rate, ttl=300)
       return rate
   ```

2. **Rate Lock Window:**
   - User initiates payment → Rate locked for 10 minutes
   - If transaction completes within window → Use locked rate
   - If expired → User must restart payment

3. **Tolerance Buffer:**
   - Accept payments within ±2% of expected amount
   - Compensates for timing delays and rate fluctuations
   - Example: Expected 10 USDT → Accept 9.8-10.2 USDT

4. **Manual Adjustment:**
   - Admin can set minimum rate floor (e.g., 25,000 VND minimum)
   - Protects against sudden rate crashes
   - Update via environment variable: `MIN_USDT_VND_RATE=25000`

---

## Database Schema Extensions

### New Collection: `crypto_payments`

```javascript
{
  "_id": ObjectId("..."),
  "user_id": "firebase_uid_123",
  "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",

  // Transaction Details
  "tx_hash": "0x1234567890abcdef...",
  "blockchain": "BSC", // BSC, ETH, TRON
  "token": "USDT",
  "amount_usdt": 10.73,
  "amount_vnd": 279000,
  "exchange_rate": 26000,
  "gas_fee_usdt": 0.5,

  // Order Details
  "order_type": "subscription", // subscription | points_purchase
  "plan": "premium", // for subscriptions
  "duration_months": 3, // for subscriptions
  "points_purchased": null, // for points packages

  // Verification
  "status": "confirmed", // pending | confirmed | failed | refunded
  "confirmations": 15,
  "verified_at": ISODate("2025-12-01T10:30:00Z"),
  "verified_by": "auto",

  // Activation
  "subscription_activated": true,
  "subscription_id": "sub_xyz789",
  "activated_at": ISODate("2025-12-01T10:31:00Z"),

  // Timestamps
  "created_at": ISODate("2025-12-01T10:25:00Z"),
  "updated_at": ISODate("2025-12-01T10:31:00Z"),

  // Metadata
  "user_agent": "Mozilla/5.0...",
  "ip_address": "123.45.67.89",
  "rate_locked_at": ISODate("2025-12-01T10:25:00Z"),
  "rate_lock_expires": ISODate("2025-12-01T10:35:00Z")
}
```

### Update `subscriptions` Collection

Add crypto payment support:
```javascript
{
  // Existing fields...
  "payment_history": [
    {
      "payment_id": "pay_123",
      "payment_method": "USDT-BSC", // NEW
      "tx_hash": "0x1234...", // NEW for crypto
      "amount_paid": 279000, // VND equivalent
      "amount_usdt": 10.73, // NEW
      "exchange_rate": 26000, // NEW
      "timestamp": ISODate("2025-12-01T10:30:00Z")
    }
  ]
}
```

---

## Security Considerations

### Transaction Security

**1. Double-Spending Prevention:**
```python
# Check if transaction hash already used
existing_payment = crypto_payments.find_one({"tx_hash": tx_hash})
if existing_payment:
    raise HTTPException(409, "Transaction already processed")

# Store with unique index on tx_hash
crypto_payments.create_index("tx_hash", unique=True)
```

**2. Wallet Whitelist (Optional):**
```python
# For high-value transactions, require wallet verification
if amount_usdt > 1000:
    verified_wallets = user_doc.get('verified_wallets', [])
    if user_wallet.lower() not in [w.lower() for w in verified_wallets]:
        raise HTTPException(403, "Wallet not verified for large transactions")
```

**3. Rate Limiting:**
```python
# Prevent spam verification requests
@limiter.limit("10/minute")
async def verify_crypto_payment(...):
    pass
```

**4. Transaction Confirmation Requirements:**
```python
# Require minimum confirmations based on amount
if amount_usdt < 100:
    min_confirmations = 3
elif amount_usdt < 1000:
    min_confirmations = 6
else:
    min_confirmations = 12  # Higher security for large amounts

current_block = w3.eth.block_number
confirmations = current_block - receipt.blockNumber

if confirmations < min_confirmations:
    return {
        "status": "pending",
        "confirmations": confirmations,
        "required": min_confirmations,
        "message": f"Waiting for {min_confirmations - confirmations} more confirmations"
    }
```

### Smart Contract Risks

**Hot Wallet Management:**
- Use dedicated wallet for receiving payments
- Automatically sweep large balances to cold storage
- Set up multi-sig for withdrawals > $10,000

**Recommended Wallet Strategy:**
```
Hot Wallet (receives payments) →
  Auto-sweep daily to Warm Wallet (multi-sig 2/3) →
    Manual transfer weekly to Cold Storage (hardware wallet)
```

---

## Frontend Implementation Guide

### Step-by-Step Integration

**1. Install Dependencies:**
```bash
npm install wagmi ethers viem @rainbow-me/rainbowkit
```

**2. Configure Wagmi Provider:**
```typescript
// app/providers.tsx
import { WagmiConfig, createConfig, configureChains } from 'wagmi';
import { bsc } from 'wagmi/chains';
import { publicProvider } from 'wagmi/providers/public';
import { MetaMaskConnector } from 'wagmi/connectors/metaMask';

const { chains, publicClient } = configureChains(
  [bsc],
  [publicProvider()]
);

const config = createConfig({
  autoConnect: true,
  connectors: [
    new MetaMaskConnector({ chains }),
  ],
  publicClient,
});

export function Providers({ children }) {
  return (
    <WagmiConfig config={config}>
      {children}
    </WagmiConfig>
  );
}
```

**3. Wallet Connect Button:**
```typescript
// components/WalletConnectButton.tsx
import { useAccount, useConnect, useDisconnect } from 'wagmi';

export function WalletConnectButton() {
  const { address, isConnected } = useAccount();
  const { connect, connectors } = useConnect();
  const { disconnect } = useDisconnect();

  if (isConnected) {
    return (
      <div>
        <p>Connected: {address?.slice(0, 6)}...{address?.slice(-4)}</p>
        <button onClick={() => disconnect()}>Disconnect</button>
      </div>
    );
  }

  return (
    <div>
      {connectors.map((connector) => (
        <button
          key={connector.id}
          onClick={() => connect({ connector })}
        >
          Connect {connector.name}
        </button>
      ))}
    </div>
  );
}
```

**4. USDT Payment Component:**
```typescript
// components/USDTPayment.tsx
import { ethers } from 'ethers';
import { useAccount, useProvider, useSigner } from 'wagmi';

const USDT_CONTRACT_BSC = '0x55d398326f99059fF775485246999027B3197955';
const WORDAI_WALLET = process.env.NEXT_PUBLIC_WORDAI_WALLET;

// USDT ABI (simplified - only transfer function)
const USDT_ABI = [
  'function transfer(address to, uint256 amount) returns (bool)',
  'function balanceOf(address owner) view returns (uint256)',
  'function decimals() view returns (uint8)'
];

export function USDTPayment({
  plan,
  duration,
  usdtAmount,
  onSuccess,
  onError
}) {
  const { address } = useAccount();
  const { data: signer } = useSigner();
  const [loading, setLoading] = useState(false);

  const handlePayment = async () => {
    if (!address || !signer) {
      onError('Please connect your wallet first');
      return;
    }

    setLoading(true);

    try {
      // Check USDT balance
      const usdtContract = new ethers.Contract(
        USDT_CONTRACT_BSC,
        USDT_ABI,
        signer
      );

      const balance = await usdtContract.balanceOf(address);
      const decimals = await usdtContract.decimals();
      const balanceFormatted = ethers.utils.formatUnits(balance, decimals);

      if (parseFloat(balanceFormatted) < usdtAmount) {
        throw new Error(`Insufficient USDT balance. You have ${balanceFormatted} USDT`);
      }

      // Send USDT transaction
      const amountInWei = ethers.utils.parseUnits(
        usdtAmount.toFixed(2),
        decimals
      );

      const tx = await usdtContract.transfer(WORDAI_WALLET, amountInWei);

      console.log('Transaction sent:', tx.hash);

      // Wait for confirmation
      const receipt = await tx.wait(3); // Wait for 3 confirmations

      console.log('Transaction confirmed:', receipt.transactionHash);

      // Verify payment on backend
      const response = await fetch('/api/v1/crypto-payments/verify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${firebaseToken}`
        },
        body: JSON.stringify({
          tx_hash: receipt.transactionHash,
          user_wallet: address,
          plan: plan,
          duration: duration,
          amount_usdt: usdtAmount
        })
      });

      const result = await response.json();

      if (result.success) {
        onSuccess(result);
      } else {
        throw new Error(result.message || 'Payment verification failed');
      }

    } catch (error) {
      console.error('Payment error:', error);
      onError(error.message || 'Payment failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="usdt-payment">
      <h3>Pay with USDT (BSC)</h3>
      <div className="payment-details">
        <p>Amount: <strong>{usdtAmount.toFixed(2)} USDT</strong></p>
        <p>Network: <strong>Binance Smart Chain</strong></p>
        <p>Your Wallet: <strong>{address?.slice(0, 10)}...</strong></p>
      </div>

      <button
        onClick={handlePayment}
        disabled={loading || !address}
        className="btn-pay-usdt"
      >
        {loading ? 'Processing...' : 'Pay with USDT'}
      </button>

      <div className="payment-info">
        <p>⚠️ Make sure you're on Binance Smart Chain network</p>
        <p>⏱️ Transaction will be confirmed in ~1-3 minutes</p>
        <p>💰 Estimated gas fee: ~$0.50</p>
      </div>
    </div>
  );
}
```

**5. Exchange Rate Display:**
```typescript
// hooks/useUSDTRate.ts
import { useState, useEffect } from 'react';

export function useUSDTRate() {
  const [rate, setRate] = useState(26000); // Default rate
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchRate() {
      try {
        const response = await fetch('/api/v1/crypto-payments/exchange-rate');
        const data = await response.json();
        setRate(data.usdt_vnd_rate);
      } catch (error) {
        console.error('Failed to fetch exchange rate:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchRate();
    // Refresh every 5 minutes
    const interval = setInterval(fetchRate, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  return { rate, loading };
}

// Usage in component
export function PricingCard({ plan, duration }) {
  const { rate, loading } = useUSDTRate();
  const vndPrice = PLAN_CONFIGS[plan][`price_${duration}_months`];
  const usdtPrice = (vndPrice / rate).toFixed(2);

  return (
    <div>
      <h3>{plan}</h3>
      <p className="price-vnd">₫{vndPrice.toLocaleString()}</p>
      {!loading && (
        <p className="price-usdt">or {usdtPrice} USDT</p>
      )}
      <button>Subscribe</button>
    </div>
  );
}
```

---

## Backend API Specifications

### New Endpoints

#### 1. Get Exchange Rate

**Endpoint:** `GET /api/v1/crypto-payments/exchange-rate`

**Response:**
```json
{
  "usdt_vnd_rate": 26000,
  "last_updated": "2025-12-01T10:30:00Z",
  "sources": ["binance", "remitano"],
  "cache_ttl": 300
}
```

#### 2. Verify Crypto Payment

**Endpoint:** `POST /api/v1/crypto-payments/verify`

**Request:**
```json
{
  "tx_hash": "0x1234567890abcdef...",
  "user_wallet": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
  "plan": "premium",
  "duration": 3,
  "amount_usdt": 10.73
}
```

**Response (Success):**
```json
{
  "success": true,
  "payment_id": "pay_crypto_123",
  "subscription_id": "sub_xyz789",
  "status": "confirmed",
  "confirmations": 15,
  "amount_usdt": 10.73,
  "amount_vnd": 279000,
  "exchange_rate": 26000,
  "points_granted": 300,
  "expires_at": "2026-03-01T10:30:00Z",
  "message": "Payment confirmed and subscription activated"
}
```

**Response (Pending):**
```json
{
  "success": false,
  "status": "pending",
  "confirmations": 1,
  "required_confirmations": 3,
  "message": "Waiting for 2 more confirmations"
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "amount_mismatch",
  "message": "Amount received (9.5 USDT) does not match expected (10.73 USDT)",
  "details": {
    "expected_usdt": 10.73,
    "received_usdt": 9.5,
    "tolerance": "±2%"
  }
}
```

#### 3. Calculate USDT Price

**Endpoint:** `POST /api/v1/crypto-payments/calculate-price`

**Request:**
```json
{
  "order_type": "subscription",
  "plan": "premium",
  "duration": 3
}
```

**Response:**
```json
{
  "vnd_price": 279000,
  "usdt_price": 10.73,
  "exchange_rate": 26000,
  "rate_locked_until": "2025-12-01T10:40:00Z",
  "rate_lock_token": "lock_abc123xyz",
  "gas_estimate_usdt": 0.5,
  "total_usdt": 11.23
}
```

#### 4. Get Payment Status

**Endpoint:** `GET /api/v1/crypto-payments/{payment_id}/status`

**Response:**
```json
{
  "payment_id": "pay_crypto_123",
  "status": "confirmed",
  "tx_hash": "0x1234567890abcdef...",
  "confirmations": 15,
  "blockchain_url": "https://bscscan.com/tx/0x1234567890abcdef...",
  "created_at": "2025-12-01T10:25:00Z",
  "confirmed_at": "2025-12-01T10:30:00Z"
}
```

---

## Implementation Phases

### Phase 1: Infrastructure Setup (Week 1-2)

**Tasks:**
- [ ] Create WordAI crypto wallet (MetaMask/hardware wallet)
- [ ] Set up BSC node connection (use public RPC or Infura)
- [ ] Install Python web3.py library
- [ ] Create MongoDB collection for crypto_payments
- [ ] Implement exchange rate fetching service
- [ ] Set up rate caching (Redis recommended)

**Deliverables:**
- Working BSC connection
- Exchange rate API endpoint
- Database schema created

### Phase 2: Backend API Development (Week 2-3)

**Tasks:**
- [ ] Implement `/crypto-payments/verify` endpoint
- [ ] Add transaction hash validation
- [ ] Build amount verification logic
- [ ] Create subscription activation integration
- [ ] Add double-spending prevention
- [ ] Implement rate locking mechanism
- [ ] Set up monitoring and logging

**Deliverables:**
- Complete verification API
- Unit tests for verification logic
- Integration with existing subscription service

### Phase 3: Frontend Integration (Week 3-4)

**Tasks:**
- [ ] Install wagmi and ethers.js
- [ ] Create wallet connection component
- [ ] Build USDT payment flow
- [ ] Add network detection/switching
- [ ] Implement transaction status tracking
- [ ] Create payment confirmation UI
- [ ] Add error handling and user feedback

**Deliverables:**
- Working wallet connection
- Complete payment flow UI
- Transaction tracking interface

### Phase 4: Testing & Security Audit (Week 4-5)

**Tasks:**
- [ ] Test on BSC testnet (get testnet USDT)
- [ ] Test all payment scenarios (success, fail, timeout)
- [ ] Verify rate locking mechanism
- [ ] Test concurrent payment handling
- [ ] Security audit of smart contract interactions
- [ ] Load testing with multiple users
- [ ] Edge case testing (network issues, insufficient gas, etc.)

**Deliverables:**
- Comprehensive test suite
- Security audit report
- Bug fixes

### Phase 5: Mainnet Deployment & Monitoring (Week 5-6)

**Tasks:**
- [ ] Deploy to production
- [ ] Start with small transaction limits ($100 max)
- [ ] Monitor first 100 transactions closely
- [ ] Set up alerts for failed verifications
- [ ] Create admin dashboard for crypto payments
- [ ] Gradually increase transaction limits
- [ ] Marketing announcement

**Deliverables:**
- Live crypto payment system
- Monitoring dashboard
- User documentation

---

## Cost Analysis

### Transaction Costs

**BSC Network Fees:**
- USDT Transfer: ~$0.10-0.50 per transaction
- Who pays: User (deducted from their wallet balance)
- WordAI cost: $0 (receiver doesn't pay gas)

**Development Costs:**
```
Backend Development: 40 hours × $50/hour = $2,000
Frontend Development: 40 hours × $50/hour = $2,000
Testing & Security: 20 hours × $75/hour = $1,500
Total: $5,500
```

**Operational Costs:**
```
BSC Node (Public RPC): $0/month (free)
Exchange Rate API: $0-50/month (depending on volume)
Monitoring Tools: $0-100/month
Total: $0-150/month
```

**Savings vs Traditional Gateways:**
```
SePay Fee: 2.5% per transaction
USDT Fee: ~$0.50 flat fee

Example: ₫1,000,000 transaction
- SePay: ₫25,000 fee (2.5%)
- USDT: ₫13,000 fee ($0.50 ÷ 26,000 VND)
- Savings: ₫12,000 (48% cheaper)

At 100 transactions/month:
- SePay fees: ₫2,500,000
- USDT fees: ₫1,300,000
- Monthly savings: ₫1,200,000 ($46)
```

---

## Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Exchange rate volatility | High | Medium | Rate locking (10 min), ±2% tolerance |
| Smart contract bug | Low | High | Use audited contracts, test thoroughly |
| Network congestion | Medium | Low | Increase gas price, extend timeout |
| Transaction reversal | Very Low | High | Wait for sufficient confirmations |
| User error (wrong network) | Medium | Medium | Network detection, clear warnings |

### Business Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Low adoption | Medium | Medium | Marketing, education, incentives |
| Regulatory issues | Low | High | Consult legal, stay updated on crypto laws |
| Customer support burden | Medium | Medium | Comprehensive docs, FAQs, video tutorials |
| Wallet hacks | Low | High | Recommend hardware wallets, security guides |

### Compliance Considerations

**Vietnam Crypto Regulations (2025):**
- ✅ Cryptocurrency payments are legal for digital services
- ⚠️ Must report transactions > $10,000 to authorities
- ⚠️ VAT may apply (consult tax advisor)
- ⚠️ AML/KYC required for large transactions

**Recommended Compliance Measures:**
- For payments > $1,000 USDT: Require email verification
- For payments > $5,000 USDT: Require KYC (ID upload)
- Maintain transaction records for 5 years
- Monthly reporting to finance team

---

## User Experience Considerations

### Education & Onboarding

**Challenges:**
- Many users unfamiliar with crypto wallets
- Fear of losing funds
- Confusion about gas fees
- Network selection complexity

**Solutions:**

1. **Wallet Setup Guide:**
   - Video tutorial: "How to set up MetaMask in 3 minutes"
   - Step-by-step screenshots
   - Vietnamese language support
   - WhatsApp/Zalo support channel

2. **Pre-Payment Checklist:**
   ```
   ✅ Wallet connected
   ✅ Binance Smart Chain network selected
   ✅ Sufficient USDT balance (10.73 + 0.5 gas fee)
   ✅ Price locked for 10 minutes
   ✅ Ready to proceed
   ```

3. **Clear Fee Breakdown:**
   ```
   Plan: Premium 3 months
   Price: 10.73 USDT (₫279,000)
   Network: BSC
   Gas Fee: ~0.5 USDT (~₫13,000)
   ─────────────────────────────
   Total: ~11.23 USDT (₫292,000)

   Note: Actual gas fee determined by network
   ```

4. **Transaction Tracking:**
   ```
   Status: Pending ⏳
   Confirmations: 2/3
   Estimated time: 1-2 minutes

   [View on BscScan] [Cancel] [Need Help?]
   ```

### Error Messages & Recovery

**Common Errors:**

1. **Insufficient Balance:**
   ```
   ❌ Insufficient USDT Balance

   You need: 11.23 USDT
   You have: 8.50 USDT
   Missing: 2.73 USDT

   [Buy USDT on Binance] [Contact Support]
   ```

2. **Wrong Network:**
   ```
   ⚠️ Wrong Network Detected

   Current: Ethereum Mainnet
   Required: Binance Smart Chain

   [Switch to BSC] [Learn More]
   ```

3. **Transaction Timeout:**
   ```
   ⏱️ Rate Lock Expired

   The price lock has expired. Exchange rates may have changed.
   Please restart the payment process.

   [Try Again] [Pay with VND Instead]
   ```

---

## Alternative Payment Options

### Other Cryptocurrencies

**Future Expansion Possibilities:**

| Currency | Network | Pros | Cons |
|----------|---------|------|------|
| USDC | BSC/ETH | Stable, trusted | Same as USDT |
| DAI | ETH | Decentralized | Higher gas fees on ETH |
| BUSD | BSC | Binance-backed | Being phased out |
| BTC | Bitcoin | Most trusted | Slow, expensive fees |
| ETH | Ethereum | Most used | Very high gas fees |

**Recommendation:** Start with USDT on BSC only. Add USDC later if demand exists.

### Payment Aggregators

**Consider These Services (Less Decentralized):**

1. **Coinbase Commerce:**
   - Accepts BTC, ETH, USDC, DAI
   - Hosted checkout page
   - Fee: 1% per transaction
   - Easy integration
   - ⚠️ Not fully decentralized

2. **NOWPayments:**
   - 150+ cryptocurrencies
   - API integration
   - Fee: 0.5% per transaction
   - Auto-conversion to fiat
   - ⚠️ Higher fees than direct

3. **CoinPayments:**
   - 100+ cryptocurrencies
   - Shopping cart plugins
   - Fee: 0.5% + $0.50
   - Established since 2013

**Trade-off:** Aggregators are easier to implement but charge fees and introduce third-party dependency. Direct USDT integration gives more control and lower costs.

---

## Marketing Strategy

### Launch Campaign

**Target Audience:**
- Tech-savvy users (20-35 years old)
- Crypto enthusiasts
- International users (avoiding VND banking)
- Privacy-conscious professionals

**Promotional Offers:**

1. **Early Adopter Bonus:**
   ```
   🎉 First 100 USDT Payments
   Get +50 bonus points with any subscription!

   Premium: 300 → 350 points
   Pro: 500 → 550 points
   VIP: 1000 → 1050 points
   ```

2. **Crypto Payment Discount:**
   ```
   💰 5% Discount for USDT Payments

   Premium 3mo: 10.73 → 10.19 USDT
   Pro 12mo: 65.35 → 62.08 USDT

   Valid for first month only
   ```

3. **Referral Program:**
   ```
   Share your referral link, earn 10% of referred payment

   Friend pays 100 USDT → You get 10 USDT worth of points
   (Points credited at current exchange rate)
   ```

### Communication Channels

**Announcement Strategy:**
1. Email blast to existing users
2. Banner on homepage
3. Blog post: "WordAI Now Accepts Crypto Payments"
4. Social media posts (Facebook, X/Twitter, LinkedIn)
5. Vietnamese crypto forums (Bitcoin Vietnam, Coin68)
6. Press release to crypto news sites

**Messaging:**
```
🚀 Big News: Pay with Crypto on WordAI!

We're excited to announce USDT payment support!

✅ Lower fees (save up to 50%)
✅ Instant settlement
✅ Global accessibility
✅ Enhanced privacy

Start using crypto to supercharge your AI workflow today!

[Learn More] [Try It Now]
```

---

## Monitoring & Analytics

### Key Metrics to Track

**Transaction Metrics:**
- Total USDT transactions per day/week/month
- Average transaction value (USDT)
- Conversion rate (crypto vs VND payments)
- Failed transaction rate
- Average confirmation time

**User Metrics:**
- Unique wallet addresses
- Repeat crypto payers
- Geographic distribution (based on wallet activity)
- User wallet types (MetaMask, Trust Wallet, etc.)

**Financial Metrics:**
- Total USDT revenue
- VND equivalent revenue
- Gas cost savings vs traditional gateways
- Exchange rate variance impact

### Monitoring Dashboard

**Real-Time Alerts:**
```python
# Alert triggers
- Failed verification rate > 5%
- Exchange rate deviation > 3%
- Unconfirmed transactions > 10 minutes old
- Wallet balance < $100 (needs sweep)
- Suspicious activity (same wallet, different users)
```

**Daily Reports:**
```
WordAI Crypto Payment Report - 2025-12-01
─────────────────────────────────────────

Transactions: 47
Success Rate: 95.7%
Total Volume: 523.41 USDT (₫13,608,660)
Average Tx: 11.13 USDT

Top Plans:
1. Premium 3mo: 23 purchases
2. Pro 12mo: 12 purchases
3. Premium 12mo: 8 purchases

Issues:
- 2 transactions pending > 30 min
- 1 amount mismatch (user refunded)

[View Full Report]
```

---

## Conclusion & Recommendations

### Why Implement USDT Payments?

**Strategic Benefits:**
1. **Lower Costs:** Save ~50% on transaction fees vs traditional gateways
2. **Global Reach:** Enable international users without VND banking
3. **Competitive Edge:** Few Vietnamese SaaS platforms accept crypto
4. **Future-Proof:** Position WordAI as innovative and tech-forward
5. **User Preference:** Growing crypto adoption in Vietnam (15% of internet users own crypto)

**Financial Projections:**
```
Scenario: 10% of paid subscriptions use USDT (conservative)

Current: 1000 paid subs/month × ₫500,000 avg = ₫500M/month
USDT: 100 crypto subs/month × ₫500,000 = ₫50M/month

Fee savings:
Traditional (2.5%): ₫1.25M in fees
USDT (flat $0.50): ₫0.5M in fees
Monthly savings: ₫0.75M ($29)
Annual savings: ₫9M ($346)

+ Attract international users (incremental revenue)
+ Marketing value (tech-forward brand image)
```

### Recommended Approach

**Start Small, Scale Gradually:**

1. **Pilot Phase (Month 1-2):**
   - Launch with Premium plan only
   - Limit to $100 transactions
   - Monitor closely, gather feedback
   - Invite 50 early adopters

2. **Expansion Phase (Month 3-4):**
   - Add Pro and VIP plans
   - Enable points purchases
   - Increase limit to $1,000
   - Public launch and marketing

3. **Optimization Phase (Month 5-6):**
   - Add USDC support (if demand exists)
   - Optimize user experience based on feedback
   - Build admin management tools
   - Scale to handle 1000+ transactions/month

### Next Steps

**Immediate Actions:**
1. ✅ **Approve Budget:** $5,500 development + $150/month operational
2. ✅ **Assign Team:** 1 backend dev + 1 frontend dev + 1 QA
3. ✅ **Legal Review:** Consult lawyer on crypto payment compliance
4. ✅ **Set Up Wallet:** Create multi-sig wallet for security
5. ✅ **Start Phase 1:** Begin infrastructure setup this week

**Timeline:**
- Week 1-2: Infrastructure & backend API
- Week 3-4: Frontend integration
- Week 5-6: Testing & security audit
- Week 7: Pilot launch (50 users)
- Week 8+: Public launch & scaling

---

**Document Version:** 1.0
**Last Updated:** December 1, 2025
**Author:** WordAI Development Team
**Status:** Proposal - Awaiting Approval

**Approval Required From:**
- [ ] CTO (Technical feasibility)
- [ ] CFO (Budget approval)
- [ ] Legal (Compliance review)
- [ ] CEO (Final decision)

---

## Appendix

### A. USDT Contract Addresses

**Binance Smart Chain (BEP-20):**
- Contract: `0x55d398326f99059fF775485246999027B3197955`
- Explorer: https://bscscan.com/token/0x55d398326f99059fF775485246999027B3197955

**Ethereum (ERC-20):**
- Contract: `0xdAC17F958D2ee523a2206206994597C13D831ec7`
- Explorer: https://etherscan.io/token/0xdac17f958d2ee523a2206206994597c13d831ec7

**Tron (TRC-20):**
- Contract: `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`
- Explorer: https://tronscan.org/#/token20/TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t

### B. Exchange Rate APIs

**Binance API:**
```
GET https://api.binance.com/api/v3/ticker/price?symbol=USDTVND

Response:
{
  "symbol": "USDTVND",
  "price": "26000.00000000"
}
```

**Remitano API:**
```
GET https://api.remitano.com/api/v1/ticker?currency=VND

Response:
{
  "usdt": {
    "buy": "26100",
    "sell": "25900",
    "mid": "26000"
  }
}
```

### C. Sample Test Cases

**Test Case 1: Successful Payment**
```
Given: User selects Premium 3 months
When: User pays 10.73 USDT on BSC
Then: Transaction confirmed in 3 blocks
And: Subscription activated
And: 300 points granted
And: Email confirmation sent
```

**Test Case 2: Insufficient Amount**
```
Given: Expected payment is 10.73 USDT
When: User sends 9.00 USDT
Then: Verification fails
And: Error message: "Amount mismatch"
And: Manual review required
```

**Test Case 3: Wrong Network**
```
Given: User should pay on BSC
When: User sends USDT on Ethereum
Then: Transaction not detected on BSC
And: Error message: "Transaction not found"
And: Support contact provided
```

**Test Case 4: Double Spending**
```
Given: Transaction hash already processed
When: User submits same tx_hash again
Then: Verification fails immediately
And: Error: "Transaction already processed"
```

### D. Support Resources

**User Guides:**
- How to set up MetaMask: `/docs/metamask-setup`
- How to buy USDT: `/docs/buy-usdt`
- How to add BSC network: `/docs/add-bsc-network`
- Troubleshooting guide: `/docs/crypto-troubleshooting`

**FAQ:**

**Q: Which wallets are supported?**
A: MetaMask, Trust Wallet, WalletConnect-compatible wallets (Coinbase Wallet, Rainbow, etc.)

**Q: What if I send on the wrong network?**
A: Contact support immediately. Recovery may be possible but depends on the network.

**Q: How long does confirmation take?**
A: Usually 1-3 minutes on BSC. Ethereum may take 3-15 minutes.

**Q: What if the exchange rate changes during payment?**
A: Rate is locked for 10 minutes when you initiate payment. Complete within this window.

**Q: Are gas fees refundable?**
A: No, gas fees go to blockchain validators, not WordAI. They are non-refundable.

**Q: Can I get a refund?**
A: Yes, but only before subscription activation. Contact support within 1 hour of payment.

---

**End of Document**
