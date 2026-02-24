#!/usr/bin/env python3
"""
Translate Conversations: EN -> ZH (Simplified Chinese) / JA (Japanese) / KO (Korean)

Purpose:
- Translate dialogue turns, title, situation, vocabulary, grammar for each conversation
- Single DeepSeek call per conversation returns all 3 languages at once
- Updates existing documents in-place (adds new fields, does NOT overwrite EN/VI)
- Skips conversations already translated (has `translations_added` field)

Schema additions to conversation_library:
  title.zh / title.ja / title.ko
  situation_zh / situation_ja / situation_ko
  full_text_zh / full_text_ja / full_text_ko
  dialogue[].text_zh / text_ja / text_ko
  translations_added: ["zh", "ja", "ko"]

Schema additions to conversation_vocabulary:
  vocabulary[].definition_zh / definition_ja / definition_ko
  grammar_points[].explanation_zh / explanation_ja / explanation_ko

RUN (test 2 conversations):
    python crawler/translate_conversations.py --level beginner --limit 2

RUN (full level):
    python crawler/translate_conversations.py --level beginner
    python crawler/translate_conversations.py --level intermediate
    python crawler/translate_conversations.py --level advanced

PRODUCTION (background):
    docker exec -d ai-chatbot-rag bash -c 'python crawler/translate_conversations.py --level beginner > /app/logs/translate_beginner.log 2>&1'
"""

import os
import sys
import json
import asyncio
import argparse
from datetime import datetime
from typing import Dict, List, Optional

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.database.db_manager import DBManager

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY environment variable required")

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1")

BATCH_SIZE = 5
BATCH_DELAY = 3


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────────────────────────────────────────


def build_translation_prompt(conversation: Dict, vocab_data: Optional[Dict]) -> str:
    title_en = conversation["title"]["en"]
    situation = conversation.get("situation", "")
    dialogue = conversation.get("dialogue", [])
    vocabulary = vocab_data.get("vocabulary", []) if vocab_data else []
    grammar_points = vocab_data.get("grammar_points", []) if vocab_data else []

    dialogue_lines = "\n".join(
        f"[{t['order']}][{t['speaker']}] {t['text_en']}" for t in dialogue
    )
    vocab_lines = "\n".join(f"- {v['word']}: {v['definition_en']}" for v in vocabulary)
    grammar_lines = "\n".join(
        f"- {g['pattern']}: {g['explanation_en']}" for g in grammar_points
    )

    return f"""Translate the following English conversation content into 3 languages:
- zh: Simplified Chinese (简体中文)
- ja: Japanese (日本語)
- ko: Korean (한국어)

Translate naturally and conversationally. Keep proper nouns (names like Tom, Sarah, cities) as-is.

SOURCE:
Title: "{title_en}"
Situation: "{situation}"

Dialogue:
{dialogue_lines}

Vocabulary definitions:
{vocab_lines if vocab_lines else "(none)"}

Grammar pattern explanations:
{grammar_lines if grammar_lines else "(none)"}

Return ONLY valid JSON (no markdown, no extra text) in this exact structure:
{{
  "title": {{"zh": "...", "ja": "...", "ko": "..."}},
  "situation": {{"zh": "...", "ja": "...", "ko": "..."}},
  "dialogue": [
    {{"order": 1, "text_zh": "...", "text_ja": "...", "text_ko": "..."}},
    {{"order": 2, "text_zh": "...", "text_ja": "...", "text_ko": "..."}}
  ],
  "vocabulary": [
    {{"word": "word1", "definition_zh": "...", "definition_ja": "...", "definition_ko": "..."}}
  ],
  "grammar_points": [
    {{"pattern": "pattern1", "explanation_zh": "...", "explanation_ja": "...", "explanation_ko": "..."}}
  ]
}}

RULES:
- dialogue array must have EXACTLY {len(dialogue)} items matching each [order] above
- vocabulary array must have {len(vocabulary)} items (same order as input)
- grammar_points array must have {len(grammar_points)} items (same order as input)
- definitions/explanations should be concise (1-2 sentences max)
"""


# ─────────────────────────────────────────────────────────────────────────────
# DeepSeek call
# ─────────────────────────────────────────────────────────────────────────────


