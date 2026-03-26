"""
Pronunciation Scoring Service

Two lazy-loaded singletons:
  - faster-whisper tiny (already cached from alignment batch)   → transcription
  - facebook/wav2vec2-lv-60-espeak-cv-ft                        → phoneme recognition

Reference IPA is derived from eng_to_ipa (pure Python, ships own dict).

Supports: single word, phrase, full sentence (any length).
"""

from __future__ import annotations

import io
import re
import logging
import tempfile
from typing import Optional

import numpy as np

logger = logging.getLogger("chatbot")

# ── eSpeak ↔ IPA normalization map ──────────────────────────────────────────
# Wav2Vec2/eSpeak sometimes uses different chars for the same sound as eng_to_ipa.
_NORMALIZE = {
    "r": "ɹ",  # eng_to_ipa 'r' → eSpeak 'ɹ'
    "ɾ": "ɹ",  # flap → rhotic
    "ː": "",  # drop length markers
    "ˑ": "",
}

# Known multi-character IPA/eSpeak tokens (order matters: longer first)
_MULTIGRAPHS = [
    "aʊ",
    "aɪ",
    "eɪ",
    "oʊ",
    "ɔɪ",
    "tʃ",
    "dʒ",
    "ɑː",
    "iː",
    "uː",
    "ɔː",
    "eː",
]

# ── Lazy singletons ─────────────────────────────────────────────────────────
_whisper_model = None
_wav2vec2_processor = None
_wav2vec2_model = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        logger.info("Loading faster-whisper tiny for pronunciation...")
        _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        logger.info("✅ faster-whisper (pronunciation) ready")
    return _whisper_model


def _get_wav2vec2():
    global _wav2vec2_processor, _wav2vec2_model
    if _wav2vec2_model is None:
        from transformers import Wav2Vec2Processor, Wav2Vec2ForCTC

        MODEL_ID = "facebook/wav2vec2-lv-60-espeak-cv-ft"
        logger.info(f"Loading Wav2Vec2 phoneme model ({MODEL_ID})...")
        _wav2vec2_processor = Wav2Vec2Processor.from_pretrained(MODEL_ID)
        # use_safetensors=True avoids torch.load (CVE-2025-32434) without upgrading torch
        _wav2vec2_model = Wav2Vec2ForCTC.from_pretrained(MODEL_ID, use_safetensors=True)
        _wav2vec2_model.eval()
        logger.info("✅ Wav2Vec2 phoneme model ready (~370 MB)")
    return _wav2vec2_processor, _wav2vec2_model


# ── Audio decoding ───────────────────────────────────────────────────────────


def _decode_audio(audio_bytes: bytes) -> np.ndarray:
    """Any audio format → 16 kHz mono float32 array via pydub."""
    from pydub import AudioSegment

    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    samples = np.frombuffer(audio.raw_data, dtype=np.int16).astype(np.float32) / 32768.0
    return samples


# ── Phoneme helpers ──────────────────────────────────────────────────────────


def _tokenize_ipa(ipa_str: str) -> list[str]:
    """Split an IPA string into individual phoneme tokens."""
    tokens: list[str] = []
    i = 0
    while i < len(ipa_str):
        matched = False
        for mg in _MULTIGRAPHS:
            if ipa_str[i : i + len(mg)] == mg:
                tokens.append(mg)
                i += len(mg)
                matched = True
                break
        if not matched:
            ch = ipa_str[i]
            if ch not in (" ", ".", "ˈ", "ˌ", "*", "-"):
                tokens.append(ch)
            i += 1
    return tokens


def _normalize_phoneme(p: str) -> str:
    """Normalize a phoneme token to a canonical form."""
    result = ""
    for ch in p:
        result += _NORMALIZE.get(ch, ch)
    # strip length/stress leftover
    result = re.sub(r"[ːˑˈˌ]", "", result)
    return result


def _text_to_phoneme_tokens(text: str) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """
    Convert text → (flat_phoneme_list, word_boundaries).

    word_boundaries: [(word, [phoneme_tokens]), ...]

    Returns:
      all_tokens    — flat list of phonemes for the whole text
      word_details  — per-word list: [(word_str, [tokens_for_that_word])]
    """
    import eng_to_ipa as ipa

    word_details: list[tuple[str, list[str]]] = []
    all_tokens: list[str] = []

    for word in text.lower().split():
        word_clean = re.sub(r"[^a-z'-]", "", word)
        ipa_raw = ipa.convert(word_clean)
        # eng_to_ipa returns '*' for unknown words – fall back to letter spelling
        if "*" in ipa_raw:
            tokens = list(word_clean)
        else:
            tokens = _tokenize_ipa(ipa_raw)
        tokens = [_normalize_phoneme(t) for t in tokens if t]
        word_details.append((word_clean, tokens))
        all_tokens.extend(tokens)

    return all_tokens, word_details


