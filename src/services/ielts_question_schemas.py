"""
IELTS Question Type Schemas and Prompts
Defines JSON schemas and generation prompts for 6 IELTS listening question types
"""

from typing import Dict, Any


def get_ielts_question_schema() -> Dict[str, Any]:
    """
    Get JSON schema for IELTS questions supporting 6 question types

    Supports:
    - mcq: Multiple Choice
    - matching: Match items
    - map_labeling: Label diagrams
    - completion: Fill in blanks
    - sentence_completion: Complete sentences
    - short_answer: Short answer questions
    """

    return {
        "type": "object",
        "properties": {
            "audio_sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "section_number": {"type": "integer"},
                        "section_title": {"type": "string"},
                        "script": {
                            "type": "object",
                            "properties": {
                                "speaker_roles": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "lines": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "speaker": {"type": "integer"},
                                            "text": {"type": "string"},
                                        },
                                        "required": ["speaker", "text"],
                                    },
                                },
                            },
                            "required": ["speaker_roles", "lines"],
                        },
                        "questions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    # Common fields
                                    "question_type": {
                                        "type": "string",
                                        "enum": [
                                            "mcq",
                                            "matching",
                                            "map_labeling",
                                            "completion",
                                            "sentence_completion",
                                            "short_answer",
                                        ],
                                    },
                                    "question_text": {"type": "string"},
                                    "instruction": {"type": "string"},
                                    "timestamp_hint": {"type": "string"},
                                    "explanation": {"type": "string"},
                                    # MCQ fields
                                    "options": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "option_key": {"type": "string"},
                                                "option_text": {"type": "string"},
                                            },
                                        },
                                    },
                                    "correct_answers": {
                                        "type": "array",
                                        "description": "Unified field for correct answers (primary)",
                                    },
                                    "correct_answer_keys": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Deprecated: use correct_answers instead",
                                    },
                                    # Matching fields
                                    "left_items": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "key": {"type": "string"},
                                                "text": {"type": "string"},
                                            },
                                        },
                                    },
                                    "right_options": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "key": {"type": "string"},
                                                "text": {"type": "string"},
                                            },
                                        },
                                    },
                                    "correct_matches": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "left_key": {"type": "string"},
                                                "right_key": {"type": "string"},
                                            },
                                        },
                                        "description": "Deprecated: use correct_answers instead",
                                    },
                                    # Completion fields
                                    "template": {"type": "string"},
                                    "blanks": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "key": {"type": "string"},
                                                "position": {"type": "string"},
                                                "word_limit": {"type": "integer"},
                                            },
                                        },
                                    },
                                    "correct_answers": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "blank_key": {"type": "string"},
                                                "answers": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                            },
                                        },
                                    },
                                    # Sentence completion fields
                                    "sentences": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "key": {"type": "string"},
                                                "template": {"type": "string"},
                                                "word_limit": {"type": "integer"},
                                                "correct_answers": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                            },
                                        },
                                    },
                                    # Short answer fields
                                    "questions": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "key": {"type": "string"},
                                                "text": {"type": "string"},
                                                "word_limit": {"type": "integer"},
                                                "correct_answers": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                            },
                                        },
                                    },
                                },
                                "required": ["question_type", "question_text"],
                            },
                        },
                    },
                    "required": [
                        "section_number",
                        "section_title",
                        "script",
                        "questions",
                    ],
                },
            }
        },
        "required": ["audio_sections"],
    }


