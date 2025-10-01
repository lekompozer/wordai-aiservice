"""
Prompt Engineering Service
Service for building AI prompts for content editing operations
"""

from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class PromptEngineeringService:
    """Service for building AI prompts for content editing operations"""

    # System prompts for each operation type
    SYSTEM_PROMPTS = {
        "summarize": """You are a professional content summarizer. Create a concise summary of the provided content.

Rules:
1. Return ONLY valid HTML using <p>, <strong>, <ul>, <li> tags
2. Keep summary between 50-150 words unless specified otherwise
3. Preserve key facts, figures, and main arguments
4. Use clear, professional language
5. Do NOT include <script>, <style>, or any unsafe tags
6. Do NOT use inline styles

Return summary as clean HTML.""",
        "change_tone": """You are a professional writing assistant. Rewrite the content to match the requested tone.

Rules:
1. Preserve the core message and facts
2. Return ONLY valid HTML matching the original structure
3. Adjust vocabulary, formality, and style to match the requested tone
4. Keep the same HTML tags as input
5. Do NOT add or remove factual information
6. Do NOT include unsafe HTML

Return rewritten HTML.""",
        "fix_grammar": """You are an expert grammar and spelling checker. Fix all errors in the content.

Rules:
1. Preserve the original HTML structure exactly
2. Only fix language errors, do not change meaning
3. Return ONLY valid HTML
4. Do NOT alter formatting or add new elements
5. Keep the same tone and style
6. Fix spelling, grammar, and punctuation errors

Return corrected HTML.""",
        "create_table": """You are a data formatting assistant. Convert the text into a well-structured HTML table.

Rules:
1. Return ONLY a complete <table> element with <thead> and <tbody>
2. Auto-detect columns from the input data
3. Ensure all rows have the same number of columns
4. Use <th> for headers, <td> for data cells
5. Do NOT include styling or classes
6. Do NOT include unsafe HTML

Return table HTML.""",
        "transform_format": """You are a content formatting specialist. Transform the content into the requested format.

Rules:
1. Preserve all content and meaning
2. Return ONLY valid HTML in the requested format
3. Maintain logical order and hierarchy
4. Do NOT add or remove information
5. Use appropriate HTML tags for the target format

Return formatted HTML.""",
        "continue_writing": """You are a creative writing assistant. Continue writing naturally from where the user left off.

Rules:
1. Match the tone and style of the existing content
2. Return ONLY valid HTML matching the surrounding structure
3. Write 2-3 paragraphs unless specified otherwise
4. Maintain coherence and logical flow
5. Use <p> tags for paragraphs
6. Do NOT include unsafe HTML

Return continuation HTML.""",
        "expand_content": """You are a content expansion specialist. Expand the content with additional details.

Rules:
1. Add relevant details, examples, and explanations
2. Maintain the original meaning and direction
3. Return ONLY valid HTML
4. Use additional context if provided
5. Cite sources when using information from context files
6. Keep the same HTML structure

Return expanded HTML.""",
        "simplify": """You are a content simplification expert. Rewrite to be simpler and easier to understand.

Rules:
1. Use simpler vocabulary and shorter sentences
2. Preserve all key information
3. Return ONLY valid HTML matching original structure
4. Maintain professional quality
5. Do NOT oversimplify technical terms inappropriately

Return simplified HTML.""",
        "translate": """You are a professional translator. Translate the content to the target language.

Rules:
1. Preserve HTML structure exactly
2. Translate all text content accurately
3. Maintain tone and style in target language
4. Do NOT translate HTML tags or attributes
5. Return ONLY valid HTML

Return translated HTML.""",
        "create_structure": """You are a document structure specialist. Create the requested document structure.

Rules:
1. Generate well-organized HTML structure
2. Use appropriate semantic HTML tags
3. Include placeholder content that matches the request
4. Use <div>, <section>, or table layouts as appropriate
5. Return ONLY valid HTML

Return structured HTML.""",
        "general_edit": """You are a versatile content editing assistant. Perform the user's requested edit.

Rules:
1. Follow the user's instructions carefully
2. Preserve HTML structure where possible
3. Return ONLY valid HTML
4. Maintain professional quality
5. Do NOT include unsafe HTML

Return edited HTML.""",
        "custom": """You are a helpful AI assistant. Perform the requested task on the content.

Rules:
1. Follow the user's instructions carefully
2. Return ONLY valid HTML
3. Maintain content quality
4. Do NOT include unsafe HTML
5. Preserve original structure when appropriate

Return result as HTML.""",
    }

    @classmethod
    def build_prompt(
        cls,
        operation_type: str,
        user_query: str,
        selected_html: str,
        selected_text: str,
        parameters: Optional[Dict] = None,
        additional_context: Optional[List[Dict]] = None,
        current_file_name: Optional[str] = None,
    ) -> str:
        """
        Build complete prompt for AI provider

        Args:
            operation_type: Type of operation
            user_query: User's natural language request
            selected_html: Selected HTML content
            selected_text: Plain text version
            parameters: Optional operation parameters
            additional_context: Additional context files
            current_file_name: Name of current file

        Returns:
            Complete prompt string
        """
        # Get base system prompt
        system_prompt = cls.SYSTEM_PROMPTS.get(
            operation_type, cls.SYSTEM_PROMPTS["general_edit"]
        )

        # Build prompt components
        prompt_parts = [system_prompt]

        # Add current file context
        if current_file_name:
            prompt_parts.append(f"\nCurrent file: {current_file_name}")

        # Add parameters
        if parameters:
            param_text = cls._format_parameters(parameters)
            if param_text:
                prompt_parts.append(f"\nParameters: {param_text}")

        # Add additional context
        if additional_context and len(additional_context) > 0:
            context_text = cls._format_additional_context(additional_context)
            prompt_parts.append(f"\nAdditional Context:\n{context_text}")

        # Add user query
        prompt_parts.append(f"\n=== USER REQUEST ===\n{user_query}")

        # Add selected content
        prompt_parts.append(f"\n=== INPUT CONTENT ===")

        # Prefer HTML if available, otherwise use text
        if selected_html and selected_html.strip():
            prompt_parts.append(f"HTML:\n{selected_html}")
        else:
            prompt_parts.append(f"Text:\n{selected_text}")

        # Final instruction
        prompt_parts.append("\n=== OUTPUT ===")
        prompt_parts.append(
            "Generate the result as clean HTML (no explanation, just the HTML):"
        )

        return "\n".join(prompt_parts)

    @staticmethod
    def _format_parameters(parameters: Dict) -> str:
        """Format parameters for prompt"""
        param_list = []

        if parameters.get("tone"):
            param_list.append(f"Tone: {parameters['tone']}")
        if parameters.get("language"):
            lang_map = {"vi": "Vietnamese", "en": "English", "auto": "auto-detect"}
            param_list.append(
                f"Language: {lang_map.get(parameters['language'], parameters['language'])}"
            )
        if parameters.get("outputFormat"):
            param_list.append(f"Output Format: {parameters['outputFormat']}")
        if parameters.get("maxLength"):
            param_list.append(f"Max Length: {parameters['maxLength']} words")
        if parameters.get("tableColumns"):
            param_list.append(f"Table Columns: {', '.join(parameters['tableColumns'])}")

        return ", ".join(param_list)

    @staticmethod
    def _format_additional_context(context_list: List[Dict]) -> str:
        """Format additional context files for prompt"""
        context_parts = []

        for i, ctx in enumerate(context_list, 1):
            file_name = ctx.get("fileName", "Unknown")
            start_line = ctx.get("startLine", "?")
            end_line = ctx.get("endLine", "?")
            content = ctx.get("content", "")

            # Truncate very long context
            if len(content) > 1000:
                content = content[:1000] + "...(truncated)"

            context_parts.append(
                f"Context {i}: {file_name} (Lines {start_line}-{end_line})\n{content}"
            )

        return "\n\n".join(context_parts)

    @classmethod
    def extract_html_from_response(cls, ai_response: str) -> str:
        """
        Extract HTML from AI response
        AI might return: "Here's the summary:\n\n<p>...</p>"
        We need to extract just the HTML part
        """
        import re

        # Remove common prefixes
        response = ai_response.strip()

        # Remove markdown code blocks if present
        if response.startswith("```html"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]

        response = response.strip()

        # Try to find HTML tags
        html_pattern = r"(<[^>]+>.*?</[^>]+>)"
        matches = re.findall(html_pattern, response, re.DOTALL)

        if matches:
            # Check if we have complete HTML blocks
            html_content = "".join(matches)

            # If it's most of the response, use it
            if len(html_content) > len(response) * 0.5:
                return html_content

        # Check if response already looks like HTML
        if response.startswith("<") and ">" in response:
            return response

        # If no HTML found, wrap in <p> tag
        # But first clean up any explanation text
        lines = response.split("\n")
        content_lines = []

        for line in lines:
            line = line.strip()
            # Skip lines that look like explanations
            if line and not line.startswith(("Here", "The", "I ", "This", "Note:")):
                content_lines.append(line)

        if content_lines:
            return "<p>" + "</p><p>".join(content_lines) + "</p>"

        return f"<p>{response}</p>"
