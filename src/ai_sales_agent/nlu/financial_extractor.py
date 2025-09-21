"""
Financial Information Extractor for Steps 4.1, 4.2, 4.3
Trích xuất thông tin tài chính
"""

import re
from typing import Dict, Any, Optional
from .extractor import BaseExtractor

class FinancialExtractor(BaseExtractor):
    """Extractor for financial information (Steps 4.1, 4.2, 4.3)"""
    
    def __init__(self):
        super().__init__()
        
        # Income source patterns
        self.income_source_patterns = {
            "Lương": [
                r'lương|lương\s+nhân\s+viên|lương\s+cố\s+định',
                r'làm\s+việc\s+cho\s+công\s+ty|nhân\s+viên',
                r'công\s+chức|viên\s+chức|cán\s+bộ'
            ],
            "Kinh doanh": [
                r'kinh\s+doanh|buôn\s+bán|thương\s+mại',
                r'chủ\s+shop|chủ\s+cửa\s+hàng|bán\s+hàng',
                r'tự\s+làm\s+chủ|freelance|tự\s+do'
            ],
            "Đầu tư": [
                r'đầu\s+tư|cho\s+thuê|thu\s+nhập\s+từ\s+đầu\s+tư',
                r'cổ\s+tức|lãi\s+suất|bất\s+động\s+sản\s+cho\s+thuê'
            ],
            "Khác": [
                r'thu\s+nhập\s+khác|nghề\s+tự\s+do|công\s+việc\s+khác'
            ]
        }
        
        # Monthly income patterns (Vietnamese currency)
        self.income_patterns = [
            (r'(\d+(?:[.,]\d+)?)\s*triệu\s*(?:đồng|vnd)?(?:\s*/\s*tháng)?', 1000000),
            (r'(\d+(?:[.,]\d+)?)\s*tr\s*(?:/\s*tháng)?', 1000000),
            (r'(\d+(?:[.,]\d+)?)\s*nghìn\s*(?:đồng|vnd)?(?:\s*/\s*tháng)?', 1000),
            (r'(\d+(?:[.,]\d+)?)\s*k\s*(?:/\s*tháng)?', 1000),
            (r'(\d+(?:[.,]\d+)?)\s*(?:đồng|vnd)(?:\s*/\s*tháng)?', 1),
            (r'khoảng\s+(\d+(?:[.,]\d+)?)\s*triệu', 1000000),
            (r'tầm\s+(\d+(?:[.,]\d+)?)\s*tr', 1000000)
        ]
        
        # Work experience patterns
        self.experience_patterns = [
            r'(\d+(?:[.,]\d+)?)\s*năm(?:\s+kinh\s+nghiệm)?',
            r'làm\s+(?:được\s+)?(\d+(?:[.,]\d+)?)\s*năm',
            r'(\d+(?:[.,]\d+)?)\s*năm\s+(?:làm\s+việc|công\s+tác)',
            r'kinh\s+nghiệm\s+(\d+(?:[.,]\d+)?)\s*năm',
            r'mới\s+ra\s+trường|chưa\s+có\s+kinh\s+nghiệm'  # 0 years
        ]
    
    def extract(self, user_message: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract financial information from user message"""
        normalized_text = self.normalize_text(user_message)
        original_text = user_message.strip()
        extracted_data = {}
        
        # Extract monthly income
        monthly_income = self._extract_monthly_income(normalized_text)
        if monthly_income:
            extracted_data["monthlyIncome"] = monthly_income
        
        # Extract primary income source
        income_source = self._extract_income_source(normalized_text)
        if income_source:
            extracted_data["primaryIncomeSource"] = income_source
        
        # Extract company name
        company_name = self._extract_company_name(original_text)
        if company_name:
            extracted_data["companyName"] = company_name
        
        # Extract job title
        job_title = self._extract_job_title(original_text)
        if job_title:
            extracted_data["jobTitle"] = job_title
        
        # Extract work experience
        work_experience = self._extract_work_experience(normalized_text)
        if work_experience is not None:
            extracted_data["workExperience"] = work_experience
        
        # Extract other income (optional)
        other_income = self._extract_other_income(normalized_text)
        if other_income:
            extracted_data["otherIncomeAmount"] = other_income
        
        # Extract total assets (optional)
        total_assets = self._extract_total_assets(normalized_text)
        if total_assets:
            extracted_data["totalAssets"] = total_assets
        
        # Extract bank name (optional)
        bank_name = self._extract_bank_name(original_text)
        if bank_name:
            extracted_data["bankName"] = bank_name
        
        return extracted_data
    
    def _extract_monthly_income(self, text: str) -> Optional[int]:
        """Extract monthly income in VND"""
        
        for pattern, multiplier in self.income_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value_str = match.group(1).replace(',', '.')
                    value = float(value_str)
                    return int(value * multiplier)
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _extract_income_source(self, text: str) -> Optional[str]:
        """Extract primary income source"""
        
        for source_type, patterns in self.income_source_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return source_type
        
        return None
    
    def _extract_company_name(self, text: str) -> Optional[str]:
        """Extract company name"""
        
        company_patterns = [
            r'(?:làm\s+(?:việc\s+)?(?:tại|ở|cho)\s+|công\s+ty\s+)([A-Za-z0-9\s\.\-]+?)(?:\s+(?:làm|là|với|có)|[,.]|$)',
            r'tên\s+công\s+ty[:\s]*([^,.\n]+)',
            r'công\s+ty[:\s]*([^,.\n]+)',
            r'(?:tại|ở)\s+([A-Za-z0-9\s\.\-]+?)(?:\s+làm|$)'
        ]
        
        for pattern in company_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                # Filter out common words that are not company names
                if len(company) > 2 and not re.match(r'^(là|làm|có|với|tại|ở)$', company, re.IGNORECASE):
                    return company.title()
        
        return None
    
    def _extract_job_title(self, text: str) -> Optional[str]:
        """Extract job title/position"""
        
        job_patterns = [
            r'(?:làm|là|chức\s+vụ|vị\s+trí)[:\s]*([^,.\n]+?)(?:\s+(?:tại|ở|với)|[,.]|$)',
            r'(?:nhân\s+viên|chuyên\s+viên|trưởng\s+phòng|giám\s+đốc|quản\s+lý)[:\s]*([^,.\n]*)',
            r'chức\s+danh[:\s]*([^,.\n]+)',
            r'(?:position|job\s+title)[:\s]*([^,.\n]+)'
        ]
        
        for pattern in job_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                job_title = match.group(1).strip()
                if len(job_title) > 2:
                    return job_title.title()
        
        # Common job titles
        common_jobs = [
            r'(nhân\s+viên\s+\w+)', r'(chuyên\s+viên\s+\w+)', r'(trưởng\s+phòng\s+\w+)',
            r'(giám\s+đốc\s+\w*)', r'(quản\s+lý\s+\w*)', r'(kế\s+toán)', r'(thư\s+ký)',
            r'(bác\s+sĩ)', r'(y\s+tá)', r'(giáo\s+viên)', r'(kỹ\s+sư\s+\w*)',
            r'(lập\s+trình\s+viên)', r'(thiết\s+kế\s+\w*)'
        ]
        
        for job_pattern in common_jobs:
            match = re.search(job_pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).title()
        
        return None
    
    def _extract_work_experience(self, text: str) -> Optional[float]:
        """Extract work experience in years"""
        
        # Check for "no experience" patterns first
        no_exp_patterns = [
            r'mới\s+ra\s+trường', r'chưa\s+có\s+kinh\s+nghiệm',
            r'mới\s+bắt\s+đầu', r'không\s+có\s+kinh\s+nghiệm'
        ]
        
        for pattern in no_exp_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return 0.0
        
        # Extract numeric experience
        for pattern in self.experience_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not re.search(r'mới\s+ra\s+trường', match.group(0), re.IGNORECASE):
                try:
                    years_str = match.group(1).replace(',', '.')
                    return float(years_str)
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _extract_other_income(self, text: str) -> Optional[int]:
        """Extract other income amount"""
        
        other_income_indicators = [
            r'thu\s+nhập\s+khác', r'thu\s+nhập\s+phụ', r'income\s+khác',
            r'kiếm\s+thêm', r'làm\s+thêm', r'part\s*time'
        ]
        
        # Check if other income is mentioned
        has_other_income = False
        for indicator in other_income_indicators:
            if re.search(indicator, text, re.IGNORECASE):
                has_other_income = True
                break
        
        if has_other_income:
            # Try to extract amount
            for pattern, multiplier in self.income_patterns:
                match = re.search(indicator + r'.*?' + pattern, text, re.IGNORECASE)
                if match:
                    try:
                        value_str = match.group(2).replace(',', '.')  # group(2) because indicator adds group(1)
                        value = float(value_str)
                        return int(value * multiplier)
                    except (ValueError, IndexError):
                        continue
        
        return None
    
    def _extract_total_assets(self, text: str) -> Optional[int]:
        """Extract total assets value"""
        
        asset_patterns = [
            r'(?:tổng\s+)?tài\s+sản[:\s]*(\d+(?:[.,]\d+)?)\s*(tỷ|triệu|nghìn)?',
            r'(?:total\s+)?assets?[:\s]*(\d+(?:[.,]\d+)?)\s*(tỷ|triệu|nghìn)?',
            r'giá\s+trị\s+tài\s+sản[:\s]*(\d+(?:[.,]\d+)?)\s*(tỷ|triệu|nghìn)?'
        ]
        
        for pattern in asset_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value_str = match.group(1).replace(',', '.')
                    value = float(value_str)
                    
                    unit = match.group(2) if len(match.groups()) > 1 else ""
                    multiplier = 1
                    if "tỷ" in unit:
                        multiplier = 1000000000
                    elif "triệu" in unit:
                        multiplier = 1000000
                    elif "nghìn" in unit:
                        multiplier = 1000
                    
                    return int(value * multiplier)
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _extract_bank_name(self, text: str) -> Optional[str]:
        """Extract bank name"""
        
        # Common Vietnamese banks
        bank_names = [
            "Vietcombank", "VCB", "Techcombank", "TCB", "BIDV", "VietinBank", "CTG",
            "Agribank", "MB Bank", "MB", "ACB", "Sacombank", "STB", "VPBank", "VPB",
            "TPBank", "TPB", "HDBank", "HDB", "MSB", "Maritime Bank", "SHB",
            "Eximbank", "EIB", "LienVietPostBank", "LPB", "PVcomBank", "PVB",
            "OCB", "Orient", "SeABank", "SEA", "VIB", "Nam A Bank", "NAB",
            "Bac A Bank", "BAB", "Kienlongbank", "KLB", "Dong A Bank", "DAB"
        ]
        
        bank_patterns = [
            r'(?:ngân\s+hàng\s+|bank\s+)([A-Za-z0-9\s]+)',
            r'(?:nhận\s+lương\s+(?:tại|ở)\s+|lương\s+từ\s+)([A-Za-z0-9\s]+)',
            r'(?:tài\s+khoản\s+(?:tại|ở)\s+)([A-Za-z0-9\s]+)'
        ]
        
        # Check for specific bank names first
        for bank in bank_names:
            if re.search(rf'\b{re.escape(bank)}\b', text, re.IGNORECASE):
                return bank
        
        # Extract from patterns
        for pattern in bank_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                bank_candidate = match.group(1).strip()
                if len(bank_candidate) > 2:
                    return bank_candidate.title()
        
        return None