async def translate_conversation(
    conversation: Dict, vocab_data: Optional[Dict]
) -> Dict:
    prompt = build_translation_prompt(conversation, vocab_data)
    conversation_id = conversation["conversation_id"]
    title_en = conversation["title"]["en"]

    print(f"\n{'='*70}")
    print(f"🌐 Translating: {title_en} ({conversation_id})")
    print(f"{'='*70}")

    for attempt in range(3):
        try:
            print(f"  🔄 Attempt {attempt + 1}/3...")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # Lower temp for translation accuracy
                max_tokens=8000,
            )
            content = response.choices[0].message.content.strip()
            content = content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)

            # Validate required keys
            assert "title" in data, "Missing title"
            assert "situation" in data, "Missing situation"
            assert "dialogue" in data, "Missing dialogue"
            assert len(data["dialogue"]) == len(
                conversation.get("dialogue", [])
            ), f"Dialogue count mismatch: got {len(data['dialogue'])}, expected {len(conversation.get('dialogue', []))}"

            print(f"  ✅ Translation received ({len(data['dialogue'])} dialogue turns)")
            return data

        except json.JSONDecodeError as e:
            print(f"  ❌ JSON parse error: {e}")
            if attempt == 2:
                raise
        except AssertionError as e:
            print(f"  ❌ Validation error: {e}")
            if attempt == 2:
                raise
        except Exception as e:
            print(f"  ❌ Error: {e}")
            if attempt == 2:
                raise

    raise Exception(f"Failed to translate {conversation_id} after 3 attempts")


# ─────────────────────────────────────────────────────────────────────────────
# Save to DB
# ─────────────────────────────────────────────────────────────────────────────


