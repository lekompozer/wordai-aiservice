"""
Payment Information Models for Earnings Withdrawal System
"""

from pydantic import BaseModel, Field
from typing import Optional


class PaymentInfoRequest(BaseModel):
    """Request model for setting up payment information for earnings withdrawal"""

    account_holder_name: str = Field(
        ..., description="Tên chủ tài khoản", min_length=2, max_length=100
    )
    account_number: str = Field(
        ..., description="Số tài khoản ngân hàng", min_length=6, max_length=30
    )
    bank_name: str = Field(
        ..., description="Tên ngân hàng", min_length=2, max_length=100
    )
    bank_branch: Optional[str] = Field(
        None, description="Chi nhánh ngân hàng (optional)", max_length=100
    )


class WithdrawEarningsRequest(BaseModel):
    """Request model for withdrawing earnings to cash"""

    amount: int = Field(
        ..., description="Amount to withdraw in points (1 point = 1 VND)", ge=100000
    )
