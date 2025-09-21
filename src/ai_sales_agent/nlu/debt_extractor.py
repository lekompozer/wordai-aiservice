"""
Debt Information Extractor for Steps 5.1 and 5.2
Trích xuất thông tin dư nợ
"""

import re
from typing import Dict, Any, Optional
from .extractor import BaseExtractor

class DebtExtractor(BaseExtractor):
    """Extractor for debt information (Steps 5.1, 5.2)"""
    
    def __init__(self):
        super().__init__()
        
        # Has debt patterns (Yes/No)
        self.has_debt_patterns = {
            True: [  # Has debt
                r'có\s+(?:nợ|vay|dư\s+nợ)', r'đang\s+vay', r'đang\s+nợ',
                r'có\s+khoản\s+vay', r'vay\s+ở\s+ngân\s+hàng',
                r'có\s+tín\s+dụng', r'có\s+loan', r'yes|có'
            ],
            False: [  # No debt
                r'không\s+(?:có\s+)?(?:nợ|vay|dư\s+nợ)', r'chưa\s+(?:từng\s+)?vay',
                r'không\s+vay\s+ở\s+đâu', r'sạch\s+nợ', r'không\s+có\s+khoản\s+vay',
                r'no|không', r'chưa\s+có\s+nợ'
            ]
        }
        
        # Debt amount patterns (Vietnamese currency)
        self.debt_amount_patterns = [
            (r'(?:dư\s+nợ|tổng\s+nợ|nợ\s+hiện\s+tại)[:\s]*(\d+(?:[.,]\d+)?)\s*tỷ', 1000000000),
            (r'(?:dư\s+nợ|tổng\s+nợ|nợ\s+hiện\s+tại)[:\s]*(\d+(?:[.,]\d+)?)\s*triệu', 1000000),
            (r'nợ\s+(\d+(?:[.,]\d+)?)\s*tỷ', 1000000000),
            (r'nợ\s+(\d+(?:[.,]\d+)?)\s*triệu', 1000000),
            (r'còn\s+nợ\s+(\d+(?:[.,]\d+)?)\s*tỷ', 1000000000),
            (r'còn\s+nợ\s+(\d+(?:[.,]\d+)?)\s*triệu', 1000000)
        ]
        
        # Monthly payment patterns
        self.monthly_payment_patterns = [
            (r'(?:trả|đóng)\s+(?:hàng\s+tháng|mỗi\s+tháng)[:\s]*(\d+(?:[.,]\d+)?)\s*triệu', 1000000),
            (r'(?:trả|đóng)\s+(?:hàng\s+tháng|mỗi\s+tháng)[:\s]*(\d+(?:[.,]\d+)?)\s*nghìn', 1000),
            (r'(\d+(?:[.,]\d+)?)\s*triệu\s*(?:/|\s+)tháng', 1000000),
            (r'(\d+(?:[.,]\d+)?)\s*nghìn\s*(?:/|\s+)tháng', 1000),
            (r'monthly\s+payment[:\s]*(\d+(?:[.,]\d+)?)\s*triệu', 1000000)
        ]
        
        # CIC credit score group patterns
        self.cic_patterns = {
            "Nhóm 1": [r'nhóm\s+1|group\s+1|cic\s+1', r'tín\s+dụng\s+tốt'],
            "Nhóm 2": [r'nhóm\s+2|group\s+2|cic\s+2', r'tín\s+dụng\s+khá'],
            "Nhóm 3": [r'nhóm\s+3|group\s+3|cic\s+3', r'tín\s+dụng\s+trung\s+bình'],
            "Nhóm 4": [r'nhóm\s+4|group\s+4|cic\s+4', r'tín\s+dụng\s+yếu'],
            "Nhóm 5": [r'nhóm\s+5|group\s+5|cic\s+5', r'tín\s+dụng\s+xấu']
        }
    
    def extract(self, user_message: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract debt information from user message"""
        normalized_text = self.normalize_text(user_message)
        original_text = user_message.strip()
        extracted_data = {}
        
        # Extract has existing debt (boolean)
        has_debt = self._extract_has_debt(normalized_text)
        if has_debt is not None:
            extracted_data["hasExistingDebt"] = has_debt
        
        # Only extract debt details if has debt = true
        if has_debt:
            # Extract total debt amount
            total_debt = self._extract_total_debt(normalized_text)
            if total_debt:
                extracted_data["totalDebtAmount"] = total_debt
            
            # Extract monthly payment
            monthly_payment = self._extract_monthly_payment(normalized_text)
            if monthly_payment:
                extracted_data["monthlyDebtPayment"] = monthly_payment
            
            # Extract CIC credit score group (optional)
            cic_group = self._extract_cic_group(normalized_text)
            if cic_group:
                extracted_data["cicCreditScoreGroup"] = cic_group
            
            # Extract credit history (optional)
            credit_history = self._extract_credit_history(original_text)
            if credit_history:
                extracted_data["creditHistory"] = credit_history
            
            # Extract existing loans info (optional)
            existing_loans = self._extract_existing_loans(original_text)
            if existing_loans:
                extracted_data["existingLoans"] = existing_loans
        
        return extracted_data
    
    def _extract_has_debt(self, text: str) -> Optional[bool]:
        """Extract whether user has existing debt"""
        
        # Check for "no debt" patterns first (more specific)
        for pattern in self.has_debt_patterns[False]:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        
        # Check for "has debt" patterns
        for pattern in self.has_debt_patterns[True]:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return None
    
    def _extract_total_debt(self, text: str) -> Optional[int]:
        """Extract total debt amount in VND"""
        
        for pattern, multiplier in self.debt_amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value_str = match.group(1).replace(',', '.')
                    value = float(value_str)
                    return int(value * multiplier)
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _extract_monthly_payment(self, text: str) -> Optional[int]:
        """Extract monthly debt payment in VND"""
        
        for pattern, multiplier in self.monthly_payment_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value_str = match.group(1).replace(',', '.')
                    value = float(value_str)
                    return int(value * multiplier)
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _extract_cic_group(self, text: str) -> Optional[str]:
        """Extract CIC credit score group"""
        
        for group, patterns in self.cic_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return group
        
        return None
    
    def _extract_credit_history(self, text: str) -> Optional[str]:
        """Extract credit history description"""
        
        history_patterns = [
            r'(?:lịch\s+sử\s+tín\s+dụng|credit\s+history)[:\s]*([^,.]+)',
            r'(?:trước\s+đây|đã\s+từng)[:\s]*([^,.]+)',
            r'(?:tín\s+dụng\s+của\s+tôi)[:\s]*([^,.]+)'
        ]
        
        for pattern in history_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                history = match.group(1).strip()
                if len(history) > 5:
                    return history
        
        # Common credit history indicators
        good_indicators = [
            r'tín\s+dụng\s+tốt', r'không\s+có\s+nợ\s+xấu', r'trả\s+nợ\s+đúng\s+hạn',
            r'lịch\s+sử\s+tốt', r'clean\s+credit'
        ]
        
        bad_indicators = [
            r'tín\s+dụng\s+xấu', r'có\s+nợ\s+xấu', r'quá\s+hạn',
            r'blacklist', r'nợ\s+nhóm\s+[45]'
        ]
        
        for pattern in good_indicators:
            if re.search(pattern, text, re.IGNORECASE):
                return "Tín dụng tốt"
        
        for pattern in bad_indicators:
            if re.search(pattern, text, re.IGNORECASE):
                return "Có vấn đề tín dụng"
        
        return None
    
    def _extract_existing_loans(self, text: str) -> Optional[str]:
        """Extract existing loans information"""
        
        loan_patterns = [
            r'(?:các\s+khoản\s+vay|existing\s+loans?)[:\s]*([^,.]+)',
            r'(?:đang\s+vay\s+ở)[:\s]*([^,.]+)',
            r'(?:vay\s+tại)[:\s]*([^,.]+)'
        ]
        
        for pattern in loan_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                loans_info = match.group(1).strip()
                if len(loans_info) > 3:
                    return loans_info
        
        # Specific loan types
        loan_types = [
            r'vay\s+thế\s+chấp', r'vay\s+tín\s+chấp', r'vay\s+mua\s+nhà',
            r'vay\s+mua\s+xe', r'thẻ\s+tín\s+dụng', r'credit\s+card'
        ]
        
        found_loans = []
        for loan_type in loan_types:
            if re.search(loan_type, text, re.IGNORECASE):
                found_loans.append(loan_type.replace(r'\s+', ' '))
        
        if found_loans:
            return ", ".join(found_loans)
        
        return None
