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
   - Fields: question_text, options, correct_answers (array of option keys), explanation, points
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
     "correct_answers": ["B"],
     "explanation": "Paris is the capital and largest city of France.",
     "points": 1
   }
   ```

2. **MCQ Multiple** - "question_type": "mcq_multiple"
   - 2+ correct answers (select all that apply)
   - Fields: question_text, options, correct_answers (array with 2+ option keys), explanation, points
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
     "correct_answers": ["A", "C"],
     "explanation": "Paris (France) and Berlin (Germany) are European capitals.",
     "points": 2
   }
   ```

3. **Matching** - "question_type": "matching"
   - Match left items to right options
   - Fields: question_text, left_items, right_options, correct_answers (array of match pairs), explanation, points
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
     "correct_answers": [
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
   - Fields: question_text, template, correct_answers (array of acceptable text variations), explanation, points
   - Example:
   ```json
   {
     "question_type": "sentence_completion",
     "question_text": "Complete the sentence",
     "template": "The library opens at _____.",
     "correct_answers": ["8 AM", "8:00 AM", "eight o'clock"],
     "explanation": "Operating hours start at 8 AM.",
     "points": 1
   }
   ```

6. **Short Answer** - "question_type": "short_answer"
   - Brief answer (1-3 words)
   - Fields: question_text, correct_answers (array of acceptable text variations), explanation, points
   - Example:
   ```json
   {
     "question_type": "short_answer",
     "question_text": "What is the speaker's occupation?",
     "correct_answers": ["software engineer", "Software Engineer", "engineer"],
     "explanation": "Speaker mentions being a software engineer.",
     "points": 1
   }
   ```

7. **True/False Multiple** - "question_type": "true_false_multiple"
   - Multiple statements, each evaluated as True or False
   - Fields: question_text, statements, scoring_mode, explanation, points
   - Scoring modes: "partial" (proportional) or "all_or_nothing" (must get all correct)
   - PERFECT FOR: Vietnamese academic exams (Math/Physics/Chemistry/Biology)
   - Example:
   ```json
   {
     "question_type": "true_false_multiple",
     "question_text": "Câu 1: Cho hàm số f(x) = x² - 4x + 3. Xét tính đúng sai của các khẳng định sau:",
     "statements": [
       {
         "key": "a",
         "text": "Hàm số có đồ thị là parabol với đỉnh I(2, -1)",
         "correct_value": true
       },
       {
         "key": "b",
         "text": "Hàm số nghịch biến trên khoảng (-∞, 2)",
         "correct_value": false
       },
       {
         "key": "c",
         "text": "Đồ thị cắt trục hoành tại 2 điểm phân biệt",
         "correct_value": true
       },
       {
         "key": "d",
         "text": "Giá trị nhỏ nhất của hàm số là -2",
         "correct_value": false
       }
     ],
     "scoring_mode": "partial",
     "explanation": "a) Đúng. Đỉnh I có x = -b/2a = 4/2 = 2, y = f(2) = 4 - 8 + 3 = -1\\nb) Sai. Với a = 1 > 0, hàm đồng biến khi x > 2\\nc) Đúng. Δ = 16 - 12 = 4 > 0 nên có 2 nghiệm phân biệt\\nd) Sai. Giá trị nhỏ nhất là y_đỉnh = -1",
     "points": 4
   }
   ```
   - **GUIDELINES FOR TRUE/FALSE MULTIPLE:**
     * Use "partial" scoring (recommended): student gets (correct_count/total) × points
     * Use "all_or_nothing" for challenging exams: must get all statements correct
     * Create 2-5 statements per question (usually 4 for Vietnamese exams)
     * Each statement must be clearly True or False (no ambiguity)
     * Mix true and false statements (don't make all true or all false)
     * Write detailed explanation for each statement in the explanation field

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
      "correct_answers": ["A"],
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
    },
    {
      "question_type": "true_false_multiple",
      "question_text": "...",
      "statements": [
        {"key": "a", "text": "...", "correct_value": true},
        {"key": "b", "text": "...", "correct_value": false}
      ],
      "scoring_mode": "partial",
      "explanation": "...",
      "points": 4
    }
  ]
}
```

⚠️ **CRITICAL: Field names by question type**
- MCQ/MCQ Multiple: use "correct_answers" field (array of option keys)
- Matching: use "correct_answers" field (array of match objects)
- Completion: use "correct_answers" field (array of blank objects)
- Sentence Completion: use "correct_answers" field (array of acceptable strings)
- Short Answer: use "correct_answers" field (array of acceptable strings)
- **True/False Multiple**: use "statements" field (array with correct_value) + "scoring_mode"

DO NOT use: correct_answer_keys, correct_matches, or any other field name!
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
        difficulty_instruction = difficulty_map.get(
            difficulty, difficulty_map["medium"]
        )

        # Convert language code to full name for clarity
        language_full = (
            "English"
            if language.lower() in ["en", "english"]
            else (
                "Vietnamese"
                if language.lower() in ["vi", "vn", "vietnamese"]
                else language
            )
        )

        prompt = f"""# ROLE
You are an expert educational assessment creator specializing in ACADEMIC tests.

# STEP 1: ANALYZE USER REQUEST
Read and understand what the user wants:
---
{user_query}
---

The above describes the test structure, topics, and requirements. Use this to understand WHAT content to create, but IGNORE any numbers mentioned.

# STEP 2: EXECUTE GENERATION WITH STRICT CONFIGURATION

⚠️ CRITICAL: Follow ONLY these configuration values, NOT any numbers from Step 1:

**TEST CONFIGURATION:**
- Title: {title}
- Topic: {topic}
- Language: {language_full}
- Difficulty: {difficulty_instruction}
- Number of Questions: {num_questions} (ABSOLUTE - ignore any other count)

**MCQ DISTRIBUTION MODE: {mcq_type_config.get("distribution_mode", "auto").upper() if mcq_type_config else "AUTO"}**

Choose how to distribute question types based on this mode:

🔹 **AUTO MODE** (Default - AI decides):
   - You decide the optimal mix of question types based on content and document structure
   - Choose from ALL available types: mcq, mcq_multiple, matching, completion, sentence_completion, short_answer, true_false_multiple
   - Balance variety and appropriateness for the topic
   - Prioritize question types that best fit the content (e.g., true_false_multiple for Vietnamese academic exams with Đúng/Sai statements)
   - Example distributions:
     * General topics: 60% mcq, 20% completion, 10% matching, 10% short_answer
     * Vietnamese academic exams: 50% mcq, 30% true_false_multiple, 20% other types

🔹 **TRADITIONAL MODE** (90% single + 10% multiple):
   - 90% of MCQ questions should be "mcq" (single correct answer)
   - 10% of MCQ questions should be "mcq_multiple" (2+ correct answers)
   - Other question types (completion, matching, etc.) allowed as specified in Step 1
   - Example: If 30 total questions and 20 are MCQ → 18 single mcq + 2 mcq_multiple

🔹 **USER_MANUAL MODE** (Follow Step 1 exactly):
   - Follow EXACTLY the breakdown specified in Step 1
   - If Step 1 says "10 single MCQ, 5 multiple MCQ" → generate exactly that
   - If Step 1 says "Part A: 5 mcq, Part B: 3 completion" → follow precisely
   - No deviation from user's explicit instructions

**EXECUTION RULES:**
- Generate EXACTLY {num_questions} questions TOTAL
- Your final "questions" array length MUST be {num_questions}
- All content (questions, options, explanations) in {language_full}

# STEP 3: QUESTION TYPES & INSTRUCTIONS

{question_types}

**CRITICAL INSTRUCTIONS:**

1. **OUTPUT FORMAT:**
   - MUST be valid JSON with "questions" array
   - Each question MUST have "question_type" field
   - Properly escape special characters in JSON strings

2. **MATHEMATICAL NOTATION (for Math/Physics/Chemistry/Biology topics):**
   - Use KaTeX/LaTeX syntax for ALL mathematical expressions, formulas, equations
   - Apply to ALL fields: question_text, option_text, statement text, explanation, template
   - Inline math: wrap in single $, e.g., "Cho hàm số $f(x) = x^2 - 4x + 3$"
   - Display math: wrap in double $$, e.g., "$$\\int_{{1}}^{{2}} (2x + 1) dx$$"
   - Common patterns:
     * Powers: $x^2$, $2^n$, $x^{{-1}}$
     * Fractions: $\\frac{{a}}{{b}}$, $\\frac{{-b \\pm \\sqrt{{b^2-4ac}}}}{{2a}}$
     * Roots: $\\sqrt{{x}}$, $\\sqrt[3]{{x}}$
     * Greek letters: $\\alpha$, $\\beta$, $\\Delta$, $\\pi$, $\\theta$
     * Integrals: $\\int$, $\\int_{{a}}^{{b}}$, $\\oint$
     * Limits: $\\lim_{{x \\to 0}}$, $\\lim_{{n \\to \\infty}}$
     * Trigonometry: $\\sin x$, $\\cos x$, $\\tan x$
     * Vectors: $\\vec{{v}}$, $\\overrightarrow{{AB}}$
     * Inequalities: $\\leq$, $\\geq$, $\\neq$, $<$, $>$
     * Sets: $\\in$, $\\subset$, $\\cup$, $\\cap$, $\\mathbb{{R}}$, $\\mathbb{{Z}}$
     * Infinity: $\\infty$, $+\\infty$, $-\\infty$
   - Example: "Giải phương trình $x^2 - 5x + 6 = 0$ với $\\Delta = b^2 - 4ac$"
   - Benefits: Beautiful rendering on frontend, professional math display

3. **QUESTION COUNT (ABSOLUTE REQUIREMENT):**
   - Generate EXACTLY {num_questions} questions TOTAL in the "questions" array
   - The "questions" array should contain {num_questions} items TOTAL, regardless of how user describes parts
   - Count the length of your "questions" array - it MUST equal {num_questions}
   - NO DUPLICATES - each question must be unique
   - STOP IMMEDIATELY when "questions" array has {num_questions} items
   - Close the JSON immediately: no extra questions, no continuation

4. **CONTENT SOURCE:**
   - ALL questions, answers, and explanations MUST come from the provided document
   - Reference specific document sections in explanations
   - Do NOT use external knowledge

5. **ANSWER ACCURACY:**
   - All questions MUST have correct answers
   - Explanations MUST explain WHY answers are correct
   - For completion/short_answer: provide multiple acceptable variations

# STEP 4: DOCUMENT CONTENT

Use ONLY information from this document:
---
{document_content}
---

# STEP 5: GENERATE OUTPUT

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
        difficulty_instruction = difficulty_map.get(
            difficulty, difficulty_map["medium"]
        )

        # Convert language code to full name for clarity
        language_full = (
            "English"
            if language.lower() in ["en", "english"]
            else (
                "Vietnamese"
                if language.lower() in ["vi", "vn", "vietnamese"]
                else language
            )
        )

        prompt = f"""# ROLE
You are an expert educational assessment creator specializing in ACADEMIC tests.

# STEP 1: ANALYZE USER REQUEST
Read and understand what the user wants:
---
{user_query}
---

The above describes the test structure, topics, and requirements. Use this to understand WHAT content to create, but IGNORE any numbers mentioned.

# STEP 2: EXECUTE GENERATION WITH STRICT CONFIGURATION

⚠️ CRITICAL: Follow ONLY these configuration values, NOT any numbers from Step 1:

**TEST CONFIGURATION:**
- Title: {title}
- Topic: {topic}
- Language: {language_full}
- Difficulty: {difficulty_instruction}
- Number of Questions: {num_questions} (ABSOLUTE - ignore any other count)

**MCQ DISTRIBUTION MODE: {mcq_type_config.get("distribution_mode", "auto").upper() if mcq_type_config else "AUTO"}**

Choose how to distribute question types based on this mode:

🔹 **AUTO MODE** (Default - AI decides):
   - You decide the optimal mix of question types based on content and structure
   - Choose from ALL available types: mcq, mcq_multiple, matching, completion, sentence_completion, short_answer, true_false_multiple
   - Balance variety and appropriateness for the topic
   - Prioritize question types that best fit the content (e.g., true_false_multiple for Vietnamese academic exams with Đúng/Sai statements)
   - Example distributions:
     * General topics: 60% mcq, 20% completion, 10% matching, 10% short_answer
     * Vietnamese academic exams: 50% mcq, 30% true_false_multiple, 20% other types

🔹 **TRADITIONAL MODE** (90% single + 10% multiple):
   - 90% of MCQ questions should be "mcq" (single correct answer)
   - 10% of MCQ questions should be "mcq_multiple" (2+ correct answers)
   - Other question types (completion, matching, etc.) allowed as specified in Step 1
   - Example: If 30 total questions and 20 are MCQ → 18 single mcq + 2 mcq_multiple

🔹 **USER_MANUAL MODE** (Follow Step 1 exactly):
   - Follow EXACTLY the breakdown specified in Step 1
   - If Step 1 says "10 single MCQ, 5 multiple MCQ" → generate exactly that
   - If Step 1 says "Part A: 5 mcq, Part B: 3 completion" → follow precisely
   - No deviation from user's explicit instructions

**EXECUTION RULES:**
- Generate EXACTLY {num_questions} questions TOTAL
- Your final "questions" array length MUST be {num_questions}
- All content (questions, options, explanations) in {language_full}

# STEP 3: QUESTION TYPES & INSTRUCTIONS

{question_types}

**CRITICAL INSTRUCTIONS:**

1. **OUTPUT FORMAT:**
   - MUST be valid JSON with "questions" array
   - Each question MUST have "question_type" field
   - Properly escape special characters in JSON strings

2. **MATHEMATICAL NOTATION (for Math/Physics/Chemistry/Biology topics):**
   - Use KaTeX/LaTeX syntax for ALL mathematical expressions, formulas, equations
   - Apply to ALL fields: question_text, option_text, statement text, explanation, template
   - Inline math: wrap in single $, e.g., "Cho hàm số $f(x) = x^2 - 4x + 3$"
   - Display math: wrap in double $$, e.g., "$$\\int_{{1}}^{{2}} (2x + 1) dx$$"
   - Common patterns:
     * Powers: $x^2$, $2^n$, $x^{{-1}}$
     * Fractions: $\\frac{{a}}{{b}}$, $\\frac{{-b \\pm \\sqrt{{b^2-4ac}}}}{{2a}}$
     * Roots: $\\sqrt{{x}}$, $\\sqrt[3]{{x}}$
     * Greek letters: $\\alpha$, $\\beta$, $\\Delta$, $\\pi$, $\\theta$
     * Integrals: $\\int$, $\\int_{{a}}^{{b}}$, $\\oint$
     * Limits: $\\lim_{{x \\to 0}}$, $\\lim_{{n \\to \\infty}}$
     * Trigonometry: $\\sin x$, $\\cos x$, $\\tan x$
     * Vectors: $\\vec{{v}}$, $\\overrightarrow{{AB}}$
     * Inequalities: $\\leq$, $\\geq$, $\\neq$, $<$, $>$
     * Sets: $\\in$, $\\subset$, $\\cup$, $\\cap$, $\\mathbb{{R}}$, $\\mathbb{{Z}}$
   - Example: "Giải phương trình $x^2 - 5x + 6 = 0$ với $\\Delta = b^2 - 4ac$"
   - Benefits: Beautiful rendering on frontend, professional math display

3. **QUESTION COUNT (ABSOLUTE REQUIREMENT):**
   - Generate EXACTLY {num_questions} questions TOTAL in the "questions" array
   - The "questions" array should contain {num_questions} items TOTAL, regardless of how user describes parts
   - Count the length of your "questions" array - it MUST equal {num_questions}
   - NO DUPLICATES - each question must be unique
   - STOP IMMEDIATELY when "questions" array has {num_questions} items
   - Close the JSON immediately: no extra questions, no continuation

4. **CONTENT SOURCE:**
   - Use general knowledge about: {topic}
   - Use common/standard information from educational resources
   - Ensure accuracy - use well-established facts
   - You are NOT given a document - generate from general knowledge

5. **ANSWER ACCURACY:**
   - All questions MUST have correct answers
   - Explanations MUST explain WHY answers are correct
   - For completion/short_answer: provide multiple acceptable variations

# STEP 4: GENERATE OUTPUT

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

        # Convert language code to full name for clarity
        language_full = (
            "English"
            if language.lower() in ["en", "english"]
            else (
                "Vietnamese"
                if language.lower() in ["vi", "vn", "vietnamese"]
                else language
            )
        )

        prompt = f"""# ROLE
You are an expert psychologist and personality assessment creator specializing in DIAGNOSTIC tests.

# STEP 1: ANALYZE USER REQUEST
Read and understand what the user wants:
---
{user_query}
---

The above describes the test structure and requirements. Use this to understand WHAT content to create, but IGNORE any numbers mentioned.

# STEP 2: EXECUTE GENERATION WITH STRICT CONFIGURATION

⚠️ CRITICAL: Follow ONLY these configuration values, NOT any numbers from Step 1:

**TEST CONFIGURATION:**
- Title: {title}
- Topic: {topic}
- Language: {language_full}
- Number of Questions: {num_questions} (ABSOLUTE - ignore any other count)
- Options per Question: {num_options}

**EXECUTION RULES:**
- Generate EXACTLY {num_questions} questions TOTAL
- If Step 1 mentions "PART 1: 4 questions, PART 2: 8 questions", treat as distribution suggestions only
- Your final "questions" array length MUST be {num_questions}
- All content (questions, options, explanations) in {language_full}

**DIAGNOSTIC TEST CHARACTERISTICS:**
- This is a PERSONALITY/DIAGNOSTIC test - NOT a knowledge test
- Questions reveal personality traits, preferences, tendencies, behaviors
- There are NO "correct" answers - all options are equally valid
- Each option represents a different trait or preference

# STEP 3: CRITICAL INSTRUCTIONS

1. **OUTPUT FORMAT:**
   - MUST be valid JSON with "questions" array AND "diagnostic_criteria" object
   - Each question uses "question_type": "mcq" (standard multiple choice)
   - DO NOT include "correct_answer_keys" field
   - DO NOT include "points" field
   - Properly escape special characters in JSON strings

2. **MATHEMATICAL NOTATION (for Math/Science topics - if applicable):**
   - Use KaTeX/LaTeX syntax for ALL mathematical expressions, formulas, equations
   - Apply to ALL fields: question_text, option_text, explanation
   - Inline math: wrap in single $, e.g., "Your learning style for $f(x) = x^2$"
   - Common patterns: $x^2$, $\\frac{{a}}{{b}}$, $\\sqrt{{x}}$, $\\Delta$, $\\pi$
   - Example: "When solving $x^2 - 5x + 6 = 0$, you prefer..."
   - Benefits: Beautiful rendering on frontend, professional math display

3. **QUESTION COUNT (ABSOLUTE REQUIREMENT):**
   - Generate EXACTLY {num_questions} questions TOTAL in the "questions" array
   - The "questions" array should contain {num_questions} items TOTAL, regardless of how user describes parts
   - Count the length of your "questions" array - it MUST equal {num_questions}
   - NO DUPLICATES - each question must be unique
   - STOP IMMEDIATELY when "questions" array has {num_questions} items
   - Close the JSON immediately: no extra questions, no continuation

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

**JSON OUTPUT STRUCTURE:**
Example:
{{
  "questions": [
    {{
      "question_type": "mcq",
      "question_text": "When facing a challenging problem at work, you prefer to:",
      "options": [
        {{"option_key": "A", "option_text": "Analyze data and create detailed plans"}},
        {{"option_key": "B", "option_text": "Brainstorm creative solutions"}},
        {{"option_key": "C", "option_text": "Discuss with team members"}},
        {{"option_key": "D", "option_text": "Take immediate action and adjust as needed"}}
      ],
      "explanation": "A indicates analytical thinking, B shows creativity, C suggests collaboration, D demonstrates action-oriented approach."
    }}
  ],
  "diagnostic_criteria": {{
    "result_types": [
      {{
        "type_id": "analytical",
        "title": "Analytical Thinker",
        "description": "You approach problems systematically with data and logic",
        "traits": ["detail-oriented", "logical", "methodical"]
      }},
      {{
        "type_id": "creative",
        "title": "Creative Problem Solver",
        "description": "You value innovation and out-of-the-box thinking",
        "traits": ["imaginative", "flexible", "innovative"]
      }}
    ],
    "mapping_rules": "Count answer patterns: Mostly A → Analytical, Mostly B → Creative, Mostly C → Collaborative, Mostly D → Action-oriented. Mixed patterns indicate balanced personality."
  }}
}}

# STEP 4: GENERATE OUTPUT

Return ONLY the JSON object, no additional text, no markdown code blocks."""

        return prompt


# Singleton instance for easy import
prompt_builder = PromptBuilder()
