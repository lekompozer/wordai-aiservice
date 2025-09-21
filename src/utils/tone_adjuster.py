"""
Tone Adjuster utility for adjusting AI response tone
"""

class ToneAdjuster:
    """
    Utility class for adjusting AI response tone based on configuration
    """
    
    def __init__(self, tone_config: dict = None):
        """
        Initialize ToneAdjuster with tone configuration
        
        Args:
            tone_config: Dictionary containing tone settings
        """
        self.tone_config = tone_config or {}
        
    def adjust_tone(self, text: str, target_tone: str = "friendly") -> str:
        """
        Adjust the tone of given text
        
        Args:
            text: Input text to adjust
            target_tone: Target tone (friendly, professional, casual, etc.)
            
        Returns:
            Tone-adjusted text
        """
        # For now, return text as-is
        # Can be enhanced with actual tone adjustment logic
        return text
        
    def get_tone_prefix(self, tone: str = "friendly") -> str:
        """
        Get appropriate prefix for given tone
        
        Args:
            tone: Desired tone
            
        Returns:
            Prefix string for the tone
        """
        prefixes = {
            "friendly": "[Theo dữ liệu ứng dụng] ",
            "professional": "[Báo cáo phân tích] ",
            "casual": "[Thông tin tham khảo] ",
            "formal": "[Kết quả tra cứu] "
        }
        
        return prefixes.get(tone, "[Theo dữ liệu ứng dụng] ")