def get_ielts_prompt(
    language: str,
    topic: str,
    difficulty: str,
    num_questions: int,
    num_audio_sections: int,
    num_speakers: int,
    user_query: str,
) -> str:
    """Build IELTS-style listening test prompt with 5 question types"""

    difficulty_map = {
        "easy": "EASY: Simple vocabulary, clear pronunciation, slow pace. Use basic sentence structures.",
        "medium": "MEDIUM: Moderate vocabulary, natural pace, some idioms. Use varied sentence structures.",
        "hard": "HARD: Advanced vocabulary, fast pace, complex structures, academic content.",
    }
    difficulty_desc = difficulty_map.get(difficulty, difficulty_map["medium"])

    speaker_instruction = ""
    if num_speakers == 1:
        speaker_instruction = "Generate a MONOLOGUE (single speaker). Suitable for: announcements, descriptions, lectures. Specify gender in speaker_roles (e.g., 'Male Announcer' or 'Female Professor')."
    elif num_speakers == 2:
        speaker_instruction = """Generate a DIALOGUE (two speakers). Alternate naturally.

**CRITICAL GENDER REQUIREMENTS FOR EVERY SECTION:**
- **EVERY section MUST have ONE MALE and ONE FEMALE speaker** (to ensure distinct voices)
- Include roles WITH gender prefix: 'Male [Role]' and 'Female [Role]'
- Examples: 'Male Customer/Female Agent', 'Female Student/Male Teacher', 'Male Applicant/Female Manager'
- **DO NOT create sections with same-gender pairs** (e.g., Male/Male or Female/Female will sound identical!)
- Vary the gender order across sections (Section 1: Male first, Section 2: Female first, etc.)"""

    prompt = f"""You are an expert IELTS listening test creator. Generate a listening comprehension test with various question types.

**🎯 CRITICAL: YOU MUST GENERATE EXACTLY {num_questions} QUESTIONS - NO EXCEPTIONS!**

**SPECIFICATIONS:**
- Language: {language}
- Topic: {topic}
- Difficulty: {difficulty_desc}
- Number of speakers: {num_speakers}
- Number of audio sections: {num_audio_sections}
- **TOTAL QUESTIONS REQUIRED: {num_questions}** (this is MANDATORY, not a suggestion)
- User requirements: {user_query}

**QUESTION COUNT DISTRIBUTION:**
- **YOU MUST CREATE EXACTLY {num_audio_sections} SECTIONS IN "audio_sections" ARRAY**
- Distribute {num_questions} QUESTION OBJECTS across ALL {num_audio_sections} sections (aim for roughly equal distribution)
- **CALCULATION:** Each section should have approximately {max(1, num_questions // num_audio_sections)} questions
  - Example: {num_questions} questions ÷ {num_audio_sections} sections = {max(1, num_questions // num_audio_sections)} questions per section
- **VERIFY BEFORE SUBMITTING:**
  1. Count sections in "audio_sections" array = Must be {num_audio_sections}
  2. Count total QUESTION OBJECTS across all sections = Must be {num_questions}
- It's better to generate {num_questions + 2} question objects than {num_questions - 2} question objects

**SPEAKER CONFIGURATION:**
{speaker_instruction}

**QUESTION TYPES TO USE (Mix them - AI decides quantity per type):**

1. **MCQ (Multiple Choice)**: 4 options (A-D), single or multiple correct answers
   - Good for: main ideas, details, attitudes, purposes

2. **MATCHING**: Match items from list (1-5) to options (A-H)
   - Good for: matching speakers to opinions, places to descriptions, people to actions
   - Example: Match each speaker (1-3) to what they say about the topic (A-E)

3. **COMPLETION (Form/Note/Table)**: Fill in blanks with NO MORE THAN TWO/THREE WORDS
   - Good for: capturing specific information (names, dates, prices, addresses)
   - Format: "Name: _____(1)_____, Phone: _____(2)_____"

4. **SENTENCE COMPLETION**: Complete sentences with words from audio
   - Good for: key facts and details
   - Example: "The library opens at _____." (Answer: 8 AM)

5. **SHORT ANSWER**: Answer questions with NO MORE THAN THREE WORDS
   - Good for: factual information
   - Example: "What is the speaker's occupation?" (Answer: Software Engineer)

**OUTPUT FORMAT (JSON) - EXAMPLE WITH MULTIPLE SECTIONS:**

Below is an example showing how to structure multiple sections. **YOU MUST GENERATE {num_audio_sections} SECTIONS LIKE THIS:**

{{
  "audio_sections": [
    {{
      "section_number": 1,
      "section_title": "Conversation about Library Membership",
      "script": {{
        "speaker_roles": ["Student", "Librarian"],
        "lines": [
          {{"speaker": 0, "text": "Hi, I'd like to register for a library card."}},
          {{"speaker": 1, "text": "Sure! Can I have your name and student ID?"}}
        ]
      }},
      "questions": [
        {{
          "question_type": "mcq",
          "question_text": "What is the main purpose of the conversation?",
          "instruction": "Choose the correct letter, A, B, C or D",
          "options": [
            {{"option_key": "A", "option_text": "To borrow books"}},
            {{"option_key": "B", "option_text": "To register for a library card"}},
            {{"option_key": "C", "option_text": "To return books"}},
            {{"option_key": "D", "option_text": "To ask for directions"}}
          ],
          "correct_answers": ["B"],
          "timestamp_hint": "0:00-0:10",
          "explanation": "Student explicitly states wanting to register for a library card."
        }},
        {{
          "question_type": "completion",
          "question_text": "Complete the registration form",
          "instruction": "Write NO MORE THAN TWO WORDS AND/OR A NUMBER for each answer",
          "template": "Name: _____(2)_____\\nStudent ID: _____(3)_____\\nPhone: _____(4)_____",
          "blanks": [
            {{"key": "2", "position": "Name", "word_limit": 2}},
            {{"key": "3", "position": "Student ID", "word_limit": 3}},
            {{"key": "4", "position": "Phone", "word_limit": 3}}
          ],
          "correct_answers": [
            {{"blank_key": "2", "answers": ["John Smith", "john smith", "JOHN SMITH"]}},
            {{"blank_key": "3", "answers": ["A12345", "a12345", "A 12345"]}},
            {{"blank_key": "4", "answers": ["0412 555 678", "0412555678", "04125556 78"]}}
          ],
          "timestamp_hint": "0:10-0:30",
          "explanation": "The student provides personal details during registration."
        }},
        {{
          "question_type": "matching",
          "question_text": "Match each facility to its location",
          "instruction": "Write the correct letter A-E next to questions 5-7",
          "left_items": [
            {{"key": "5", "text": "Reading room"}},
            {{"key": "6", "text": "Computer lab"}},
            {{"key": "7", "text": "Study rooms"}}
          ],
          "right_options": [
            {{"key": "A", "text": "Ground floor"}},
            {{"key": "B", "text": "First floor"}},
            {{"key": "C", "text": "Second floor"}},
            {{"key": "D", "text": "Third floor"}},
            {{"key": "E", "text": "Basement"}}
          ],
          \"correct_answers\": [\n            {{\"left_key\": \"5\", \"right_key\": \"B\"}},\n            {{\"left_key\": \"6\", \"right_key\": \"B\"}},\n            {{\"left_key\": \"7\", \"right_key\": \"C\"}}\n          ],\n          \"timestamp_hint\": \"0:45-1:10\",
          "explanation": "Librarian describes locations of facilities."
        }},
        {{
          "question_type": "sentence_completion",
          "question_text": "Complete the sentences below",
          "instruction": "Write NO MORE THAN TWO WORDS for each answer",
          "sentences": [
            {{
              "key": "8",
              "template": "The library's opening hours on weekdays are from _____.",
              "word_limit": 2,
              "correct_answers": ["8 AM", "8:00 AM", "eight o'clock"]
            }},
            {{
              "key": "9",
              "template": "Members can borrow a maximum of _____ books.",
              "word_limit": 2,
              "correct_answers": ["5 books", "five books", "5"]
            }}
          ],
          "timestamp_hint": "1:20-1:40",
          "explanation": "Librarian mentions operating hours and borrowing limits."
        }},
        {{
          "question_type": "short_answer",
          "question_text": "Answer the questions",
          "instruction": "Write NO MORE THAN THREE WORDS for each answer",
          "questions": [
            {{
              "key": "10",
              "text": "What type of card is being issued?",
              "word_limit": 3,
              "correct_answers": ["library card", "student library card", "Library Card"]
            }}
          ],
          "timestamp_hint": "1:50-2:00",
          "explanation": "Context from the entire conversation about card registration."
        }}
      ]
    }},
    {{
      "section_number": 2,
      "section_title": "Guide to Student Services",
      "script": {{
        "speaker_roles": ["Orientation Leader"],
        "lines": [
          {{"speaker": 0, "text": "Welcome to campus orientation. Today I'll explain our student services."}},
          {{"speaker": 0, "text": "First, let's talk about the health center..."}}
        ]
      }},
      "questions": [
        {{
          "question_type": "mcq",
          "question_text": "What is the first service mentioned?",
          "instruction": "Choose the correct letter, A, B, C or D",
          "options": [
            {{"option_key": "A", "option_text": "Library"}},
            {{"option_key": "B", "option_text": "Health center"}},
            {{"option_key": "C", "option_text": "Career office"}},
            {{"option_key": "D", "option_text": "Sports facilities"}}
          ],
                    \"correct_answers\": [\"B\"],\n          \"timestamp_hint\": \"0:00-0:15\",\n          \"explanation\": \"Speaker explicitly mentions health center first.\"
        }}
      ]
    }}
  ]
}}

**CRITICAL: This example shows ONLY 2 sections for illustration. YOU MUST generate ALL {num_audio_sections} sections!**
**Each section must have its own script and questions. Distribute {num_questions} questions across all {num_audio_sections} sections.**

**CRITICAL INSTRUCTIONS:**
1. Output MUST be valid JSON
2. **Generate EXACTLY {num_audio_sections} sections** in "audio_sections" array (no more, no less)
   - Section 1, Section 2, ..., Section {num_audio_sections}
   - Each section needs: section_number, section_title, script, questions
3. **MUST generate EXACTLY {num_questions} QUESTION OBJECTS total** - distribute across ALL sections
   - Example: {num_questions} questions ÷ {num_audio_sections} sections ≈ {max(1, num_questions // num_audio_sections)} questions per section
4. **COUNT QUESTION OBJECTS, NOT ITEMS/BLANKS:** 1 matching with 5 items = 1 question object, NOT 5
5. **ALL MCQ questions MUST have:**
   - Exactly 4 options (A, B, C, D) with both option_key and option_text
   - correct_answer_keys array (cannot be null/empty)
   - Complete question_text (not just "Choose the correct letter")
6. MIX question types (don't use only MCQ - aim for variety)
6. **For completion/sentence/short answer:**
   - Set word_limit to match instruction (e.g., "NO MORE THAN TWO WORDS" → word_limit: 2)
   - IMPORTANT: word_limit must be 1-3 (typical IELTS)
   - Include "AND/OR A NUMBER" in instruction for flexibility
   - Provide multiple acceptable answers: case variations, spacing variations, equivalent formats
   - Examples: ["15th July", "15 July", "July 15th", "July 15"] or ["0908 555 231", "0908555231"]
7. **For matching:**
   - Left items use numbered keys: "1", "2", "3", etc.
   - Right options use letter keys: "A", "B", "C", etc.
   - MUST have MORE right options than left items (e.g., 3 items → 5 options)
   - Keys in correct_matches must match exactly: left_key from left_items, right_key from right_options
8. **For MCQ:**
   - Always provide exactly 4 options (A, B, C, D)
   - correct_answer_keys is an array (can have multiple correct answers)
10. All content in {language} language
11. Scripts must be natural and conversational
12. Questions answerable from audio only
13. Include timestamp hints (e.g., "0:15-0:30")

**HOW TO COUNT QUESTIONS (CRITICAL - READ CAREFULLY):**

🎯 **IMPORTANT:** 1 question object in JSON = 1 question (regardless of how many items/blanks inside)

- **MCQ:** 1 MCQ object = 1 question
  - Example: 1 MCQ with 4 options (A-D) = 1 question

- **MATCHING:** 1 matching object = 1 question (even if matching 5 items)
  - Example: Match 5 people to 8 options = 1 question (not 5 questions!)

- **COMPLETION:** 1 completion object = 1 question (even if filling 5 blanks)
  - Example: Complete form with 5 blanks = 1 question (not 5 questions!)

- **SENTENCE COMPLETION:** 1 sentence_completion object = 1 question (even if 3 sentences)
  - Example: Complete 3 sentences = 1 question (not 3 questions!)

- **SHORT ANSWER:** 1 short_answer object = 1 question (even if 2 sub-questions)
  - Example: Answer 2 questions = 1 question (not 2 questions!)

**CALCULATION CHECK BEFORE OUTPUT:**
Before you output JSON, COUNT THE QUESTION OBJECTS:
Total question objects in "questions" array = ?
Result MUST = {num_questions}

**QUESTION TYPE DISTRIBUTION (Flexible - AI decides):**
You have 5 question types to choose from for your {num_questions} questions:
- MCQ: Most versatile (30-40% of questions)
- Completion: IELTS authentic (20-30% of questions)
- Matching: Adds variety (15-25% of questions)
- Sentence completion: Detail-focused (10-20% of questions)
- Short answer: Quick facts (10-20% of questions)

**Example for {num_questions} questions:**
If {num_questions} = 10, you might generate 10 QUESTION OBJECTS:
- 3 MCQ objects (questions 1, 2, 3)
- 2 Completion objects with 3-5 blanks each (questions 4, 5)
- 2 Matching objects with 3-4 items each (questions 6, 7)
- 2 Sentence completion objects with 2-3 sentences each (questions 8, 9)
- 1 Short answer object with 2-3 sub-questions (question 10)
TOTAL = 3+2+2+2+1 = 10 question objects ✓

**🔴 FINAL REMINDER BEFORE GENERATING:**
1. **Count SECTIONS:** You MUST have EXACTLY {num_audio_sections} section objects in "audio_sections" array
2. **Count QUESTIONS:** Total question objects across ALL sections = EXACTLY {num_questions}
3. **Distribution example for {num_questions} questions in {num_audio_sections} sections:**
   - Section 1: {max(1, num_questions // num_audio_sections)} questions
   - Section 2: {max(1, num_questions // num_audio_sections)} questions
   - Section 3: {max(1, num_questions // num_audio_sections)} questions
   - Section 4: {max(1, num_questions // num_audio_sections)} questions
   - (Add remaining questions to last section if {num_questions} not evenly divisible)
4. Example: 10 questions = 10 objects across 4 sections (2+3+2+3 or similar distribution)
5. If you have fewer sections than {num_audio_sections}, ADD MORE SECTIONS
6. If you have fewer questions than {num_questions}, ADD MORE QUESTION OBJECTS
7. Quality is important BUT hitting {num_audio_sections} SECTIONS and {num_questions} QUESTIONS is MANDATORY

Now, generate listening test like IELTS style. Return ONLY the JSON object."""

    return prompt