def save_translations(
    db,
    conversation_id: str,
    conversation: Dict,
    vocab_data: Optional[Dict],
    translation: Dict,
):
    now = datetime.utcnow()

    # ── 1. Update conversation_library ──────────────────────────────────────
    # Build updated dialogue array (add text_zh/ja/ko to each turn)
    dialogue = conversation.get("dialogue", [])
    trans_by_order = {t["order"]: t for t in translation["dialogue"]}

    updated_dialogue = []
    for turn in dialogue:
        updated_turn = dict(turn)
        order = turn["order"]
        if order in trans_by_order:
            t = trans_by_order[order]
            updated_turn["text_zh"] = t.get("text_zh", "")
            updated_turn["text_ja"] = t.get("text_ja", "")
            updated_turn["text_ko"] = t.get("text_ko", "")
        updated_dialogue.append(updated_turn)

    # Build full translated texts (join all turns)
    full_text_zh = "\n".join(
        f"[{t['speaker']}] {t.get('text_zh', '')}" for t in updated_dialogue
    )
    full_text_ja = "\n".join(
        f"[{t['speaker']}] {t.get('text_ja', '')}" for t in updated_dialogue
    )
    full_text_ko = "\n".join(
        f"[{t['speaker']}] {t.get('text_ko', '')}" for t in updated_dialogue
    )

    title_trans = translation.get("title", {})
    situation_trans = translation.get("situation", {})

    conv_update = {
        "$set": {
            "title.zh": title_trans.get("zh", ""),
            "title.ja": title_trans.get("ja", ""),
            "title.ko": title_trans.get("ko", ""),
            "situation_zh": situation_trans.get("zh", ""),
            "situation_ja": situation_trans.get("ja", ""),
            "situation_ko": situation_trans.get("ko", ""),
            "dialogue": updated_dialogue,  # Replace full array
            "full_text_zh": full_text_zh,
            "full_text_ja": full_text_ja,
            "full_text_ko": full_text_ko,
            "translations_added": ["zh", "ja", "ko"],
            "translations_updated_at": now,
        }
    }
    db.conversation_library.update_one(
        {"conversation_id": conversation_id}, conv_update
    )
    print(f"  💾 conversation_library updated")

    # ── 2. Update conversation_vocabulary ───────────────────────────────────
    if vocab_data and (
        translation.get("vocabulary") or translation.get("grammar_points")
    ):
        vocab = vocab_data.get("vocabulary", [])
        grammar = vocab_data.get("grammar_points", [])
        trans_vocab = translation.get("vocabulary", [])
        trans_grammar = translation.get("grammar_points", [])

        # Build updated arrays (match by index)
        updated_vocab = []
        for i, v in enumerate(vocab):
            updated_v = dict(v)
            if i < len(trans_vocab):
                tv = trans_vocab[i]
                updated_v["definition_zh"] = tv.get("definition_zh", "")
                updated_v["definition_ja"] = tv.get("definition_ja", "")
                updated_v["definition_ko"] = tv.get("definition_ko", "")
            updated_vocab.append(updated_v)

        updated_grammar = []
        for i, g in enumerate(grammar):
            updated_g = dict(g)
            if i < len(trans_grammar):
                tg = trans_grammar[i]
                updated_g["explanation_zh"] = tg.get("explanation_zh", "")
                updated_g["explanation_ja"] = tg.get("explanation_ja", "")
                updated_g["explanation_ko"] = tg.get("explanation_ko", "")
            updated_grammar.append(updated_g)

        db.conversation_vocabulary.update_one(
            {"conversation_id": conversation_id},
            {
                "$set": {
                    "vocabulary": updated_vocab,
                    "grammar_points": updated_grammar,
                    "translations_added": ["zh", "ja", "ko"],
                    "translations_updated_at": now,
                }
            },
        )
        print(
            f"  💾 conversation_vocabulary updated ({len(updated_vocab)} words, {len(updated_grammar)} grammar)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Process one conversation
# ─────────────────────────────────────────────────────────────────────────────


async def process_one(conversation: Dict, db, semaphore: asyncio.Semaphore) -> Dict:
    async with semaphore:
        conversation_id = conversation["conversation_id"]
        title_en = conversation.get("title", {}).get("en", "?")
        try:
            vocab_data = db.conversation_vocabulary.find_one(
                {"conversation_id": conversation_id}
            )
            translation = await translate_conversation(conversation, vocab_data)
            save_translations(
                db, conversation_id, conversation, vocab_data, translation
            )
            return {
                "conversation_id": conversation_id,
                "title": title_en,
                "success": True,
            }
        except Exception as e:
            print(f"  ❌ FAILED {conversation_id}: {e}")
            return {
                "conversation_id": conversation_id,
                "title": title_en,
                "success": False,
                "error": str(e),
            }


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--level", choices=["beginner", "intermediate", "advanced"], required=True
    )
    parser.add_argument("--limit", type=int, default=0, help="Limit number (0 = all)")
    parser.add_argument(
        "--force", action="store_true", help="Re-translate already translated"
    )
    args = parser.parse_args()

    print("=" * 70)
    print(f"🌐 CONVERSATION TRANSLATION — {args.level.upper()}")
    print("=" * 70)
    print(f"Languages: ZH (Simplified Chinese) / JA (Japanese) / KO (Korean)")
    print(f"Level: {args.level} | Limit: {args.limit or 'ALL'} | Force: {args.force}")
    print("=" * 70)

    db = DBManager().db
    print(f"✅ MongoDB: {db.name}")

    # Query: skip already translated unless --force
    query: Dict = {"level": args.level}
    if not args.force:
        query["translations_added"] = {
            "$nin": [["zh", "ja", "ko"]],
            "$not": {"$all": ["zh", "ja", "ko"]},
        }
        # Simpler: just check if translations_added field is missing
        query = {"level": args.level, "translations_added": {"$exists": False}}

    conversations = list(db.conversation_library.find(query).sort("conversation_id", 1))
    if args.limit:
        conversations = conversations[: args.limit]

    total = len(conversations)
    print(f"📚 Found {total} conversations to translate")
    if total == 0:
        print("✅ All conversations already translated!")
        return

    semaphore = asyncio.Semaphore(BATCH_SIZE)
    results = []

    for i in range(0, total, BATCH_SIZE):
        batch = conversations[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"\n{'='*70}")
        print(f"📦 BATCH {batch_num}/{total_batches} ({len(batch)} conversations)")
        print(f"{'='*70}")

        tasks = [process_one(conv, db, semaphore) for conv in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in batch_results:
            if isinstance(r, Exception):
                print(f"❌ Exception: {r}")
                results.append({"success": False, "error": str(r)})
                continue
            status = "✅" if r["success"] else "❌"
            print(f"{status} {r['conversation_id']:55} | {r['title'][:35]}")
            results.append(r)

        if i + BATCH_SIZE < total:
            print(f"\n⏳ Waiting {BATCH_DELAY}s before next batch...")
            await asyncio.sleep(BATCH_DELAY)

    success = sum(1 for r in results if r.get("success"))
    failed = len(results) - success
    print(f"\n{'='*70}")
    print(f"📊 SUMMARY: {success} ✅  {failed} ❌  (total: {len(results)})")
    if failed:
        print("Failed:")
        for r in results:
            if not r.get("success"):
                print(f"  - {r.get('conversation_id', '?')}: {r.get('error', '?')}")
    print("✅ Translation complete!")


if __name__ == "__main__":
    asyncio.run(main())
