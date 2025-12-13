"""
Prompt Builders for Test Generation
Separate prompts for: Academic (Document), Academic (General), Diagnostic, Listening
"""

import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Centralized prompt builder with shared components"""

    @staticmethod
    def _get_question_type_definitions(mcq_type_config: Optional[Dict] = None) -> str:
        """
        Shared section defining all question types and their JSON structure
        Used across all prompts for consistency

        Returns:
            String with question type definitions and JSON examples
        """
        if not mcq_type_config or mcq_type_config.get("distribution_mode") is None:
            mcq_type_config = {"distribution_mode": "auto"}

        distribution_mode = mcq_type_config.get("distribution_mode")

        # Common question type definitions
        common_types = """
**QUESTION TYPES AVAILABLE:**

1. **MCQ (Multiple Choice)** - "question_type": "mcq"
   - Single correct answer with 4 options (A-D)
   - Fields: question_text, options, correct_answer_keys, explanation, points
   - Example:
   ```json
   {
     "question_type": "mcq",
     "question_text": "What is the capital of France?",
     "options": [
       {"option_key": "A", "option_text": "London"},
       {"option_key": "B", "option_text": "Paris"},
       {"option_key": "C", "option_text": "Berlin"},
       {"option_key": "D", "option_text": "Madrid"}
     ],
     "correct_answer_keys": ["B"],
     "explanation": "Paris is the capital and largest city of France.",
     "points": 1
   }
   ```

2. **MCQ Multiple** - "question_type": "mcq_multiple"
   - 2+ correct answers (select all that apply)
   - Fields: question_text, options, correct_answer_keys (array with 2+ items), explanation, points
   - Example:
   ```json
   {
     "question_type": "mcq_multiple",
     "question_text": "Which of these are European capitals?",
     "options": [
       {"option_key": "A", "option_text": "Paris"},
       {"option_key": "B", "option_text": "Tokyo"},
       {"option_key": "C", "option_text": "Berlin"},
       {"option_key": "D", "option_text": "Sydney"}
     ],
     "correct_answer_keys": ["A", "C"],
     "explanation": "Paris (France) and Berlin (Germany) are European capitals.",
     "points": 2
   }
   ```

3. **Matching** - "question_type": "matching"
   - Match left items to right options
   - Fields: question_text, left_items, right_options, correct_matches, explanation, points
   - Example:
   ```json
   {
     "question_type": "matching",
     "question_text": "Match each country to its capital",
     "left_items": [
       {"key": "1", "text": "France"},
       {"key": "2", "text": "Germany"},
       {"key": "3", "text": "Italy"}
     ],
     "right_options": [
       {"key": "A", "text": "Paris"},
       {"key": "B", "text": "Berlin"},
       {"key": "C", "text": "Rome"},
       {"key": "D", "text": "Madrid"},
       {"key": "E", "text": "Athens"}
     ],
     "correct_matches": [
       {"left_key": "1", "right_key": "A"},
       {"left_key": "2", "right_key": "B"},
       {"left_key": "3", "right_key": "C"}
     ],
     "explanation": "Standard European capital city matches.",
     "points": 3
   }
   ```

4. **Completion (IELTS Format)** - "question_type": "completion"
   - Fill blanks in form/note/table
   - Fields: question_text, template, blanks, correct_answers, explanation, points
   - IMPORTANT: Use _____(1)_____, _____(2)_____ format
   - Example:
   ```json
   {
     "question_type": "completion",
     "question_text": "Complete the registration form",
     "template": "Name: _____(1)_____\\nPhone: _____(2)_____\\nEmail: _____(3)_____",
     "blanks": [
       {"key": "1", "position": "Name field"},
       {"key": "2", "position": "Phone field"},
       {"key": "3", "position": "Email field"}
     ],
     "correct_answers": [
       {"blank_key": "1", "answers": ["John Smith", "john smith", "JOHN SMITH"]},
       {"blank_key": "2", "answers": ["0412 555 678", "0412555678"]},
       {"blank_key": "3", "answers": ["john@email.com", "JOHN@EMAIL.COM"]}
     ],
     "explanation": "Standard contact information format.",
     "points": 3
   }
   ```

5. **Sentence Completion** - "question_type": "sentence_completion"
   - Complete sentences with specific words
   - Fields: question_text, template, correct_answer_keys, explanation, points
   - Example:
   ```json
   {
     "question_type": "sentence_completion",
     "question_text": "Complete the sentence",
     "template": "The library opens at _____.",
     "correct_answer_keys": ["8 AM", "8:00 AM", "eight o'clock"],
     "explanation": "Operating hours start at 8 AM.",
     "points": 1
   }
   ```

6. **Short Answer** - "question_type": "short_answer"
   - Brief answer (1-3 words)
   - Fields: question_text, correct_answer_keys (array of acceptable variations), explanation, points
   - Example:
   ```json
   {
     "question_type": "short_answer",
     "question_text": "What is the speaker's occupation?",
     "correct_answer_keys": ["software engineer", "Software Engineer", "engineer"],
     "explanation": "Speaker mentions being a software engineer.",
     "points": 1
   }
   ```

