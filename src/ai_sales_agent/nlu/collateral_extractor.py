"""
Collateral Information Extractor for Steps 3.1 and 3.2
Trích xuất thông tin tài sản đảm bảo
"""

import re
from typing import Dict, Any, Optional
from .extractor import BaseExtractor

class CollateralExtractor(BaseExtractor):
    """Extractor for collateral information (Steps 3.1, 3.2)"""
    
    def __init__(self):
        super().__init__()
        
        # Collateral type patterns
        self.collateral_type_patterns = {
            "Bất động sản": [
                r'bất\s+động\s+sản|bđs|nhà\s+đất|đất\s+đai|căn\s+hộ|chung\s+cư',
                r'nhà\s+(riêng|cấp\s+4|tầng)|biệt\s+thự|villa',
                r'đất\s+(nền|thổ\s+cư|ở|xây\s+dựng)',
                r'shop\s+house|townhouse|penthouse'
            ],
            "Ô tô": [
                r'ô\s+tô|xe\s+hơi|xe\s+con|xe\s+sedan|xe\s+suv',
                r'toyota|honda|mazda|hyundai|ford|bmw|mercedes',
                r'xe\s+\d+\s+chỗ|xe\s+bán\s+tải|pickup'
            ],
            "Xe máy": [
                r'xe\s+máy|motor|moto|scooter',
                r'honda\s+(wave|winner|vision)|yamaha\s+(exciter|sirius)',
                r'suzuki|piaggio|sym'
            ],
            "Vàng": [
                r'vàng|gold|kim\s+loại\s+quý',
                r'vàng\s+(miếng|nhẫn|dây\s+chuyền|lắc)',
                r'vàng\s+\d+k|vàng\s+24k|vàng\s+18k'
            ],
            "Giấy tờ có giá": [
                r'giấy\s+tờ\s+có\s+giá|chứng\s+khoán|cổ\s+phiếu',
                r'trái\s+phiếu|sổ\s+tiết\s+kiệm|sổ\s+ngân\s+hàng',
                r'bảo\s+hiểm\s+nhân\s+thọ|hợp\s+đồng\s+đầu\s+tư'
            ],
            "Khác": [
                r'máy\s+móc|thiết\s+bị|tài\s+sản\s+khác',
                r'kim\s+cương|đồng\s+hồ\s+xa\s+xỉ|túi\s+xách\s+hiệu'
            ]
        }
        
        # Value patterns (Vietnamese currency)
        self.value_patterns = [
            (r'(\d+(?:[.,]\d+)?)\s*tỷ\s*(?:đồng|vnd)?', 1000000000),
            (r'(\d+(?:[.,]\d+)?)\s*triệu\s*(?:đồng|vnd)?', 1000000),
            (r'(\d+(?:[.,]\d+)?)\s*nghìn\s*(?:đồng|vnd)?', 1000),
            (r'(\d+(?:[.,]\d+)?)\s*(?:đồng|vnd)', 1),
            (r'khoảng\s+(\d+(?:[.,]\d+)?)\s*tỷ', 1000000000),
            (r'gần\s+(\d+(?:[.,]\d+)?)\s*triệu', 1000000),
            (r'ước\s+tính\s+(\d+(?:[.,]\d+)?)\s*tỷ', 1000000000)
        ]
    
    def extract(self, user_message: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract collateral information from user message"""
        normalized_text = self.normalize_text(user_message)
        extracted_data = {}
        
        # Extract collateral type
        collateral_type = self._extract_collateral_type(normalized_text)
        if collateral_type:
            extracted_data["collateralType"] = collateral_type
        
        # Extract collateral info (description)
        collateral_info = self._extract_collateral_info(user_message, collateral_type)
        if collateral_info:
            extracted_data["collateralInfo"] = collateral_info
        
        # Extract collateral value
        collateral_value = self._extract_collateral_value(normalized_text)
        if collateral_value:
            extracted_data["collateralValue"] = collateral_value
        
        # Extract image info (optional)
        image_info = self._extract_image_info(normalized_text)
        if image_info:
            extracted_data["collateralImage"] = image_info
        
        return extracted_data
    
    def _extract_collateral_type(self, text: str) -> Optional[str]:
        """Extract collateral type"""
        
        for collateral_type, patterns in self.collateral_type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return collateral_type
        
        return None
    
    def _extract_collateral_info(self, original_text: str, collateral_type: str = None) -> Optional[str]:
        """Extract detailed collateral information"""
        
        # Common description patterns
        info_patterns = [
            r'(?:là|có)\s+(.+?)(?:\s+(?:trị\s+giá|giá\s+trị|ước\s+tính)|$)',
            r'mô\s+tả[:\s]*(.+?)(?:\s+giá|$)',
            r'chi\s+tiết[:\s]*(.+?)(?:\s+giá|$)',
            r'(?:loại|kiểu)[:\s]*(.+?)(?:\s+giá|$)'
        ]
        
        text = original_text.strip()
        
        # Try to extract description
        for pattern in info_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info = match.group(1).strip()
                if len(info) > 5:  # Reasonable description length
                    return info
        
        # Fallback: extract based on collateral type
        if collateral_type:
            type_specific_patterns = {
                "Bất động sản": [
                    r'(nhà\s+\d+\s+tầng.*?)(?:\s+giá|$)',
                    r'(căn\s+hộ.*?)(?:\s+giá|$)',
                    r'(đất\s+\d+m2.*?)(?:\s+giá|$)'
                ],
                "Ô tô": [
                    r'(xe.*?\d{4}.*?)(?:\s+giá|$)',
                    r'(\w+\s+\w+.*?)(?:\s+giá|$)'
                ],
                "Xe máy": [
                    r'(xe\s+máy.*?)(?:\s+giá|$)',
                    r'(\w+\s+\w+.*?\d+cc.*?)(?:\s+giá|$)'
                ]
            }
            
            patterns = type_specific_patterns.get(collateral_type, [])
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
        
        # Last resort: return cleaned original text if reasonable
        if len(text) > 10 and len(text) < 200:
            return text
        
        return None
    
    def _extract_collateral_value(self, text: str) -> Optional[int]:
        """Extract collateral value in VND"""
        
        for pattern, multiplier in self.value_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value_str = match.group(1).replace(',', '.')
                    value = float(value_str)
                    return int(value * multiplier)
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _extract_image_info(self, text: str) -> Optional[str]:
        """Extract image/photo information"""
        
        image_patterns = [
            r'có\s+(hình\s+ảnh|ảnh|photo|hình)',
            r'đính\s+kèm\s+(ảnh|hình)',
            r'gửi\s+(ảnh|hình|photo)',
            r'upload\s+(ảnh|hình|file)',
            r'(không|chưa)\s+có\s+(ảnh|hình)'
        ]
        
        for pattern in image_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if "không" in match.group(0) or "chưa" in match.group(0):
                    return "Chưa có hình ảnh"
                else:
                    return "Có hình ảnh"
        
        return None
