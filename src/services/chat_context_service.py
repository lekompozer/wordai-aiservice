"""
Chat Context Service
Build chat prompts with file context
"""

import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class ChatContextService:
    """
    Service for building chat prompts with file context
    Simple text-based, no HTML processing
    """
    
    @staticmethod
    def build_chat_prompt(
        user_message: str,
        selected_text: Optional[str] = None,
        current_file_name: Optional[str] = None,
        current_file_content: Optional[str] = None,
        additional_contexts: Optional[List[Dict]] = None
    ) -> str:
        """
        Build chat prompt with file context
        
        Args:
            user_message: User's question/message
            selected_text: Text user selected in file
            current_file_name: Name of current file
            current_file_content: Full content of current file
            additional_contexts: List of additional file contexts
            
        Returns:
            Complete prompt string
        """
        prompt_parts = []
        
        # Add system context if we have file context
        if current_file_name or additional_contexts:
            prompt_parts.append("=== CONTEXT ===")
        
        # Add current file context
        if current_file_name and current_file_content:
            prompt_parts.append(f"\n--- File: {current_file_name} ---")
            prompt_parts.append(current_file_content)
        
        # Add additional contexts
        if additional_contexts:
            for ctx in additional_contexts:
                file_name = ctx.get('fileName', 'Unknown')
                content = ctx.get('content', '')
                if content:
                    prompt_parts.append(f"\n--- Reference File: {file_name} ---")
                    prompt_parts.append(content)
        
        # Add selected text emphasis
        if selected_text:
            prompt_parts.append("\n=== SELECTED TEXT ===")
            prompt_parts.append(selected_text)
            prompt_parts.append("\nThe user is asking about the selected text above.")
        
        # Add user message
        prompt_parts.append("\n=== USER QUESTION ===")
        prompt_parts.append(user_message)
        
        # Instructions
        if selected_text or current_file_content:
            prompt_parts.append("\n=== INSTRUCTIONS ===")
            prompt_parts.append("- Answer based on the provided context")
            prompt_parts.append("- Reference specific parts when relevant")
            prompt_parts.append("- Be concise and helpful")
            prompt_parts.append("- If information is not in context, say so")
        
        return "\n".join(prompt_parts)
    
    @staticmethod
    def format_conversation_history(history: List[Dict]) -> List[Dict]:
        """
        Format conversation history for AI providers
        
        Args:
            history: List of {role, content} dicts
            
        Returns:
            Formatted history list
        """
        if not history:
            return []
        
        formatted = []
        for msg in history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            if role in ['user', 'assistant', 'system']:
                formatted.append({
                    'role': role,
                    'content': content
                })
        
        # Limit history to last 10 messages to avoid token overflow
        return formatted[-10:]
    
    @staticmethod
    def estimate_context_size(
        selected_text: Optional[str] = None,
        current_file_content: Optional[str] = None,
        additional_contexts: Optional[List[Dict]] = None
    ) -> int:
        """
        Estimate total context size in characters
        
        Returns:
            Total character count
        """
        total = 0
        
        if selected_text:
            total += len(selected_text)
        
        if current_file_content:
            total += len(current_file_content)
        
        if additional_contexts:
            for ctx in additional_contexts:
                content = ctx.get('content', '')
                total += len(content)
        
        return total
    
    @staticmethod
    def truncate_context_if_needed(
        text: str,
        max_chars: int,
        keep_start: bool = True
    ) -> str:
        """
        Truncate text if exceeds max characters
        
        Args:
            text: Text to truncate
            max_chars: Maximum characters
            keep_start: Keep start or end of text
            
        Returns:
            Truncated text
        """
        if len(text) <= max_chars:
            return text
        
        if keep_start:
            return text[:max_chars] + "\n\n[... content truncated ...]"
        else:
            return "[... content truncated ...]\n\n" + text[-max_chars:]
