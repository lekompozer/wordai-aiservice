"""
Base template for industry-specific data extraction
Abstract base class cho các template extraction theo ngành
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
import json


class BaseExtractionTemplate(ABC):
    """Abstract base class for extraction templates"""

    def __init__(self):
        self.template_name = self.__class__.__name__
        self.version = "2.0"
        self.industry = self._get_industry()

    @abstractmethod
    def _get_industry(self) -> str:
        """Get industry name for this template"""
        pass

    @abstractmethod
    def get_system_prompt(self, data_type: str) -> str:
        """Get system prompt for this template and data type"""
        pass

    @abstractmethod
    def get_extraction_schema(self, data_type: str) -> Dict[str, Any]:
        """Get JSON schema for extraction"""
        pass

    @abstractmethod
    def get_validation_rules(self, data_type: str) -> Dict[str, Any]:
        """Get validation rules for extracted data"""
        pass

    @abstractmethod
    def post_process(
        self, extracted_data: Dict[str, Any], data_type: str
    ) -> Dict[str, Any]:
        """Post-process extracted data"""
        pass

    def post_process_auto_categorized(
        self, extracted_data: Dict[str, Any], target_categories: List[str]
    ) -> Dict[str, Any]:
        """Post-process auto-categorized data (default implementation)"""
        # Default implementation - subclasses can override for industry-specific logic
        result = {}

        # Copy raw content
        if "raw_content" in extracted_data:
            result["raw_content"] = extracted_data["raw_content"]

        # Process structured data
        if "structured_data" in extracted_data:
            structured_data = extracted_data["structured_data"]

            # Copy each target category
            for category in target_categories:
                if category in structured_data:
                    result[category] = structured_data[category]
                else:
                    result[category] = []

            # Copy extraction summary
            if "extraction_summary" in structured_data:
                result["extraction_summary"] = structured_data["extraction_summary"]

        # Ensure all target categories exist
        for category in target_categories:
            if category not in result:
                result[category] = []

        return result

    def build_extraction_prompt(
        self, file_name: str, data_type: str, language: str = "vi"
    ) -> str:
        """Build complete extraction prompt"""
        schema = self.get_extraction_schema(data_type)

        return f"""
Extract {data_type} data from this {self.industry} document: {file_name}
Language: {language}

IMPORTANT: Follow this EXACT schema structure:
{json.dumps(schema, indent=2, ensure_ascii=False)}

Extraction Rules:
1. Extract ALL {data_type} items found in the document
2. Use null for missing optional fields
3. Ensure all prices are numbers (not strings)
4. Include confidence_score (0.0-1.0) for each item
5. Categorize items correctly based on industry standards
6. For Vietnamese documents, include both Vietnamese and English names when possible
7. Extract complete industry_data structure as specified
8. For each item, generate optimized content_for_embedding that includes key searchable terms

Output format:
{{
    "{data_type}": [...],
    "raw_data": "original extracted text for backup",
    "content_for_embedding": "optimized search content combining all items with key terms, categories, and descriptions",
    "metadata": {{
        "total_items": number,
        "language": "{language}",
        "confidence": 0.0-1.0,
        "template_used": "{self.template_name}",
        "extraction_timestamp": "{datetime.now().isoformat()}"
    }}
}}

CONTENT_FOR_EMBEDDING Guidelines:
- Include all item names and key terms
- Add category information and industry keywords
- Include important features, benefits, and specifications
- Make it search-friendly for RAG retrieval
- Limit to 2000 characters for optimal embedding

Return ONLY valid JSON, no additional text.
        """

    def validate_extracted_data(
        self, data: Dict[str, Any], data_type: str
    ) -> Dict[str, Any]:
        """Validate extracted data against rules"""
        rules = self.get_validation_rules(data_type)
        items = data.get(data_type, [])

        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "validated_items": [],
        }

        for idx, item in enumerate(items):
            item_errors = []

            # Check required fields
            for field in rules.get("required_fields", []):
                if field not in item or item[field] is None:
                    item_errors.append(f"Missing required field: {field}")

            # Check price ranges
            if "price" in item and item["price"] is not None:
                if item["price"] < rules.get("price_min", 0):
                    item_errors.append(f"Price too low: {item['price']}")
                if item["price"] > rules.get("price_max", float("inf")):
                    item_errors.append(f"Price too high: {item['price']}")

            # Add item-specific validation
            if item_errors:
                validation_result["errors"].append(
                    {
                        "item_index": idx,
                        "item_name": item.get("name", "Unknown"),
                        "errors": item_errors,
                    }
                )
                validation_result["valid"] = False
            else:
                validation_result["validated_items"].append(item)

        return validation_result

    def generate_tags(self, item: Dict[str, Any]) -> List[str]:
        """Generate relevant tags for an item"""
        tags = set()

        # Add category as tag
        if item.get("category"):
            tags.add(item["category"].lower())

        # Add industry as tag
        tags.add(self.industry.lower())

        # Add name words as tags (first 3 words)
        if item.get("name"):
            name_words = item["name"].lower().split()
            for word in name_words[:3]:
                if len(word) > 2:  # Skip short words
                    tags.add(word)

        return list(tags)

    def create_sku(self, item: Dict[str, Any], index: int) -> str:
        """Generate SKU for item if not provided"""
        if item.get("sku"):
            return item["sku"]

        # Generate SKU based on category and index
        category = item.get("category", "ITEM")
        industry_code = self.industry.upper()[:3]
        return f"{industry_code}-{category.upper()[:3]}-{index+1:03d}"

    def get_extraction_prompt(
        self, file_name: str = "document", language: str = "vi"
    ) -> str:
        """Alias for build_extraction_prompt for backward compatibility"""
        # Extract data_type from the call context or default to 'products'
        # This is a simplified approach - you might want to pass data_type explicitly
        return self.build_extraction_prompt("products", file_name, language)
