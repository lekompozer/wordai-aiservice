"""
NLU Extractor for Loan Information (Steps 1.1 and 1.2)
"""
import re
from typing import Dict, Any, Optional
from .extractor import BaseExtractor

class LoanInfoExtractor(BaseExtractor):
    """Extract loan information from user messages"""
    
    def __init__(self):
        super().__init__()
        self._init_mappings()
    
    def _init_mappings(self):
        """Initialize mapping dictionaries"""
        
        # Loan amount patterns with multipliers
        self.amount_patterns = [
            # Billions: "5 tỷ", "2.5 tỷ", "3,5 tỷ"
            (r'(\d+(?:[.,]\d+)?)\s*(?:tỷ|tỉ|ty|ti)', 1_000_000_000),
            # Millions: "500 triệu", "50 tr"
            (r'(\d+(?:[.,]\d+)?)\s*(?:triệu|trieu|tr)', 1_000_000),
            # Thousands: "500 nghìn", "500k"
            (r'(\d+(?:[.,]\d+)?)\s*(?:nghìn|nghin|k)', 1_000),
            # Formatted numbers: "500.000.000", "500,000,000"
            (r'(\d{1,3}(?:[.,]\d{3}){2,})', 1),
            # Simple large numbers: "500000000"
            (r'(\d{8,})', 1)
        ]
        
        # Loan term mappings
        self.term_mappings = {
            # Years in Vietnamese
            "01 năm": ["1 năm", "một năm", "1 nam", "mot nam", "12 tháng", "12 thang"],
            "02 năm": ["2 năm", "hai năm", "2 nam", "hai nam", "24 tháng", "24 thang"],
            "03 năm": ["3 năm", "ba năm", "3 nam", "ba nam", "36 tháng", "36 thang"],
            "04 năm": ["4 năm", "bốn năm", "4 nam", "bon nam", "48 tháng", "48 thang"],
            "05 năm": ["5 năm", "năm năm", "5 nam", "nam nam", "60 tháng", "60 thang"],
            "10 năm": ["10 năm", "mười năm", "10 nam", "muoi nam", "120 tháng", "120 thang"],
            "15 năm": ["15 năm", "mười lăm năm", "15 nam", "muoi lam nam", "180 tháng"],
            "20 năm": ["20 năm", "hai mươi năm", "20 nam", "hai muoi nam", "240 tháng"],
        }
        
        # Loan type keywords
        self.loan_type_keywords = {
            "Thế chấp": [
                "thế chấp", "the chap", "có tài sản", "co tai san",
                "có nhà", "co nha", "có đất", "co dat", "có bảo đảm", "co bao dam",
                "bất động sản", "bat dong san", "bds", "tài sản đảm bảo"
            ],
            "Tín chấp": [
                "tín chấp", "tin chap", "không thế chấp", "khong the chap",
                "không tài sản", "khong tai san", "không cần tài sản", "khong can tai san",
                "không bảo đảm", "khong bao dam"
            ]
        }
        
        # Loan purpose mappings
        self.purpose_mappings = {
            "Vay tiêu dùng cá nhân": [
                "tiêu dùng", "tieu dung", "cá nhân", "ca nhan", 
                "chi tiêu", "chi tieu", "sinh hoạt", "sinh hoat", "cần tiền", "can tien"
            ],
            "Vay mua bất động sản": [
                "mua nhà", "mua nha", "mua đất", "mua dat",
                "xây nhà", "xay nha", "sửa nhà", "sua nha",
                "bất động sản", "bat dong san", "nhà đất", "nha dat",
                "mua bds", "đầu tư bds", "dau tu bds"
            ],
            "Vay mua ô tô xe máy": [
                "mua xe", "mua ô tô", "mua o to", "mua xe máy", "mua xe may",
                "mua auto", "xe hơi", "xe hoi", "phương tiện", "phuong tien",
                "mua oto", "mua xe oto"
            ],
            "Vay kinh doanh": [
                "kinh doanh", "kinh doanh", "làm ăn", "lam an",
                "buôn bán", "buon ban", "mở cửa hàng", "mo cua hang",
                "đầu tư", "dau tu", "sản xuất", "san xuat", "kdoanh",
                "mở shop", "mo shop", "làm việc", "lam viec"
            ],
            "Vay học tập": [
                "học phí", "hoc phi", "du học", "du hoc",
                "học tập", "hoc tap", "đào tạo", "dao tao",
                "học nghề", "hoc nghe", "giáo dục", "giao duc"
            ]
        }
    
    def extract(self, user_message: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract loan information from user message"""
        message_lower = self.normalize_text(user_message)
        extracted = {}
        
        # 1. Extract loan amount
        amount = self._extract_amount(message_lower)
        if amount:
            extracted['loanAmount'] = amount
        
        # 2. Extract loan term
        term = self._extract_term(message_lower)
        if term:
            extracted['loanTerm'] = term
        
        # 3. Extract loan purpose
        purpose = self._extract_purpose(message_lower)
        if purpose:
            extracted['loanPurpose'] = purpose
        
        # 4. Extract loan type
        loan_type = self._extract_loan_type(message_lower)
        if loan_type:
            extracted['loanType'] = loan_type
        
        # 5. Extract sales agent code (if any)
        agent_code = self._extract_agent_code(user_message)  # Use original message for case
        if agent_code:
            extracted['salesAgentCode'] = agent_code
        
        return extracted
    
    def _extract_amount(self, text: str) -> Optional[int]:
        """Extract loan amount from text"""
        # Try each pattern
        for pattern, multiplier in self.amount_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                try:
                    # Extract number and clean it
                    number_str = match.group(1)
                    # Handle comma/dot decimal separators
                    if ',' in number_str and '.' in number_str:
                        # Format like 1,500.5 (treat comma as thousand separator)
                        clean_number = number_str.replace(',', '')
                    elif number_str.count('.') > 1:
                        # Format like 1.500.000 (dots as thousand separators)
                        clean_number = number_str.replace('.', '')
                    elif number_str.count(',') > 1:
                        # Format like 1,500,000 (commas as thousand separators)
                        clean_number = number_str.replace(',', '')
                    else:
                        # Single decimal point
                        clean_number = number_str.replace(',', '.')
                    
                    # Convert to float and multiply
                    amount = float(clean_number) * multiplier
                    return int(amount)
                except ValueError:
                    continue
        return None
    
    def _extract_term(self, text: str) -> Optional[str]:
        """Extract loan term from text"""
        # First try exact mapping
        for standard_term, variations in self.term_mappings.items():
            for variation in variations:
                if variation in text:
                    return standard_term
        
        # Try regex patterns for flexibility
        year_pattern = r'(\d+)\s*(?:năm|nam|year)'
        month_pattern = r'(\d+)\s*(?:tháng|thang|month)'
        
        # Check years
        year_match = re.search(year_pattern, text)
        if year_match:
            years = int(year_match.group(1))
            # Map to standard terms
            year_map = {1: "01 năm", 2: "02 năm", 3: "03 năm", 4: "04 năm", 
                       5: "05 năm", 10: "10 năm", 15: "15 năm", 20: "20 năm"}
            return year_map.get(years)
        
        # Check months
        month_match = re.search(month_pattern, text)
        if month_match:
            months = int(month_match.group(1))
            # Convert months to years
            month_map = {12: "01 năm", 24: "02 năm", 36: "03 năm", 48: "04 năm",
                        60: "05 năm", 120: "10 năm", 180: "15 năm", 240: "20 năm"}
            return month_map.get(months)
        
        return None
    
    def _extract_purpose(self, text: str) -> Optional[str]:
        """Extract loan purpose from text"""
        # Score each purpose based on keyword matches
        scores = {}
        for purpose, keywords in self.purpose_mappings.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                scores[purpose] = score
        
        # Return purpose with highest score
        if scores:
            return max(scores, key=scores.get)
        return None
    
    def _extract_loan_type(self, text: str) -> Optional[str]:
        """Extract loan type from text"""
        # Count keyword matches for each type
        scores = {}
        for loan_type, keywords in self.loan_type_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                scores[loan_type] = score
        
        # Return type with highest score
        if scores:
            return max(scores, key=scores.get)
        return None
    
    def _extract_agent_code(self, text: str) -> Optional[str]:
        """Extract sales agent code (case sensitive)"""
        # Patterns: SALE001, NV123, AGENT_ABC, ABC123, etc.
        patterns = [
            r'(?:mã\s+(?:nhân\s+viên|nv|giới\s+thiệu|agent)?\s*[:\-]?\s*|agent\s*code\s*[:\-]?\s*|với\s+mã\s*)([A-Z][A-Z0-9]{2,10})',  # ABC123
            r'(SALE\d+)',
            r'(NV\d+)',
            r'(AGENT[_\-]?\w+)',
            r'(NVKD\d+)',  # Nhân viên kinh doanh
            r'(REF[_\-]?\w+)',  # Referral code
            r'([A-Z]{2,4}\d{2,6})',  # General pattern: 2-4 letters + 2-6 digits
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        
        return None
