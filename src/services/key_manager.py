"""
Key Manager Service for E2EE
Manages user RSA key pairs for End-to-End Encryption
"""

from typing import Optional, Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class KeyManager:
    """Manage E2EE keys for users"""

    def __init__(self, db):
        """
        Initialize KeyManager

        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.users = db.users

    def register_user_keys(
        self,
        user_id: str,
        public_key: str,
        encrypted_private_key: str,
        key_salt: str,
        key_iterations: int = 100000,
    ) -> bool:
        """
        Register user's RSA key pair (public + encrypted private)

        Args:
            user_id: Firebase UID
            public_key: RSA public key (PEM format, Base64)
            encrypted_private_key: Private key encrypted with master key (Base64)
            key_salt: Salt for PBKDF2 key derivation (Base64)
            key_iterations: PBKDF2 iteration count

        Returns:
            bool: Success status
        """
        try:
            now = datetime.utcnow()

            logger.info(f"🔐 Registering keys for user_id: {user_id}")
            
            # Check if keys already exist
            existing = self.users.find_one({"firebase_uid": user_id})
            
            logger.info(f"🔍 Existing user data: {existing}")

            if existing and existing.get("publicKey"):
                logger.warning(
                    f"⚠️ User {user_id} already has keys registered. Use update_keys() to change."
                )
                return False

            # Store keys in users collection
            logger.info(f"💾 Saving keys to database for user {user_id}")
            result = self.users.update_one(
                {"firebase_uid": user_id},
                {
                    "$set": {
                        "publicKey": public_key,
                        "encryptedPrivateKey": encrypted_private_key,
                        "keySalt": key_salt,
                        "keyIterations": key_iterations,
                        "keysRegisteredAt": now,
                        "lastKeyUpdate": now,
                        "hasRecoveryKey": False,
                    }
                },
                upsert=True,
            )
            
            logger.info(f"💾 Update result: matched={result.matched_count}, modified={result.modified_count}, upserted_id={result.upserted_id}")

            if result.modified_count > 0 or result.upserted_id:
                logger.info(f"✅ Registered E2EE keys for user {user_id}")
                return True
            else:
                logger.error(f"❌ Failed to register keys for user {user_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Error registering keys: {e}")
            return False

    def get_public_key(self, user_id: str) -> Optional[str]:
        """
        Get user's public key for encryption

        Args:
            user_id: Firebase UID

        Returns:
            Public key (PEM Base64) or None if not found
        """
        try:
            logger.info(f"🔍 Querying public key for user_id: {user_id}")
            user = self.users.find_one({"firebase_uid": user_id}, {"publicKey": 1, "firebase_uid": 1})
            
            logger.info(f"🔍 Query result: {user}")

            if user and user.get("publicKey"):
                logger.info(f"✅ Found public key for user {user_id}")
                return user["publicKey"]
            else:
                if user:
                    logger.warning(f"⚠️ User {user_id} exists but has no publicKey field")
                else:
                    logger.warning(f"⚠️ User {user_id} not found in database")
                return None

        except Exception as e:
            logger.error(f"❌ Error getting public key: {e}")
            return None

    def get_encrypted_private_key(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user's encrypted private key + salt for decryption

        Args:
            user_id: Firebase UID

        Returns:
            Dict with encrypted_private_key, salt, iterations
            None if not found
        """
        try:
            user = self.users.find_one(
                {"firebase_uid": user_id},
                {
                    "encryptedPrivateKey": 1,
                    "keySalt": 1,
                    "keyIterations": 1,
                },
            )

            if user and user.get("encryptedPrivateKey"):
                return {
                    "encrypted_private_key": user["encryptedPrivateKey"],
                    "salt": user["keySalt"],
                    "iterations": user.get("keyIterations", 100000),
                }
            else:
                logger.warning(f"⚠️ Encrypted private key not found for user {user_id}")
                return None

        except Exception as e:
            logger.error(f"❌ Error getting encrypted private key: {e}")
            return None

    def update_master_password(
        self, user_id: str, new_encrypted_private_key: str, new_salt: str
    ) -> bool:
        """
        Re-encrypt private key with new master password

        Args:
            user_id: Firebase UID
            new_encrypted_private_key: Private key encrypted with new master key
            new_salt: New salt for PBKDF2

        Returns:
            bool: Success status
        """
        try:
            result = self.users.update_one(
                {"firebase_uid": user_id},
                {
                    "$set": {
                        "encryptedPrivateKey": new_encrypted_private_key,
                        "keySalt": new_salt,
                        "lastKeyUpdate": datetime.utcnow(),
                    }
                },
            )

            if result.modified_count > 0:
                logger.info(f"✅ Updated master password for user {user_id}")
                return True
            else:
                logger.error(f"❌ Failed to update master password for user {user_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Error updating master password: {e}")
            return False

    def store_recovery_key_backup(
        self, user_id: str, encrypted_private_key_with_recovery: str
    ) -> bool:
        """
        Store recovery key encrypted version of private key

        Args:
            user_id: Firebase UID
            encrypted_private_key_with_recovery: Private key encrypted with recovery key

        Returns:
            bool: Success status
        """
        try:
            result = self.users.update_one(
                {"firebase_uid": user_id},
                {
                    "$set": {
                        "encryptedPrivateKeyWithRecovery": encrypted_private_key_with_recovery,
                        "recoveryKeySetAt": datetime.utcnow(),
                    }
                },
            )

            if result.modified_count > 0:
                logger.info(f"✅ Stored recovery key backup for user {user_id}")
                return True
            else:
                logger.error(
                    f"❌ Failed to store recovery key backup for user {user_id}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Error storing recovery key backup: {e}")
            return False

    def get_recovery_encrypted_private_key(
        self, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get private key encrypted with recovery key

        Args:
            user_id: Firebase UID

        Returns:
            Dict with encrypted_private_key_with_recovery
            None if not found or recovery not set up
        """
        try:
            user = self.users.find_one(
                {"firebase_uid": user_id},
                {
                    "encryptedPrivateKeyWithRecovery": 1,
                },
            )

            if user and user.get("encryptedPrivateKeyWithRecovery"):
                return {
                    "encrypted_private_key_with_recovery": user[
                        "encryptedPrivateKeyWithRecovery"
                    ]
                }
            else:
                logger.warning(f"⚠️ Recovery key not set up for user {user_id}")
                return None

        except Exception as e:
            logger.error(f"❌ Error getting recovery encrypted private key: {e}")
            return None

    def has_keys_registered(self, user_id: str) -> bool:
        """
        Check if user has E2EE keys set up

        Args:
            user_id: Firebase UID

        Returns:
            bool: True if keys exist
        """
        try:
            user = self.users.find_one({"firebase_uid": user_id}, {"publicKey": 1})
            return user is not None and user.get("publicKey") is not None

        except Exception as e:
            logger.error(f"❌ Error checking if keys registered: {e}")
            return False

    def has_recovery_key(self, user_id: str) -> bool:
        """
        Check if user has recovery key set up

        Args:
            user_id: Firebase UID

        Returns:
            bool: True if recovery key exists
        """
        try:
            user = self.users.find_one(
                {"firebase_uid": user_id}, {"encryptedPrivateKeyWithRecovery": 1}
            )
            return user is not None and bool(
                user.get("encryptedPrivateKeyWithRecovery")
            )

        except Exception as e:
            logger.error(f"❌ Error checking recovery key status: {e}")
            return False

    def create_indexes(self):
        """Create indexes for E2EE key management"""
        try:
            # Index on publicKey for fast lookups when sharing
            self.users.create_index("publicKey")
            logger.info("✅ Created index on users.publicKey")

        except Exception as e:
            logger.error(f"❌ Error creating indexes: {e}")
