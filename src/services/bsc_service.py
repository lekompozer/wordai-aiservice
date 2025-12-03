"""
BSC (Binance Smart Chain) Blockchain Integration Service

Service for interacting with BSC network to verify USDT BEP20 transactions:
- Check transaction status and confirmations
- Verify USDT transfer amount and recipient
- Get wallet balances
- Transaction receipt validation
"""

import os
from typing import Optional, Dict, Any, Tuple
from decimal import Decimal
from web3 import Web3
from web3.exceptions import TransactionNotFound, BlockNotFound
from eth_typing import HexStr

from src.utils.logger import setup_logger

logger = setup_logger()


class BSCService:
    """Service for BSC blockchain operations"""

    # BSC Network Configuration
    BSC_MAINNET_RPC = "https://bsc-dataseed1.binance.org:443"
    BSC_TESTNET_RPC = "https://data-seed-prebsc-1-s1.binance.org:8545"

    # USDT BEP20 Contract Address (BSC Mainnet)
    USDT_CONTRACT_ADDRESS = "0x55d398326f99059fF775485246999027B3197955"

    # USDT has 18 decimals on BSC
    USDT_DECIMALS = 18

    def __init__(self, use_testnet: bool = False):
        """
        Initialize BSC service

        Args:
            use_testnet: Use BSC testnet instead of mainnet
        """
        self.use_testnet = use_testnet

        # Select RPC endpoint
        rpc_url = self.BSC_TESTNET_RPC if use_testnet else self.BSC_MAINNET_RPC

        # Custom RPC from environment (optional)
        custom_rpc = os.getenv("BSC_RPC_URL")
        if custom_rpc:
            rpc_url = custom_rpc
            logger.info(f"🔗 Using custom BSC RPC: {custom_rpc}")

        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        # Verify connection
        if not self.w3.is_connected():
            logger.error(f"❌ Failed to connect to BSC network: {rpc_url}")
            raise ConnectionError(f"Cannot connect to BSC network: {rpc_url}")

        network_name = "Testnet" if use_testnet else "Mainnet"
        logger.info(f"✅ Connected to BSC {network_name}: {rpc_url}")
        logger.info(f"📦 Latest block: {self.w3.eth.block_number}")

        # USDT BEP20 Contract ABI (minimal - only Transfer event)
        self.usdt_abi = [
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "name": "from", "type": "address"},
                    {"indexed": True, "name": "to", "type": "address"},
                    {"indexed": False, "name": "value", "type": "uint256"},
                ],
                "name": "Transfer",
                "type": "event",
            },
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function",
            },
        ]

        # Create contract instance
        self.usdt_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.USDT_CONTRACT_ADDRESS),
            abi=self.usdt_abi,
        )

    # =========================================================================
    # TRANSACTION VERIFICATION
    # =========================================================================

    def get_transaction(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get transaction details

        Args:
            tx_hash: Transaction hash (0x...)

        Returns:
            Transaction dict or None if not found
        """
        try:
            tx = self.w3.eth.get_transaction(tx_hash)
            return dict(tx)
        except TransactionNotFound:
            logger.warning(f"⚠️ Transaction not found: {tx_hash}")
            return None
        except Exception as e:
            logger.error(f"❌ Error getting transaction {tx_hash}: {e}")
            return None

    def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get transaction receipt (includes status and logs)

        Args:
            tx_hash: Transaction hash

        Returns:
            Receipt dict or None if not found/not mined yet
        """
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            return dict(receipt)
        except TransactionNotFound:
            logger.warning(
                f"⚠️ Transaction receipt not found (not mined yet?): {tx_hash}"
            )
            return None
        except Exception as e:
            logger.error(f"❌ Error getting receipt {tx_hash}: {e}")
            return None

    def get_transaction_confirmations(self, tx_hash: str) -> int:
        """
        Get number of confirmations for a transaction

        Args:
            tx_hash: Transaction hash

        Returns:
            Number of confirmations (0 if not mined, -1 if error)
        """
        try:
            receipt = self.get_transaction_receipt(tx_hash)

            if not receipt:
                return 0  # Not mined yet

            tx_block = receipt.get("blockNumber")
            if not tx_block:
                return 0

            current_block = self.w3.eth.block_number
            confirmations = current_block - tx_block + 1

            return confirmations
        except Exception as e:
            logger.error(f"❌ Error getting confirmations for {tx_hash}: {e}")
            return -1

    def is_transaction_successful(self, tx_hash: str) -> Tuple[bool, Optional[str]]:
        """
        Check if transaction was successful

        Args:
            tx_hash: Transaction hash

        Returns:
            (success: bool, error_message: Optional[str])
        """
        try:
            receipt = self.get_transaction_receipt(tx_hash)

            if not receipt:
                return False, "Transaction not mined yet"

            # Status: 1 = success, 0 = failed
            status = receipt.get("status")

            if status == 1:
                return True, None
            elif status == 0:
                return False, "Transaction failed (reverted)"
            else:
                return False, f"Unknown status: {status}"

        except Exception as e:
            logger.error(f"❌ Error checking transaction success: {e}")
            return False, f"Error: {str(e)}"

    # =========================================================================
    # USDT TRANSFER VERIFICATION
    # =========================================================================

    def verify_usdt_transfer(
        self,
        tx_hash: str,
        expected_recipient: str,
        expected_amount_usdt: float,
        tolerance_percentage: float = 1.0,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Verify USDT BEP20 transfer transaction

        Checks:
        1. Transaction exists and is successful
        2. Transfer is to correct recipient address
        3. Amount matches expected value (with tolerance)

        Args:
            tx_hash: Transaction hash
            expected_recipient: Expected recipient address (WordAI wallet)
            expected_amount_usdt: Expected USDT amount
            tolerance_percentage: Acceptable difference as percentage (default 1.0%)

        Returns:
            (is_valid: bool, message: str, details: dict)
        """
        try:
            logger.info(f"🔍 Verifying USDT transfer: {tx_hash}")

            # Step 1: Get transaction receipt
            receipt = self.get_transaction_receipt(tx_hash)

            if not receipt:
                return False, "Transaction not found or not mined yet", {}

            # Step 2: Check transaction success
            if receipt.get("status") != 1:
                return False, "Transaction failed or reverted", {"receipt": receipt}

            # Step 3: Get transaction details
            tx = self.get_transaction(tx_hash)

            if not tx:
                return False, "Cannot get transaction details", {}

            # Step 4: Verify it's a USDT contract interaction
            tx_to = tx.get("to", "").lower()
            usdt_address = self.USDT_CONTRACT_ADDRESS.lower()

            if tx_to != usdt_address:
                return (
                    False,
                    f"Transaction is not to USDT contract (to: {tx_to})",
                    {"tx": tx},
                )

            # Step 5: Parse Transfer event from logs
            transfer_found = False
            actual_recipient = None
            actual_amount = None

            for log in receipt.get("logs", []):
                # Check if it's a Transfer event
                # Transfer event signature: Transfer(address,address,uint256)
                # Topic[0] = event signature hash
                if len(log.get("topics", [])) >= 3:
                    # Transfer has 3 topics: signature, from, to
                    event_signature = log["topics"][0].hex()
                    transfer_signature = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

                    if event_signature == transfer_signature:
                        # Extract recipient (topic[2])
                        recipient_topic = log["topics"][2].hex()
                        actual_recipient = (
                            "0x" + recipient_topic[-40:]
                        )  # Last 20 bytes (40 hex chars)

                        # Extract amount from data
                        amount_hex = log["data"].hex()
                        amount_wei = int(amount_hex, 16)
                        actual_amount = amount_wei / (10**self.USDT_DECIMALS)

                        transfer_found = True
                        break

            if not transfer_found:
                return (
                    False,
                    "No USDT Transfer event found in logs",
                    {"receipt": receipt},
                )

            # Step 6: Verify recipient address
            expected_recipient_lower = expected_recipient.lower()
            actual_recipient_lower = actual_recipient.lower()

            if actual_recipient_lower != expected_recipient_lower:
                return (
                    False,
                    f"Recipient mismatch. Expected: {expected_recipient}, Got: {actual_recipient}",
                    {
                        "expected_recipient": expected_recipient,
                        "actual_recipient": actual_recipient,
                        "actual_amount": actual_amount,
                    },
                )

            # Step 7: Verify amount (with percentage-based tolerance)
            # Calculate tolerance as percentage of expected amount
            tolerance = expected_amount_usdt * (tolerance_percentage / 100.0)
            amount_diff = abs(actual_amount - expected_amount_usdt)

            if amount_diff > tolerance:
                return (
                    False,
                    f"Amount mismatch. Expected: {expected_amount_usdt} USDT, Got: {actual_amount} USDT (tolerance: {tolerance_percentage}%)",
                    {
                        "expected_amount": expected_amount_usdt,
                        "actual_amount": actual_amount,
                        "difference": amount_diff,
                        "tolerance": tolerance,
                        "tolerance_percentage": tolerance_percentage,
                    },
                )

            # Step 8: All checks passed
            confirmations = self.get_transaction_confirmations(tx_hash)

            logger.info(
                f"✅ USDT transfer verified: {actual_amount} USDT to {actual_recipient}"
            )

            return (
                True,
                "Transfer verified successfully",
                {
                    "transaction_hash": tx_hash,
                    "from_address": tx.get("from"),
                    "to_address": actual_recipient,
                    "amount_usdt": actual_amount,
                    "block_number": receipt.get("blockNumber"),
                    "confirmations": confirmations,
                    "gas_used": receipt.get("gasUsed"),
                    "status": "success",
                },
            )

        except Exception as e:
            logger.error(f"❌ Error verifying USDT transfer: {e}")
            return False, f"Error: {str(e)}", {}

    # =========================================================================
    # WALLET OPERATIONS
    # =========================================================================

    def get_usdt_balance(self, address: str) -> Optional[float]:
        """
        Get USDT balance of an address

        Args:
            address: Wallet address

        Returns:
            USDT balance or None if error
        """
        try:
            checksum_address = Web3.to_checksum_address(address)
            balance_wei = self.usdt_contract.functions.balanceOf(
                checksum_address
            ).call()
            balance_usdt = balance_wei / (10**self.USDT_DECIMALS)

            logger.info(f"💰 USDT balance for {address}: {balance_usdt}")
            return balance_usdt

        except Exception as e:
            logger.error(f"❌ Error getting USDT balance for {address}: {e}")
            return None

    def get_bnb_balance(self, address: str) -> Optional[float]:
        """
        Get BNB balance (for gas fees)

        Args:
            address: Wallet address

        Returns:
            BNB balance or None if error
        """
        try:
            checksum_address = Web3.to_checksum_address(address)
            balance_wei = self.w3.eth.get_balance(checksum_address)
            balance_bnb = self.w3.from_wei(balance_wei, "ether")

            logger.info(f"💰 BNB balance for {address}: {balance_bnb}")
            return float(balance_bnb)

        except Exception as e:
            logger.error(f"❌ Error getting BNB balance for {address}: {e}")
            return None

    # =========================================================================
    # BLOCKCHAIN INFO
    # =========================================================================

    def get_current_block_number(self) -> int:
        """Get current block number"""
        try:
            return self.w3.eth.block_number
        except Exception as e:
            logger.error(f"❌ Error getting block number: {e}")
            return 0

    def get_block(self, block_number: int) -> Optional[Dict[str, Any]]:
        """
        Get block details

        Args:
            block_number: Block number

        Returns:
            Block dict or None
        """
        try:
            block = self.w3.eth.get_block(block_number)
            return dict(block)
        except BlockNotFound:
            logger.warning(f"⚠️ Block not found: {block_number}")
            return None
        except Exception as e:
            logger.error(f"❌ Error getting block {block_number}: {e}")
            return None

    def get_gas_price(self) -> Optional[int]:
        """
        Get current gas price in wei

        Returns:
            Gas price in wei or None
        """
        try:
            gas_price = self.w3.eth.gas_price
            gas_price_gwei = self.w3.from_wei(gas_price, "gwei")
            logger.info(f"⛽ Gas price: {gas_price_gwei} Gwei")
            return gas_price
        except Exception as e:
            logger.error(f"❌ Error getting gas price: {e}")
            return None

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def is_valid_address(self, address: str) -> bool:
        """Check if address is valid Ethereum/BSC address"""
        try:
            return Web3.is_address(address)
        except:
            return False

    def to_checksum_address(self, address: str) -> Optional[str]:
        """Convert address to checksum format"""
        try:
            return Web3.to_checksum_address(address)
        except:
            return None

    def is_connected(self) -> bool:
        """Check if connected to BSC network"""
        return self.w3.is_connected()

    def get_network_info(self) -> Dict[str, Any]:
        """Get network information"""
        return {
            "connected": self.is_connected(),
            "network": "Testnet" if self.use_testnet else "Mainnet",
            "current_block": self.get_current_block_number(),
            "gas_price_wei": self.get_gas_price(),
            "usdt_contract": self.USDT_CONTRACT_ADDRESS,
        }

    def find_usdt_transfer(
        self,
        from_address: str,
        to_address: str,
        expected_amount_usdt: float,
        tolerance_percentage: float = 1.0,
        max_blocks_to_scan: int = 1000,
    ) -> Optional[Dict[str, Any]]:
        """
        Scan blockchain to find USDT transfer from sender to recipient with expected amount
        
        This method scans recent blocks to find a matching USDT transfer transaction.
        Use this when user claims they sent USDT but didn't provide transaction hash.
        
        Args:
            from_address: Sender wallet address (user's wallet)
            to_address: Recipient address (WordAI wallet)
            expected_amount_usdt: Expected USDT amount
            tolerance_percentage: Acceptable difference as percentage (default 1%)
            max_blocks_to_scan: Maximum number of recent blocks to scan (default 1000)
            
        Returns:
            Dict with transaction details if found, None otherwise
            {
                "tx_hash": "0x...",
                "from_address": "0x...",
                "to_address": "0x...",
                "amount_usdt": 1.92,
                "block_number": 12345678,
                "timestamp": 1234567890,
                "confirmations": 5
            }
        """
        try:
            logger.info(
                f"🔍 Scanning blockchain for USDT transfer: {from_address[:8]}...→{to_address[:8]}... amount: {expected_amount_usdt} USDT"
            )

            # Normalize addresses
            from_addr = from_address.lower()
            to_addr = to_address.lower()
            
            # Calculate tolerance
            tolerance = expected_amount_usdt * (tolerance_percentage / 100.0)
            min_amount = expected_amount_usdt - tolerance
            max_amount = expected_amount_usdt + tolerance

            # Get current block number
            current_block = self.w3.eth.block_number
            start_block = max(0, current_block - max_blocks_to_scan)

            logger.info(
                f"📊 Scanning blocks {start_block} to {current_block} ({max_blocks_to_scan} blocks)"
            )

            # Scan blocks in reverse (newest first)
            for block_num in range(current_block, start_block, -1):
                try:
                    block = self.w3.eth.get_block(block_num, full_transactions=False)
                    
                    # Check each transaction in block
                    for tx_hash in block.transactions:
                        tx_hash_hex = tx_hash.hex()
                        
                        # Get transaction receipt to check logs
                        try:
                            receipt = self.w3.eth.get_transaction_receipt(tx_hash_hex)
                            
                            # Skip if transaction failed
                            if receipt.get("status") != 1:
                                continue
                            
                            # Check if it's to USDT contract
                            if receipt.get("to", "").lower() != self.USDT_CONTRACT_ADDRESS.lower():
                                continue
                            
                            # Parse Transfer events
                            for log in receipt.get("logs", []):
                                # Check if it's Transfer event
                                if len(log.get("topics", [])) >= 3:
                                    event_sig = log["topics"][0].hex()
                                    transfer_sig = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
                                    
                                    if event_sig == transfer_sig:
                                        # Extract from address (topic[1])
                                        from_topic = log["topics"][1].hex()
                                        tx_from = ("0x" + from_topic[-40:]).lower()
                                        
                                        # Extract to address (topic[2])
                                        to_topic = log["topics"][2].hex()
                                        tx_to = ("0x" + to_topic[-40:]).lower()
                                        
                                        # Extract amount
                                        amount_hex = log["data"].hex()
                                        amount_wei = int(amount_hex, 16)
                                        amount_usdt = amount_wei / (10**self.USDT_DECIMALS)
                                        
                                        # Check if matches
                                        if (
                                            tx_from == from_addr
                                            and tx_to == to_addr
                                            and min_amount <= amount_usdt <= max_amount
                                        ):
                                            confirmations = current_block - block_num
                                            
                                            logger.info(
                                                f"✅ Found matching USDT transfer! "
                                                f"Tx: {tx_hash_hex[:10]}... "
                                                f"Amount: {amount_usdt} USDT "
                                                f"Block: {block_num} "
                                                f"Confirmations: {confirmations}"
                                            )
                                            
                                            return {
                                                "tx_hash": tx_hash_hex,
                                                "from_address": from_address,
                                                "to_address": to_address,
                                                "amount_usdt": amount_usdt,
                                                "block_number": block_num,
                                                "timestamp": block.timestamp,
                                                "confirmations": confirmations,
                                            }
                        
                        except Exception as tx_error:
                            # Skip transactions that can't be retrieved
                            continue
                
                except BlockNotFound:
                    continue
                except Exception as block_error:
                    logger.error(f"❌ Error scanning block {block_num}: {block_error}")
                    continue

            logger.warning(
                f"⚠️ No matching USDT transfer found in last {max_blocks_to_scan} blocks"
            )
            return None

        except Exception as e:
            logger.error(f"❌ Error finding USDT transfer: {e}")
            return None


# Global service instance
_bsc_service: Optional[BSCService] = None


def get_bsc_service(use_testnet: bool = False) -> BSCService:
    """
    Get or create global BSC service instance

    Args:
        use_testnet: Use testnet instead of mainnet

    Returns:
        BSCService instance
    """
    global _bsc_service

    # Check if environment requests testnet
    env_testnet = os.getenv("BSC_USE_TESTNET", "false").lower() == "true"
    use_testnet = use_testnet or env_testnet

    if _bsc_service is None:
        _bsc_service = BSCService(use_testnet=use_testnet)

    return _bsc_service
