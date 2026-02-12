"""
Test Deepseek API for Conversation Generation
Topic: At Restaurant (Beginner)
"""

import os
import json
from openai import OpenAI

# Deepseek API
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

# Prompt template
PROMPT = """Generate 1 English conversation for learning English at BEGINNER level on topic "At Restaurant".

Requirements:
1. Conversation structure:
   - 8-10 dialogue turns (A and B speakers alternating)
   - Speaker A: Customer (Male)
   - Speaker B: Waiter (Female)
   - Natural, realistic restaurant dialogue
   - Use simple vocabulary suitable for beginners
   - Include common restaurant phrases

2. Content for each turn:
   - speaker: "A" or "B"
   - gender: "male" or "female"
   - text_en: English text
   - text_vi: Vietnamese translation
   - order: Turn number (1, 2, 3...)

3. Conversation metadata:
   - title_en: English title (e.g., "Ordering Food")
   - title_vi: Vietnamese title
   - situation: Brief context of the conversation

4. Vocabulary & Grammar:
   - vocabulary: List 8-12 key words from conversation
     * word: The word
     * definition_en: English definition
     * definition_vi: Vietnamese definition
     * example: Usage example from conversation
     * pos_tag: NOUN, VERB, ADJ, ADV, etc.

   - grammar_points: List 3-5 grammar patterns
     * pattern: The grammar pattern (e.g., "Can I have...?")
     * explanation_en: English explanation
     * explanation_vi: Vietnamese explanation
     * example: Example from conversation

5. Output format: VALID JSON ONLY
   {
     "title_en": "...",
     "title_vi": "...",
     "situation": "...",
     "dialogue": [
       {
         "speaker": "A",
         "gender": "male",
         "text_en": "...",
         "text_vi": "...",
         "order": 1
       }
     ],
     "vocabulary": [
       {
         "word": "...",
         "definition_en": "...",
         "definition_vi": "...",
         "example": "...",
         "pos_tag": "..."
       }
     ],
     "grammar_points": [
       {
         "pattern": "...",
         "explanation_en": "...",
         "explanation_vi": "...",
         "example": "..."
       }
     ]
   }

IMPORTANT: Return ONLY valid JSON. No markdown, no code blocks, no explanations.
"""

print("=" * 80)
print("Testing Deepseek API - Conversation Generation")
print("Topic: At Restaurant (Beginner)")
print("=" * 80)
print()

try:
    print("🚀 Calling Deepseek API...")
    print()

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": "You are an expert English teacher creating natural conversations for language learners. Always respond in valid JSON format.",
            },
            {"role": "user", "content": PROMPT},
        ],
        temperature=0.7,
        max_tokens=4000,
        stream=False,
    )

    raw_response = response.choices[0].message.content

    print("📥 Raw Response:")
    print("-" * 80)
    print(raw_response[:500] + "..." if len(raw_response) > 500 else raw_response)
    print()

    # Try to parse JSON
    print("🔍 Parsing JSON...")

    # Clean response if it has markdown code blocks
    cleaned = raw_response.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    conversation_data = json.loads(cleaned)

    print("✅ JSON Parsed Successfully!")
    print()

    # Validate structure
    print("📊 Validation:")
    print("-" * 80)

    required_keys = [
        "title_en",
        "title_vi",
        "situation",
        "dialogue",
        "vocabulary",
        "grammar_points",
    ]
    for key in required_keys:
        status = "✅" if key in conversation_data else "❌"
        print(f"{status} {key}: {type(conversation_data.get(key, 'MISSING'))}")

    print()

    # Show conversation details
    print("📖 Conversation Details:")
    print("-" * 80)
    print(f"Title (EN): {conversation_data.get('title_en', 'N/A')}")
    print(f"Title (VI): {conversation_data.get('title_vi', 'N/A')}")
    print(f"Situation: {conversation_data.get('situation', 'N/A')}")
    print()

    dialogue = conversation_data.get("dialogue", [])
    print(f"🗣️ Dialogue Turns: {len(dialogue)}")
    print()

    for turn in dialogue[:3]:  # Show first 3 turns
        print(f"  [{turn.get('speaker', '?')}] {turn.get('text_en', 'N/A')}")
        print(f"      → {turn.get('text_vi', 'N/A')}")
        print()

    if len(dialogue) > 3:
        print(f"  ... and {len(dialogue) - 3} more turns")
        print()

    # Vocabulary
    vocabulary = conversation_data.get("vocabulary", [])
    print(f"📚 Vocabulary: {len(vocabulary)} words")
    print()

    for word in vocabulary[:3]:  # Show first 3
        print(f"  • {word.get('word', 'N/A')} ({word.get('pos_tag', 'N/A')})")
        print(f"    EN: {word.get('definition_en', 'N/A')}")
        print(f"    VI: {word.get('definition_vi', 'N/A')}")
        print(f"    Example: {word.get('example', 'N/A')}")
        print()

    if len(vocabulary) > 3:
        print(f"  ... and {len(vocabulary) - 3} more words")
        print()

    # Grammar points
    grammar = conversation_data.get("grammar_points", [])
    print(f"📝 Grammar Points: {len(grammar)}")
    print()

    for point in grammar:
        print(f"  • Pattern: {point.get('pattern', 'N/A')}")
        print(f"    EN: {point.get('explanation_en', 'N/A')}")
        print(f"    VI: {point.get('explanation_vi', 'N/A')}")
        print(f"    Example: {point.get('example', 'N/A')}")
        print()

    # Save to file
    output_file = "test_conversation_output.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(conversation_data, f, ensure_ascii=False, indent=2)

    print(f"💾 Saved to: {output_file}")
    print()

    print("=" * 80)
    print("✅ SUCCESS - Deepseek returned valid JSON!")
    print("=" * 80)

    # Summary
    print()
    print("📊 Summary:")
    print(f"  ✅ Valid JSON format")
    print(f"  ✅ {len(dialogue)} dialogue turns")
    print(f"  ✅ {len(vocabulary)} vocabulary items")
    print(f"  ✅ {len(grammar)} grammar points")
    print(f"  ✅ Includes Vietnamese translations")
    print()

except json.JSONDecodeError as e:
    print(f"❌ JSON Parse Error: {e}")
    print()
    print("Raw response:")
    print(raw_response)

except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")
    import traceback

    traceback.print_exc()
