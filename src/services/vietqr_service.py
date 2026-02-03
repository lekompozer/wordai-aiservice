"""
VietQR Service - Generate VietQR codes for bank transfers
"""

import httpx
from typing import Dict, Any, Optional
from src.utils.logger import setup_logger

logger = setup_logger()


class VietQRService:
    """Service for generating VietQR codes"""

    BASE_URL = "https://api.vietqr.io/v2"

    # Bank BIN codes reference (major Vietnamese banks)
    BANK_BINS = {
        "Vietcombank": "970436",
        "Techcombank": "970407",
        "BIDV": "970418",
        "VietinBank": "970415",
        "ACB": "970416",
        "MBBank": "970422",
        "Sacombank": "970403",
        "VPBank": "970432",
        "TPBank": "970423",
        "MSB": "970426",
        "HDBank": "970437",
        "VIB": "970441",
        "SHB": "970443",
        "Eximbank": "970431",
        "OCB": "970448",
        "SeABank": "970440",
        "NamABank": "970428",
        "PGBank": "970430",
        "VietCapitalBank": "970454",
        "SCB": "970429",
        "BacABank": "970409",
        "ABBank": "970425",
        "NCB": "970419",
        "OceanBank": "970414",
        "GPBank": "970408",
        "BaoVietBank": "970438",
        "KienLongBank": "970452",
        "CBBank": "970444",
        "LienVietPostBank": "970449",
    }

    def __init__(self):
        """Initialize VietQR service"""
        self.timeout = 30.0  # 30 seconds timeout

    async def generate_qr_code(
        self,
        bank_bin: str,
        account_number: str,
        amount: int,
        description: str,
        account_name: str,
        template: str = "compact",
    ) -> Dict[str, Any]:
        """
        Generate QR code for bank transfer

        Args:
            bank_bin: Bank BIN code (e.g., "970436" for Vietcombank)
            account_number: Bank account number
            amount: Transfer amount in VND
            description: Transfer description/content
            account_name: Account holder name
            template: QR template ("compact", "compact2", "qr_only")

        Returns:
            {
                "code": "00",
                "desc": "Success",
                "data": {
                    "qrCode": "00020101021238...",  # QR code content
                    "qrDataURL": "data:image/png;base64,..."  # Base64 image
                }
            }

        Raises:
            httpx.HTTPError: If API request fails
        """
        try:
            url = f"{self.BASE_URL}/generate"

            payload = {
                "accountNo": account_number,
                "accountName": account_name,
                "acqId": bank_bin,
                "amount": amount,
                "addInfo": description,
                "format": "text",
                "template": template,
            }

            logger.info(
                f"🔄 Generating VietQR code for {account_number} - Amount: {amount:,} VND"
            )

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                result = response.json()

                if result.get("code") == "00":
                    logger.info(f"✅ VietQR code generated successfully")
                    return result
                else:
                    error_msg = result.get("desc", "Unknown error")
                    logger.error(f"❌ VietQR API error: {error_msg}")
                    raise Exception(f"VietQR API error: {error_msg}")

        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP error generating VietQR: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error generating VietQR: {e}")
            raise

    def get_bank_bin(self, bank_name: str) -> Optional[str]:
        """
        Get bank BIN code from bank name

        Args:
            bank_name: Bank name (e.g., "Vietcombank", "Techcombank")

        Returns:
            Bank BIN code or None if not found
        """
        return self.BANK_BINS.get(bank_name)

    async def generate_qr_from_bank_name(
        self,
        bank_name: str,
        account_number: str,
        amount: int,
        description: str,
        account_name: str,
        template: str = "compact",
    ) -> Dict[str, Any]:
        """
        Generate QR code using bank name instead of BIN

        Args:
            bank_name: Bank name (e.g., "Vietcombank")
            account_number: Bank account number
            amount: Transfer amount in VND
            description: Transfer description/content
            account_name: Account holder name
            template: QR template

        Returns:
            QR code data

        Raises:
            ValueError: If bank name not found
        """
        bank_bin = self.get_bank_bin(bank_name)
        if not bank_bin:
            raise ValueError(
                f"Bank '{bank_name}' not found. Available banks: {list(self.BANK_BINS.keys())}"
            )

        return await self.generate_qr_code(
            bank_bin=bank_bin,
            account_number=account_number,
            amount=amount,
            description=description,
            account_name=account_name,
            template=template,
        )


# Global VietQR service instance
vietqr_service = VietQRService()