**POINTS SYSTEM:**
- Assign 'points' (1-5) based on difficulty:
  * 1 = very easy (simple recall)
  * 2 = easy (basic understanding)
  * 3 = medium (application/analysis)
  * 4 = hard (synthesis/evaluation)
  * 5 = very hard (complex critical thinking)

**JSON OUTPUT STRUCTURE:**
```json
{
  "questions": [
    {
      "question_type": "mcq",
      "question_text": "...",
      "options": [...],
      "correct_answer_keys": ["A"],
      "explanation": "...",
      "points": 1
    },
    {
      "question_type": "completion",
      "question_text": "...",
      "template": "...",
      "blanks": [...],
      "correct_answers": [...],
      "explanation": "...",
      "points": 3
    }
  ]
}
```
"""

        return common_types

    @staticmethod
    def build_academic_document_prompt(
        title: str,
        topic: str,
        num_questions: int,
        language: str,
        difficulty: str,
        user_query: str,
        document_content: str,
        mcq_type_config: Optional[Dict] = None,
    ) -> str:
        """
        Build prompt for ACADEMIC tests from DOCUMENT/PDF

        Characteristics:
        - Tests knowledge with correct answers
        - Based on provided document
        - Uses 'points' field for scoring
        """

        question_types = PromptBuilder._get_question_type_definitions(mcq_type_config)

        difficulty_map = {
            "easy": "Create EASY questions testing basic understanding and recall of straightforward facts",
            "medium": "Create MEDIUM questions testing comprehension and application of concepts",
            "hard": "Create HARD questions testing deep analysis, synthesis, and critical thinking",
        }
        difficulty_instruction = difficulty_map.get(difficulty, difficulty_map["medium"])

        prompt = f"""You are an expert educational assessment creator specializing in ACADEMIC tests.

**TEST CONFIGURATION:**
- Title: {title}
- Topic: {topic}
- Language: {language}
- Difficulty: {difficulty_instruction}
- Number of Questions: {num_questions} (EXACTLY - no more, no less)

**USER REQUIREMENTS:**
{user_query}

{question_types}

**CRITICAL INSTRUCTIONS:**

1. **OUTPUT FORMAT:**
   - MUST be valid JSON with "questions" array
   - Each question MUST have "question_type" field
   - Properly escape special characters: use \\" for quotes, \\n for newlines, \\\\\\\\ for backslashes

2. **QUESTION COUNT (ABSOLUTE REQUIREMENT):**
   - Generate EXACTLY {num_questions} questions
   - NO DUPLICATES - each question must be unique
   - Count your output before returning

3. **CONTENT SOURCE:**
   - ALL questions, answers, and explanations MUST come from the provided document
   - Reference specific document sections in explanations
   - Do NOT use external knowledge

4. **ANSWER ACCURACY:**
   - All questions MUST have correct answers
   - Explanations MUST explain WHY answers are correct
   - For completion/short_answer: provide multiple acceptable variations

5. **LANGUAGE:**
   - ALL content (questions, options, explanations) in {language}

**DOCUMENT CONTENT:**
---
{document_content}
---

Return ONLY the JSON object, no additional text, no markdown code blocks."""

        return prompt

    @staticmethod
    def build_academic_general_prompt(
        title: str,
        topic: str,
        num_questions: int,
        language: str,
        difficulty: str,
        user_query: str,
        mcq_type_config: Optional[Dict] = None,
    ) -> str:
        """
        Build prompt for ACADEMIC tests from GENERAL KNOWLEDGE (no document)

        Characteristics:
        - Tests knowledge with correct answers
        - Based on general/common knowledge
        - Uses 'points' field for scoring
        """

        question_types = PromptBuilder._get_question_type_definitions(mcq_type_config)

        difficulty_map = {
            "easy": "Create EASY questions testing basic general knowledge",
            "medium": "Create MEDIUM questions testing standard knowledge and understanding",
            "hard": "Create HARD questions testing advanced knowledge and critical thinking",
        }
        difficulty_instruction = difficulty_map.get(difficulty, difficulty_map["medium"])

        prompt = f"""You are an expert educational assessment creator specializing in ACADEMIC tests.

**TEST CONFIGURATION:**
- Title: {title}
- Topic: {topic}
- Language: {language}
- Difficulty: {difficulty_instruction}
- Number of Questions: {num_questions} (EXACTLY - no more, no less)

**USER REQUIREMENTS:**
{user_query}

{question_types}

**CRITICAL INSTRUCTIONS:**

1. **OUTPUT FORMAT:**
   - MUST be valid JSON with "questions" array
   - Each question MUST have "question_type" field
   - Properly escape special characters: use \\" for quotes, \\n for newlines, \\\\\\\\ for backslashes

