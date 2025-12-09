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
                                    "correct_answer_keys": {
                                        "type": "array",
                                        "items": {"type": "string"},
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
    """Build IELTS-style listening test prompt with 6 question types"""

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
        speaker_instruction = "Generate a DIALOGUE (two speakers). Alternate naturally. Include roles WITH gender (e.g., 'Male Customer/Female Agent', 'Female Student/Male Teacher'). Use diverse gender combinations."

    prompt = f"""You are an expert IELTS listening test creator. Generate a listening comprehension test with various question types.

**CRITICAL REQUIREMENTS:**
- Language: {language}
- Topic: {topic}
- Difficulty: {difficulty_desc}
- Number of speakers: {num_speakers}
- Number of audio sections: {num_audio_sections}
- **IMPORTANT: Generate EXACTLY {num_questions} questions total** (distribute evenly across {num_audio_sections} section(s))
- User requirements: {user_query}

**QUESTION COUNT ENFORCEMENT:**
- If {num_audio_sections} = 1: Generate ALL {num_questions} questions in section 1
- If {num_audio_sections} = 2: Generate ~{num_questions//2} questions per section (total must be {num_questions})
- DO NOT generate fewer questions than {num_questions}!

**SPEAKER CONFIGURATION:**
{speaker_instruction}

**QUESTION TYPES TO USE (Mix them):**

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

**OUTPUT FORMAT (JSON):**

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
          "question_type": "completion",
          "question_text": "Complete the registration form",
          "instruction": "Write NO MORE THAN TWO WORDS AND/OR A NUMBER for each answer",
          "template": "Name: _____(1)_____\\nStudent ID: _____(2)_____\\nPhone: _____(3)_____",
          "blanks": [
            {{"key": "1", "position": "Name", "word_limit": 2}},
            {{"key": "2", "position": "Student ID", "word_limit": 3}},
            {{"key": "3", "position": "Phone", "word_limit": 3}}
          ],
          "correct_answers": [
            {{"blank_key": "1", "answers": ["John Smith", "john smith", "JOHN SMITH"]}},
            {{"blank_key": "2", "answers": ["A12345", "a12345", "A 12345"]}},
            {{"blank_key": "3", "answers": ["0412 555 678", "0412555678", "04125556 78"]}}
          ],
          "timestamp_hint": "0:10-0:30",
          "explanation": "The student provides personal details during registration."
        }},
        {{
          "question_type": "matching",
          "question_text": "Match each facility to its location",
          "instruction": "Write the correct letter A-E next to questions 4-6",
          "left_items": [
            {{"key": "4", "text": "Reading room"}},
            {{"key": "5", "text": "Computer lab"}},
            {{"key": "6", "text": "Study rooms"}}
          ],
          "right_options": [
            {{"key": "A", "text": "Ground floor"}},
            {{"key": "B", "text": "First floor"}},
            {{"key": "C", "text": "Second floor"}},
            {{"key": "D", "text": "Third floor"}},
            {{"key": "E", "text": "Basement"}}
          ],
          "correct_matches": [
            {{"left_key": "4", "right_key": "B"}},
            {{"left_key": "5", "right_key": "B"}},
            {{"left_key": "6", "right_key": "C"}}
          ],
          "timestamp_hint": "0:45-1:10",
          "explanation": "Librarian describes locations of facilities."
        }},
        {{
          "question_type": "short_answer",
          "question_text": "Answer the questions",
          "instruction": "Write NO MORE THAN THREE WORDS for each answer",
          "questions": [
            {{
              "key": "7",
              "text": "What time does the library open on weekdays?",
              "word_limit": 2,
              "correct_answers": ["8 AM", "8:00 AM", "eight o'clock"]
            }},
            {{
              "key": "8",
              "text": "How many books can students borrow at once?",
              "word_limit": 1,
              "correct_answers": ["5", "five"]
            }}
          ],
          "timestamp_hint": "1:20-1:40",
          "explanation": "Librarian mentions operating hours and borrowing limits."
        }}
      ]
    }}
  ]
}}

**CRITICAL INSTRUCTIONS:**
1. Output MUST be valid JSON
2. Generate EXACTLY {num_audio_sections} sections (no more, no less)
3. **MUST generate EXACTLY {num_questions} questions total** - distribute across sections
4. **ALL MCQ questions MUST have:**
   - Exactly 4 options (A, B, C, D) with both option_key and option_text
   - correct_answer_keys array (cannot be null/empty)
   - Complete question_text (not just "Choose the correct letter")
5. MIX question types (don't use only MCQ - aim for variety)
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
9. All content in {language} language
10. Scripts must be natural and conversational
11. Questions answerable from audio only
12. Include timestamp hints (e.g., "0:15-0:30")

**QUESTION TYPE DISTRIBUTION (Recommended):**
- 40-50% MCQ (familiar format)
- 20-30% Completion/Sentence completion (IELTS common)
- 15-20% Matching (good for variety)
- 10-15% Short answer (specific details)

Now, generate the IELTS listening test. Return ONLY the JSON object."""

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