def _get_user_phonemes(audio_array: np.ndarray) -> list[str]:
    """Run Wav2Vec2 on audio → list of eSpeak phoneme tokens."""
    import torch

    processor, model = _get_wav2vec2()
    inputs = processor(
        audio_array, sampling_rate=16000, return_tensors="pt", padding=True
    )
    with torch.no_grad():
        logits = model(**inputs).logits
    predicted_ids = torch.argmax(logits, dim=-1)
    raw = processor.batch_decode(predicted_ids)[0]
    tokens = [_normalize_phoneme(p) for p in raw.strip().split() if p]
    return [t for t in tokens if t]


# ── Sequence alignment (edit distance + backtrace) ──────────────────────────


def _align(ref: list[str], hyp: list[str]) -> list[dict]:
    """
    Levenshtein alignment between reference and hypothesis phoneme lists.

    Returns list of:
      {"expected": str|None, "actual": str|None, "correct": bool}
    """
    n, m = len(ref), len(hyp)
    # Build DP table
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref[i - 1] == hyp[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1])

    # Backtrace
    pairs: list[dict] = []
    i, j = n, m
    while i > 0 or j > 0:
        if (
            i > 0
            and j > 0
            and ref[i - 1] == hyp[j - 1]
            and dp[i][j] == dp[i - 1][j - 1]
        ):
            pairs.append(
                {"expected": ref[i - 1], "actual": hyp[j - 1], "correct": True}
            )
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            pairs.append(
                {"expected": ref[i - 1], "actual": hyp[j - 1], "correct": False}
            )
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            pairs.append({"expected": ref[i - 1], "actual": None, "correct": False})
            i -= 1
        else:
            pairs.append({"expected": None, "actual": hyp[j - 1], "correct": False})
            j -= 1

    pairs.reverse()
    return pairs


def _score_from_pairs(pairs: list[dict], ref_len: int) -> float:
    """0.0–1.0 score based on correct matches vs reference length."""
    correct = sum(1 for p in pairs if p["correct"])
    return round(correct / max(ref_len, 1), 3)


def _per_word_scores(
    word_details: list[tuple[str, list[str]]],
    global_pairs: list[dict],
) -> list[dict]:
    """
    Distribute global alignment pairs back to individual words.

    Strategy: consume pairs greedily matching each word's expected phoneme count.
    """
    result = []
    pair_idx = 0
    for word, ref_tokens in word_details:
        # Consume pairs until we've seen len(ref_tokens) expected phonemes
        word_pairs: list[dict] = []
        consumed_expected = 0
        while consumed_expected < len(ref_tokens) and pair_idx < len(global_pairs):
            p = global_pairs[pair_idx]
            word_pairs.append(p)
            pair_idx += 1
            if p["expected"] is not None:
                consumed_expected += 1

        word_score = _score_from_pairs(word_pairs, len(ref_tokens))
        result.append(
            {
                "word": word,
                "expected_ipa": "".join(ref_tokens),
                "score": word_score,
                "phonemes": word_pairs,
            }
        )
    return result


# ── Public API ───────────────────────────────────────────────────────────────


def transcribe_audio(audio_bytes: bytes) -> dict:
    """
    Transcribe audio → English text using faster-whisper.

    Returns:
      transcript   — recognized English text
      language     — detected language code (should be "en")
      duration_s   — audio length in seconds
    """
    import soundfile as sf

    arr = _decode_audio(audio_bytes)
    model = _get_whisper()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
        sf.write(f.name, arr, 16000)
        segments, info = model.transcribe(f.name, beam_size=5, language="en")
        transcript = " ".join(s.text.strip() for s in segments).strip()

    return {
        "transcript": transcript,
        "language": info.language,
        "duration_s": round(info.duration, 2),
    }


def score_pronunciation(audio_bytes: bytes, expected_text: str) -> dict:
    """
    Score pronunciation of audio against expected_text.

    Works for a single word, phrase, or full sentence.

    Returns:
      overall_score   — 0.0–1.0
      transcript      — what faster-whisper heard (sanity check)
      expected_text   — original input
      expected_ipa    — reference IPA sequence (flattened)
      actual_ipa      — phonemes recognized from audio
      phoneme_alignment — [{expected, actual, correct}, ...]  (global)
      words           — [{word, expected_ipa, score, phonemes}, ...]
    """
    import soundfile as sf

    arr = _decode_audio(audio_bytes)

    # 1. Transcribe via Whisper (for feedback / sanity)
    model = _get_whisper()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
        sf.write(f.name, arr, 16000)
        segments, _ = model.transcribe(f.name, beam_size=5, language="en")
        transcript = " ".join(s.text.strip() for s in segments).strip()

    # 2. Get user phonemes via Wav2Vec2
    user_phonemes = _get_user_phonemes(arr)

    # 3. Get reference phonemes from expected_text
    ref_phonemes, word_details = _text_to_phoneme_tokens(expected_text)

    # 4. Global alignment
    global_pairs = _align(ref_phonemes, user_phonemes)
    overall_score = _score_from_pairs(global_pairs, len(ref_phonemes))

    # 5. Per-word breakdown
    words = _per_word_scores(word_details, global_pairs)

    return {
        "overall_score": overall_score,
        "transcript": transcript,
        "expected_text": expected_text,
        "expected_ipa": "".join(ref_phonemes),
        "actual_ipa": " ".join(user_phonemes),
        "phoneme_alignment": global_pairs,
        "words": words,
    }