def get_ielts_example_output():
    """Example output for reference"""
    return {
        "audio_sections": [
            {
                "section_number": 1,
                "section_title": "Enquiry about language course",
                "script": {
                    "speaker_roles": ["Student", "Course Advisor"],
                    "lines": [
                        {
                            "speaker": 0,
                            "text": "Hello, I'm interested in enrolling in a Spanish course.",
                        },
                        {
                            "speaker": 1,
                            "text": "Great! We have several options. What's your current level?",
                        },
                    ],
                },
                "questions": [
                    {
                        "question_type": "completion",
                        "question_text": "Complete the enrollment form",
                        "instruction": "Write NO MORE THAN TWO WORDS for each answer",
                        "template": "Course: _____(1)_____ Spanish\nLevel: _____(2)_____\nStart date: _____(3)_____",
                        "blanks": [
                            {"key": "1", "position": "Course type", "word_limit": 2},
                            {"key": "2", "position": "Level", "word_limit": 1},
                            {"key": "3", "position": "Date", "word_limit": 2},
                        ],
                        "correct_answers": {
                            "1": ["Intensive Spanish", "intensive spanish"],
                            "2": ["Beginner", "beginner"],
                            "3": ["March 1", "1 March", "1st March"],
                        },
                        "timestamp_hint": "0:10-0:40",
                        "explanation": "Student provides course preferences and level",
                    }
                ],
            }
        ]
    }
