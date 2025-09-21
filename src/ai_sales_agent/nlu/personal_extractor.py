"""
NLU Extractor for Personal Information (Steps 2.1 and 2.2)
"""
import re
from typing import Dict, Any, Optional
from datetime import datetime
from .extractor import BaseExtractor

class PersonalInfoExtractor(BaseExtractor):
    """Extract personal information from user messages"""
    
    def __init__(self):
        super().__init__()
        self._init_mappings()
    
    def _init_mappings(self):
        """Initialize mapping dictionaries"""
        
        # Gender mappings
        self.gender_mappings = {
            "Nam": ["nam", "trai", "ông", "anh", "chú", "bác", "male", "m", "boy"],
            "Nữ": ["nữ", "gái", "bà", "chị", "cô", "dì", "female", "f", "nu", "girl", "woman"]
        }
        
        # Marital status mappings
        self.marital_mappings = {
            "Độc thân": [
                "độc thân", "doc than", "chưa kết hôn", "chua ket hon",
                "chưa lập gia đình", "chua lap gia dinh", "single",
                "chưa có vợ", "chưa có chồng", "chua co vo", "chua co chong",
                "còn độc thân", "con doc than"
            ],
            "Đã kết hôn": [
                "đã kết hôn", "da ket hon", "đã lập gia đình", "da lap gia dinh",
                "có gia đình", "co gia dinh", "married", "đã có vợ", "đã có chồng",
                "da co vo", "da co chong", "có vợ", "có chồng", "co vo", "co chong",
                "lập gia đình", "lap gia dinh"
            ],
            "Ly hôn": [
                "ly hôn", "ly hon", "ly dị", "ly di", "divorced",
                "đã ly hôn", "da ly hon", "đã ly dị", "da ly di"
            ],
            "Góa": [
                "góa", "goa", "góa vợ", "goa vo", "góa chồng", "goa chong",
                "widowed", "mất vợ", "mat vo", "mất chồng", "mat chong"
            ]
        }
        
        # Phone patterns
        self.phone_patterns = [
            r'(?:\+84|84|0)?(\d{9,10})',  # Vietnam phone with optional prefix
            r'(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})',  # formatted phone
            r'(\d{10})',  # plain 10 digits
        ]
        
        # Email pattern
        self.email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        
        # Vietnamese name patterns
        self.name_patterns = [
            r'(?:tên(?:\s+(?:tôi|em|anh|chị))?\s+là\s+|tôi\s+là\s+|em\s+là\s+|tên\s*:\s*)([A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+(?:\s+[A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+)*)',
            r'(?:họ\s+tên|họ\s+và\s+tên)\s*[:=]?\s*([A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][^\n,\.]{2,})',
            r'^([A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+(?:\s+[A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+){1,4})'
        ]
    
    def extract(self, user_message: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract personal information from user message"""
        extracted = {}
        message_lower = self.normalize_text(user_message)
        
        # 1. Extract full name (case sensitive)
        name = self._extract_name(user_message)
        if name:
            extracted['fullName'] = name
        
        # 2. Extract phone number
        phone = self._extract_phone(user_message)
        if phone:
            extracted['phoneNumber'] = phone
        
        # 3. Extract birth year
        birth_year = self._extract_birth_year(message_lower)
        if birth_year:
            extracted['birthYear'] = birth_year
        
        # 4. Extract gender
        gender = self._extract_gender(message_lower)
        if gender:
            extracted['gender'] = gender
        
        # 5. Extract marital status
        marital_status = self._extract_marital_status(message_lower)
        if marital_status:
            extracted['maritalStatus'] = marital_status
        
        # 6. Extract dependents
        dependents = self._extract_dependents(message_lower)
        if dependents is not None:
            extracted['dependents'] = dependents
        
        # 7. Extract email (optional)
        email = self._extract_email(user_message)
        if email:
            extracted['email'] = email
        
        return extracted
    
    def _extract_name(self, text: str) -> Optional[str]:
        """Extract Vietnamese full name"""
        # Try each pattern
        for pattern in self.name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Validate it's a reasonable name
                words = name.split()
                if 2 <= len(words) <= 6 and len(name) >= 5:
                    # Proper case format
                    return ' '.join(word.capitalize() for word in words)
        
        return None
    
    def _extract_phone(self, text: str) -> Optional[str]:
        """Extract phone number"""
        # Remove non-digits except + for international format
        cleaned = re.sub(r'[^\d+]', '', text)
        
        for pattern in self.phone_patterns:
            match = re.search(pattern, cleaned)
            if match:
                phone = match.group(1) if match.groups() else match.group(0)
                # Clean and format
                phone = re.sub(r'[-.\s]', '', phone)
                
                # Ensure it's Vietnamese format
                if len(phone) == 10 and phone.startswith('0'):
                    return phone
                elif len(phone) == 9:
                    return '0' + phone  # Add leading 0
                elif len(phone) == 11 and phone.startswith('84'):
                    return '0' + phone[2:]  # Convert from +84 format
        
        return None
    
    def _extract_birth_year(self, text: str) -> Optional[int]:
        """Extract birth year"""
        current_year = datetime.now().year
        
        # Direct year patterns
        year_patterns = [
            r'sinh\s+năm\s+(\d{4})',
            r'năm\s+sinh\s*[:=]?\s*(\d{4})',
            r'(\d{4})\s*(?:là\s+)?năm\s+sinh',
            r'sinh\s+(\d{4})',
            r'năm\s+(\d{4})',
            r'(\d{4})'  # Last resort - any 4 digit number
        ]
        
        for pattern in year_patterns:
            match = re.search(pattern, text)
            if match:
                year = int(match.group(1))
                # Validate year (18-65 years old)
                if current_year - 65 <= year <= current_year - 18:
                    return year
        
        # Age patterns - convert to birth year
        age_patterns = [
            r'(\d{1,2})\s*tuổi',
            r'tuổi\s*[:=]?\s*(\d{1,2})',
            r'(\d{1,2})\s*(?:tuổi|t)',
        ]
        
        for pattern in age_patterns:
            match = re.search(pattern, text)
            if match:
                age = int(match.group(1))
                if 18 <= age <= 65:
                    return current_year - age
        
        return None
    
    def _extract_gender(self, text: str) -> Optional[str]:
        """Extract gender with priority order and context awareness"""
        # Use word boundaries to avoid partial matches
        import re
        
        # Check Nữ patterns first (more specific) with word boundaries
        nu_patterns = [r'\bnữ\b', r'\bgái\b', r'\bbà\b', r'\bchị\b', r'\bcô\b', r'\bdì\b', 
                      r'\bfemale\b', r'\bf\b', r'\bnu\b', r'\bgirl\b', r'\bwoman\b']
        for pattern in nu_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return "Nữ"
        
        # Then check Nam patterns with word boundaries
        nam_patterns = [r'\bnam\b', r'\btrai\b', r'\bông\b', r'\banh\b', r'\bchú\b', 
                       r'\bbác\b', r'\bmale\b', r'\bm\b', r'\bboy\b']
        for pattern in nam_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return "Nam"
                
        return None
    
    def _extract_marital_status(self, text: str) -> Optional[str]:
        """Extract marital status"""
        for status, keywords in self.marital_mappings.items():
            for keyword in keywords:
                if keyword in text:
                    return status
        return None
    
    def _extract_dependents(self, text: str) -> Optional[int]:
        """Extract number of dependents"""
        # Check for "no dependents" first (expanded patterns)
        no_dependent_keywords = [
            "không có con", "khong co con",
            "không có người phụ thuộc", "khong co nguoi phu thuoc", 
            "không người phụ thuộc", "khong nguoi phu thuoc",
            "không có ai phụ thuộc", "khong co ai phu thuoc",
            "sống một mình", "song mot minh",
            "độc thân không có", "doc than khong co",
            "chưa có con", "chua co con",
            "0 người phụ thuộc", "0 nguoi phu thuoc",
            "không phụ thuộc", "khong phu thuoc",
            "không ai phụ thuộc", "khong ai phu thuoc"
        ]
        
        for keyword in no_dependent_keywords:
            if keyword in text:
                return 0
        
        # Patterns for dependents (enhanced)
        patterns = [
            r'(\d+)\s*(?:người\s+)?(?:phụ\s+thuộc|phu\s+thuoc)',
            r'(?:phụ\s+thuộc|phu\s+thuoc)\s*[:=]?\s*(\d+)',
            r'có\s+(\d+)\s+(?:con|người)',
            r'(\d+)\s+con',
            r'(\d+)\s+(?:đứa\s+)?con',
            r'nuôi\s+(\d+)',
            r'(\d+)\s+người\s+(?:phụ\s+thuộc|phu\s+thuoc)',
            r'gia\s+đình\s+(\d+)\s+người',  # "gia đình 5 người"
            r'có\s+vợ\s+và\s+(\d+)\s+con',  # "có vợ và 3 con" -> extract 3, not 4
            r'có\s+chồng\s+và\s+(\d+)\s+con',  # "có chồng và 2 con" -> extract 2
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        return None
    
    def _extract_email(self, text: str) -> Optional[str]:
        """Extract email address"""
        match = re.search(self.email_pattern, text)
        if match:
            return match.group(1).lower()
        return None
