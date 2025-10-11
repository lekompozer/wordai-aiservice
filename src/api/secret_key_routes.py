"""
Secret Documents API Routes - Key Management
E2EE key registration and retrieval
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging
import asyncio

from src.middleware.auth import verify_firebase_token
from src.services.key_manager import KeyManager
from src.database.db_manager import DBManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/secret-documents/auth", tags=["E2EE Key Management"])

# Global instance
_key_manager = None


def get_key_manager() -> KeyManager:
    """Get or create KeyManager instance"""
    global _key_manager
    if _key_manager is None:
        db_manager = DBManager()
        _key_manager = KeyManager(db_manager.db)
        logger.info("✅ KeyManager initialized")
    return _key_manager


# ============ PYDANTIC MODELS ============


class RegisterKeysRequest(BaseModel):
    publicKey: str  # Base64 encoded RSA public key (PEM format)
    encryptedPrivateKey: str  # Private key encrypted with master key
    keySalt: str  # Salt for PBKDF2
    keyIterations: int = 100000  # PBKDF2 iterations


class UpdatePasswordRequest(BaseModel):
    newEncryptedPrivateKey: str  # Re-encrypted with new master key
    newSalt: str


class StoreRecoveryKeyRequest(BaseModel):
    encryptedPrivateKeyWithRecovery: str  # Private key encrypted with recovery key


class KeyStatusResponse(BaseModel):
    hasKeys: bool
    hasRecoveryKey: bool
    keysRegisteredAt: Optional[str] = None
    lastKeyUpdate: Optional[str] = None


class PublicKeyResponse(BaseModel):
    user_id: str
    publicKey: str


class EncryptedPrivateKeyResponse(BaseModel):
    encryptedPrivateKey: str
    salt: str
    iterations: int


# ============ KEY REGISTRATION ============


@router.post("/register-keys")
async def register_keys(
    request: RegisterKeysRequest,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Register user's RSA key pair for E2EE

    Client flow:
    1. User sets master password
    2. Generate master key: PBKDF2(password, salt, 100k iterations)
    3. Generate RSA key pair (2048-bit)
    4. Encrypt private key with master key (AES-256-GCM)
    5. Send public key + encrypted private key + salt to server

    Returns:
        success: bool
        message: str
    """
    user_id = user_data.get("uid")
    key_manager = get_key_manager()

    try:
        logger.info(f"🔐 Registering E2EE keys for user {user_id}")

        # Check if keys already exist
        if await asyncio.to_thread(key_manager.has_keys_registered, user_id):
            raise HTTPException(
                status_code=400,
                detail="Keys already registered. Use update-password to change.",
            )

        # Register keys
        success = await asyncio.to_thread(
            key_manager.register_user_keys,
            user_id=user_id,
            public_key=request.publicKey,
            encrypted_private_key=request.encryptedPrivateKey,
            key_salt=request.keySalt,
            key_iterations=request.keyIterations,
        )

        if success:
            logger.info(f"✅ Successfully registered keys for user {user_id}")
            return {
                "success": True,
                "message": "E2EE keys registered successfully",
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to register keys")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error registering keys: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ GET PUBLIC KEY ============


@router.get("/public-key/{target_user_id}", response_model=PublicKeyResponse)
async def get_public_key(
    target_user_id: str,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get another user's public key for sharing

    Used when sharing secret documents - need recipient's public key
    to re-encrypt file key

    Args:
        target_user_id: Firebase UID of the user whose public key is needed

    Returns:
        PublicKeyResponse with user_id and publicKey
    """
    current_user_id = user_data.get("uid")
    key_manager = get_key_manager()

    try:
        logger.info(
            f"🔍 User {current_user_id} requesting public key for {target_user_id}"
        )

        # Get public key
        public_key = await asyncio.to_thread(key_manager.get_public_key, target_user_id)

        if not public_key:
            raise HTTPException(
                status_code=404,
                detail=f"User {target_user_id} has not set up E2EE keys",
            )

        return PublicKeyResponse(
            user_id=target_user_id,
            publicKey=public_key,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting public key: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ GET ENCRYPTED PRIVATE KEY ============


@router.get("/encrypted-private-key", response_model=EncryptedPrivateKeyResponse)
async def get_encrypted_private_key(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get own encrypted private key for decryption

    Client flow:
    1. User enters master password
    2. Derive master key from password + salt
    3. Decrypt private key
    4. Use private key to decrypt file keys

    Returns:
        EncryptedPrivateKeyResponse with encrypted key, salt, iterations
    """
    user_id = user_data.get("uid")
    key_manager = get_key_manager()

    try:
        logger.info(f"🔍 User {user_id} requesting encrypted private key")

        # Get encrypted private key
        key_data = await asyncio.to_thread(
            key_manager.get_encrypted_private_key, user_id
        )

        if not key_data:
            raise HTTPException(
                status_code=404,
                detail="E2EE keys not found. Please register keys first.",
            )

        return EncryptedPrivateKeyResponse(
            encryptedPrivateKey=key_data["encrypted_private_key"],
            salt=key_data["salt"],
            iterations=key_data["iterations"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting encrypted private key: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ UPDATE MASTER PASSWORD ============


@router.post("/update-password")
async def update_password(
    request: UpdatePasswordRequest,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Update master password (re-encrypt private key)

    Client flow:
    1. User enters old password → decrypt private key
    2. User enters new password → generate new master key
    3. Re-encrypt private key with new master key
    4. Send new encrypted private key + new salt to server

    Returns:
        success: bool
        message: str
    """
    user_id = user_data.get("uid")
    key_manager = get_key_manager()

    try:
        logger.info(f"🔐 Updating master password for user {user_id}")

        # Update keys
        success = await asyncio.to_thread(
            key_manager.update_master_password,
            user_id=user_id,
            new_encrypted_private_key=request.newEncryptedPrivateKey,
            new_salt=request.newSalt,
        )

        if success:
            logger.info(f"✅ Successfully updated master password for user {user_id}")
            return {
                "success": True,
                "message": "Master password updated successfully",
            }
        else:
            raise HTTPException(
                status_code=500, detail="Failed to update master password"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating master password: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ RECOVERY KEY ============


@router.post("/setup-recovery")
async def setup_recovery_key(
    request: StoreRecoveryKeyRequest,
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Store recovery key backup

    Client flow:
    1. Generate 24-word recovery key
    2. Derive encryption key from recovery key
    3. Encrypt private key with recovery key
    4. Send encrypted backup to server
    5. Display recovery key to user (one-time only)

    Returns:
        success: bool
        message: str
    """
    user_id = user_data.get("uid")
    key_manager = get_key_manager()

    try:
        logger.info(f"🔐 Setting up recovery key for user {user_id}")

        # Store recovery backup
        success = await asyncio.to_thread(
            key_manager.store_recovery_key_backup,
            user_id=user_id,
            encrypted_private_key_with_recovery=request.encryptedPrivateKeyWithRecovery,
        )

        if success:
            logger.info(f"✅ Recovery key set up for user {user_id}")
            return {
                "success": True,
                "message": "Recovery key backup stored successfully",
            }
        else:
            raise HTTPException(
                status_code=500, detail="Failed to store recovery key backup"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error setting up recovery key: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recovery-status")
async def get_recovery_status(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Check if user has recovery key set up

    Returns:
        hasRecoveryKey: bool
    """
    user_id = user_data.get("uid")
    key_manager = get_key_manager()

    try:
        has_recovery = await asyncio.to_thread(key_manager.has_recovery_key, user_id)

        return {
            "hasRecoveryKey": has_recovery,
        }

    except Exception as e:
        logger.error(f"❌ Error checking recovery status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ KEY STATUS ============


@router.get("/key-status", response_model=KeyStatusResponse)
async def get_key_status(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Get user's E2EE key status

    Returns:
        hasKeys: bool
        hasRecoveryKey: bool
        keysRegisteredAt: ISO datetime
        lastKeyUpdate: ISO datetime
    """
    user_id = user_data.get("uid")
    key_manager = get_key_manager()

    try:
        # Check if has keys
        has_keys = await asyncio.to_thread(key_manager.has_keys_registered, user_id)

        if not has_keys:
            return KeyStatusResponse(
                hasKeys=False,
                hasRecoveryKey=False,
            )

        # Get user data
        user_data_doc = key_manager.users.find_one(
            {"user_id": user_id},
            {
                "hasRecoveryKey": 1,
                "keysRegisteredAt": 1,
                "lastKeyUpdate": 1,
            },
        )

        return KeyStatusResponse(
            hasKeys=True,
            hasRecoveryKey=user_data_doc.get("hasRecoveryKey", False),
            keysRegisteredAt=(
                user_data_doc["keysRegisteredAt"].isoformat()
                if user_data_doc.get("keysRegisteredAt")
                else None
            ),
            lastKeyUpdate=(
                user_data_doc["lastKeyUpdate"].isoformat()
                if user_data_doc.get("lastKeyUpdate")
                else None
            ),
        )

    except Exception as e:
        logger.error(f"❌ Error getting key status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ INITIALIZE INDEXES ============


@router.post("/initialize-indexes")
async def initialize_indexes(
    user_data: Dict[str, Any] = Depends(verify_firebase_token),
):
    """
    Initialize database indexes for E2EE keys
    Admin only - called once on first deployment
    """
    key_manager = get_key_manager()

    try:
        await asyncio.to_thread(key_manager.create_indexes)
        return {
            "success": True,
            "message": "E2EE key indexes created successfully",
        }

    except Exception as e:
        logger.error(f"❌ Error creating indexes: {e}")
        raise HTTPException(status_code=500, detail=str(e))