2. **QUESTION COUNT (ABSOLUTE REQUIREMENT):**
   - Generate EXACTLY {num_questions} questions
   - NO DUPLICATES - each question must be unique
   - Count your output before returning

3. **CONTENT SOURCE:**
   - Use general knowledge about: {topic}
   - Use common/standard information from educational resources
   - Ensure accuracy - use well-established facts

4. **ANSWER ACCURACY:**
   - All questions MUST have correct answers
   - Explanations MUST explain WHY answers are correct
   - For completion/short_answer: provide multiple acceptable variations

5. **LANGUAGE:**
   - ALL content (questions, options, explanations) in {language}

6. **NO DOCUMENT PROVIDED:**
   - You are NOT given a document
   - Generate questions from general knowledge
   - Focus on widely-known information about the topic

Return ONLY the JSON object, no additional text, no markdown code blocks."""

        return prompt

    @staticmethod
    def build_diagnostic_prompt(
        title: str,
        topic: str,
        num_questions: int,
        language: str,
        user_query: str,
        num_options: int = 4,
    ) -> str:
        """
        Build prompt for DIAGNOSTIC/PERSONALITY tests

        Characteristics:
        - NO correct answers - reveals traits/preferences
        - NO 'points' field
        - Includes 'diagnostic_criteria' with result types
        - Options represent different personality traits
        """

        prompt = f"""You are an expert psychologist and personality assessment creator specializing in DIAGNOSTIC tests.

**TEST CONFIGURATION:**
- Title: {title}
- Topic: {topic}
- Language: {language}
- Number of Questions: {num_questions} (EXACTLY - no more, no less)
- Options per Question: {num_options}

**USER REQUIREMENTS:**
{user_query}

**DIAGNOSTIC TEST CHARACTERISTICS:**
- This is a PERSONALITY/DIAGNOSTIC test - NOT a knowledge test
- Questions reveal personality traits, preferences, tendencies, behaviors
- There are NO "correct" answers - all options are equally valid
- Each option represents a different trait or preference

**CRITICAL INSTRUCTIONS:**

1. **OUTPUT FORMAT:**
   - MUST be valid JSON with "questions" array AND "diagnostic_criteria" object
   - Each question uses "question_type": "mcq" (standard multiple choice)
   - DO NOT include "correct_answer_keys" field
   - DO NOT include "points" field
   - Properly escape special characters: use \\" for quotes, \\n for newlines, \\\\\\\\ for backslashes

2. **QUESTION COUNT (ABSOLUTE REQUIREMENT):**
   - Generate EXACTLY {num_questions} questions
   - NO DUPLICATES - each question must be unique

3. **QUESTION DESIGN:**
   - Focus on behaviors, preferences, reactions, tendencies
   - Options should represent distinct personality traits
   - Avoid judgmental language - all options are valid choices
   - Example topics: work style, social preferences, decision-making, stress handling

4. **EXPLANATION FIELD:**
   - Explain what each option reveals about personality
   - Example: "Option A suggests analytical thinking, B suggests creative approach, C suggests collaborative style, D suggests independent working"

5. **DIAGNOSTIC CRITERIA (REQUIRED):**
   - Define 3-5 result types (personality types/categories)
   - Include mapping rules for interpreting answer patterns
   - Example: "Mostly A answers → Analytical Type, Mostly B answers → Creative Type"

6. **LANGUAGE:**
   - ALL content (questions, options, explanations) in {language}

**JSON OUTPUT STRUCTURE:**
```json
{
  "questions": [
    {
      "question_type": "mcq",
      "question_text": "When facing a challenging problem at work, you prefer to:",
      "options": [
        {"option_key": "A", "option_text": "Analyze data and create detailed plans"},
        {"option_key": "B", "option_text": "Brainstorm creative solutions"},
        {"option_key": "C", "option_text": "Discuss with team members"},
        {"option_key": "D", "option_text": "Take immediate action and adjust as needed"}
      ],
      "explanation": "A indicates analytical thinking, B shows creativity, C suggests collaboration, D demonstrates action-oriented approach."
    }
  ],
  "diagnostic_criteria": {
    "result_types": [
      {
        "type_id": "analytical",
        "title": "Analytical Thinker",
        "description": "You approach problems systematically with data and logic",
        "traits": ["detail-oriented", "logical", "methodical"]
      },
      {
        "type_id": "creative",
        "title": "Creative Problem Solver",
        "description": "You value innovation and out-of-the-box thinking",
        "traits": ["imaginative", "flexible", "innovative"]
      }
    ],
    "mapping_rules": "Count answer patterns: Mostly A → Analytical, Mostly B → Creative, Mostly C → Collaborative, Mostly D → Action-oriented. Mixed patterns indicate balanced personality."
  }
}
```

Return ONLY the JSON object, no additional text, no markdown code blocks."""

        return prompt


# Singleton instance for easy import
prompt_builder = PromptBuilder()
