"""
Base Extractor Class for NLU
"""
import re
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

class BaseExtractor(ABC):
    """Base class for all extractors"""
    
    def __init__(self):
        self.confidence_threshold = 0.7
    
    @abstractmethod
    def extract(self, user_message: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract information from user message"""
        pass
    
    def normalize_text(self, text: str) -> str:
        """Normalize Vietnamese text"""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower().strip()
        
        # Remove extra spaces
        text = re.sub(r'\s+', ' ', text)
        
        return text
    
    def calculate_confidence(self, extracted_count: int, total_fields: int) -> float:
        """Calculate extraction confidence score"""
        if total_fields == 0:
            return 1.0
        return min(extracted_count / total_fields, 1.0)
    
    def validate_extraction(self, field: str, value: Any, rules: Dict[str, Any]) -> Optional[str]:
        """Validate extracted field against rules"""
        if not rules:
            return None
            
        # Check min/max for numeric fields
        if "min" in rules and isinstance(value, (int, float)):
            if value < rules["min"]:
                return f"Giá trị quá thấp (tối thiểu: {rules['min']:,})"
        
        if "max" in rules and isinstance(value, (int, float)):
            if value > rules["max"]:
                return f"Giá trị quá cao (tối đa: {rules['max']:,})"
        
        # Check enum values
        if "enum" in rules and value not in rules["enum"]:
            return f"Giá trị không hợp lệ. Phải là một trong: {', '.join(rules['enum'])}"
        
        return None
