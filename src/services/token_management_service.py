"""
Token Management Service
Manages token limits and content truncation for AI providers
"""

import re
import logging
from typing import List, Dict, Tuple
from bs4 import BeautifulSoup

logger = logging.getLogger("chatbot")


class TokenManagementService:
    """
    Service for managing tokens and content length
    Ensures content fits within AI provider token limits
    """

    # Token limits per provider (input context)
    TOKEN_LIMITS = {
        "deepseek": 32000,  # DeepSeek context window
        "chatgpt": 128000,  # GPT-4o has 128k context
        "gemini": 1048576,  # Gemini 2.5 Pro: 1M+ input tokens
        "qwen": 32000,  # Qwen 3 via Cerebras: 32k limit
        "cerebras": 32000,  # Cerebras default
    }

    # Reserve tokens for response (output limits)
    RESPONSE_RESERVE = {
        "deepseek": 4000,  # DeepSeek: 4k output
        "chatgpt": 8000,  # GPT-4o: 8k max output
        "gemini": 65536,  # Gemini 2.5 Pro: 65k output limit
        "qwen": 4000,  # Qwen 3: 4k output
        "cerebras": 4000,  # Cerebras: 4k output
    }

    # Approximate chars per token (English/Vietnamese mix)
    CHARS_PER_TOKEN = 3.5

    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        """
        Estimate token count from text
        Simple heuristic: ~3.5 chars per token for mixed EN/VI
        """
        return int(len(text) / cls.CHARS_PER_TOKEN)

    @classmethod
    def truncate_to_token_limit(
        cls, text: str, max_tokens: int, preserve_start: bool = True
    ) -> str:
        """
        Truncate text to fit within token limit

        Args:
            text: Text to truncate
            max_tokens: Maximum tokens allowed
            preserve_start: If True, keep beginning; if False, keep end

        Returns:
            Truncated text
        """
        current_tokens = cls.estimate_tokens(text)

        if current_tokens <= max_tokens:
            return text

        # Calculate target character count
        target_chars = int(max_tokens * cls.CHARS_PER_TOKEN)

        if preserve_start:
            # Keep beginning
            truncated = text[:target_chars]
            # Try to cut at sentence boundary
            last_period = truncated.rfind(".")
            if last_period > target_chars * 0.8:  # Within 80% of target
                truncated = truncated[: last_period + 1]
        else:
            # Keep ending
            truncated = text[-target_chars:]
            # Try to cut at sentence boundary
            first_period = truncated.find(".")
            if first_period < target_chars * 0.2:  # Within first 20%
                truncated = truncated[first_period + 1 :].lstrip()

        logger.info(
            f"Truncated content: {current_tokens} → {cls.estimate_tokens(truncated)} tokens"
        )
        return truncated

    @classmethod
    def smart_truncate_html(
        cls, html: str, max_tokens: int, priority: str = "middle"
    ) -> str:
        """
        Smart truncate HTML content while preserving structure

        Args:
            html: HTML content
            max_tokens: Max tokens allowed
            priority: 'start', 'middle', or 'end' - which part to keep

        Returns:
            Truncated HTML
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Get all text blocks
            blocks = []
            for element in soup.find_all(
                ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"]
            ):
                text = element.get_text(strip=True)
                if text:
                    blocks.append(
                        {
                            "element": element,
                            "text": text,
                            "tokens": cls.estimate_tokens(text),
                        }
                    )

            if not blocks:
                return html

            total_tokens = sum(b["tokens"] for b in blocks)

            if total_tokens <= max_tokens:
                return html

            # Select blocks based on priority
            selected_blocks = []
            current_tokens = 0

            if priority == "start":
                # Keep from beginning
                for block in blocks:
                    if current_tokens + block["tokens"] <= max_tokens:
                        selected_blocks.append(block["element"])
                        current_tokens += block["tokens"]
                    else:
                        break

            elif priority == "end":
                # Keep from end
                for block in reversed(blocks):
                    if current_tokens + block["tokens"] <= max_tokens:
                        selected_blocks.insert(0, block["element"])
                        current_tokens += block["tokens"]
                    else:
                        break

            else:  # middle
                # Keep middle sections (most relevant for editing)
                mid_point = len(blocks) // 2

                # Start from middle and expand outward
                indices = []
                left = mid_point
                right = mid_point + 1

                while (
                    left >= 0 or right < len(blocks)
                ) and current_tokens < max_tokens:
                    if (
                        left >= 0
                        and current_tokens + blocks[left]["tokens"] <= max_tokens
                    ):
                        indices.insert(0, left)
                        current_tokens += blocks[left]["tokens"]
                        left -= 1

                    if (
                        right < len(blocks)
                        and current_tokens + blocks[right]["tokens"] <= max_tokens
                    ):
                        indices.append(right)
                        current_tokens += blocks[right]["tokens"]
                        right += 1

                selected_blocks = [blocks[i]["element"] for i in sorted(indices)]

            # Reconstruct HTML with selected blocks
            result_html = "".join(str(element) for element in selected_blocks)

            logger.info(
                f"Smart HTML truncate: {len(blocks)} blocks → {len(selected_blocks)} blocks, {total_tokens} → {current_tokens} tokens"
            )

            return result_html

        except Exception as e:
            logger.error(
                f"Smart HTML truncate failed: {e}, falling back to simple truncate"
            )
            # Fallback to simple truncation
            text = BeautifulSoup(html, "html.parser").get_text()
            truncated_text = cls.truncate_to_token_limit(text, max_tokens)
            return f"<p>{truncated_text}</p>"

    @classmethod
    def optimize_context_for_provider(
        cls,
        provider: str,
        selected_content: str,
        full_content: str = None,
        additional_contexts: List[str] = None,
    ) -> Tuple[str, str, List[str], int]:
        """
        Optimize all context to fit within provider's token limit

        Args:
            provider: AI provider name
            selected_content: User's selected text (highest priority)
            full_content: Full document content (medium priority)
            additional_contexts: List of additional context texts (lowest priority)

        Returns:
            (optimized_selected, optimized_full, optimized_additional, total_tokens)
        """
        # Get token limit for provider
        max_tokens = cls.TOKEN_LIMITS.get(provider, 32000)
        response_reserve = cls.RESPONSE_RESERVE.get(provider, 4000)
        available_tokens = max_tokens - response_reserve

        # Always preserve selected content (highest priority)
        selected_tokens = cls.estimate_tokens(selected_content)

        # If selected content itself is too long, truncate it
        if selected_tokens > available_tokens * 0.7:  # Max 70% for selection
            selected_content = cls.smart_truncate_html(
                selected_content, int(available_tokens * 0.7), priority="middle"
            )
            selected_tokens = cls.estimate_tokens(selected_content)
            logger.warning(f"Selected content truncated to {selected_tokens} tokens")

        remaining_tokens = available_tokens - selected_tokens

        # Allocate tokens for full content
        optimized_full = None
        if full_content and remaining_tokens > 1000:
            full_tokens = min(
                cls.estimate_tokens(full_content),
                int(remaining_tokens * 0.6),  # Max 60% of remaining for full content
            )

            if cls.estimate_tokens(full_content) > full_tokens:
                optimized_full = cls.smart_truncate_html(
                    full_content, full_tokens, priority="middle"
                )
                logger.info(f"Full content truncated to {full_tokens} tokens")
            else:
                optimized_full = full_content

            remaining_tokens -= cls.estimate_tokens(optimized_full)

        # Allocate tokens for additional contexts
        optimized_additional = []
        if additional_contexts and remaining_tokens > 500:
            tokens_per_context = remaining_tokens // len(additional_contexts)

            for context in additional_contexts:
                context_tokens = cls.estimate_tokens(context)

                if context_tokens > tokens_per_context:
                    truncated = cls.smart_truncate_html(
                        context, tokens_per_context, priority="start"
                    )
                    optimized_additional.append(truncated)
                else:
                    optimized_additional.append(context)

        # Calculate total tokens used
        total_tokens = selected_tokens
        if optimized_full:
            total_tokens += cls.estimate_tokens(optimized_full)
        for ctx in optimized_additional:
            total_tokens += cls.estimate_tokens(ctx)

        logger.info(
            f"Context optimized for {provider}: {total_tokens}/{available_tokens} tokens"
        )

        return selected_content, optimized_full, optimized_additional, total_tokens

    @classmethod
    def extract_relevant_excerpt(
        cls, full_text: str, query: str, max_tokens: int = 2000
    ) -> str:
        """
        Extract most relevant excerpt from full text based on query

        Args:
            full_text: Full text content
            query: User's query
            max_tokens: Maximum tokens for excerpt

        Returns:
            Relevant excerpt
        """
        # Simple relevance: find sentences containing query keywords
        query_words = set(query.lower().split())

        sentences = re.split(r"[.!?]+", full_text)

        # Score sentences by keyword overlap
        scored_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_words = set(sentence.lower().split())
            overlap = len(query_words & sentence_words)

            scored_sentences.append(
                {
                    "text": sentence,
                    "score": overlap,
                    "tokens": cls.estimate_tokens(sentence),
                }
            )

        # Sort by relevance
        scored_sentences.sort(key=lambda x: x["score"], reverse=True)

        # Select top sentences within token limit
        selected = []
        current_tokens = 0

        for sent in scored_sentences:
            if current_tokens + sent["tokens"] <= max_tokens:
                selected.append(sent)
                current_tokens += sent["tokens"]
            else:
                break

        # Sort selected sentences by original order
        selected.sort(key=lambda x: full_text.index(x["text"]))

        excerpt = ". ".join(s["text"] for s in selected)

        return excerpt
