"""
IELTS Question Scoring Logic
Handles scoring for 6 IELTS question types with flexible answer matching
"""

import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def normalize_text(text: str, case_sensitive: bool = False) -> str:
    """
    Normalize text for comparison

    Args:
        text: Text to normalize
        case_sensitive: Whether to preserve case

    Returns:
        Normalized text
    """
    if not isinstance(text, str):
        text = str(text)

    # Remove extra whitespace
    text = " ".join(text.split())

    # Convert to lowercase if not case-sensitive
    if not case_sensitive:
        text = text.lower()

    return text.strip()


def score_mcq_question(
    question: Dict[str, Any], user_answer: Dict[str, Any]
) -> Tuple[bool, int, str]:
    """
    Score MCQ question (Multiple Choice)

    Args:
        question: Question data with correct_answer_keys
        user_answer: User's answer with selected_answer_keys

    Returns:
        (is_correct, points_earned, feedback)
    """
    correct_answers = question.get("correct_answer_keys", [])
    if not correct_answers and "correct_answer_key" in question:
        correct_answers = [question["correct_answer_key"]]

    # Get user's selected answers
    selected_answers = user_answer.get("selected_answer_keys", [])
    if not selected_answers and "selected_answer_key" in user_answer:
        selected_answers = [user_answer["selected_answer_key"]]

    # All-or-nothing scoring: user must select ALL correct answers
    is_correct = (
        set(selected_answers) == set(correct_answers)
        if (correct_answers and selected_answers)
        else False
    )

    max_points = question.get("max_points", 1)
    points_earned = max_points if is_correct else 0

    feedback = ""
    if is_correct:
        feedback = "Correct!"
    else:
        feedback = f"Incorrect. Correct answer(s): {', '.join(correct_answers)}"

    return is_correct, points_earned, feedback


def score_matching_question(
    question: Dict[str, Any], user_answer: Dict[str, Any]
) -> Tuple[bool, int, str]:
    """
    Score Matching question

    Args:
        question: Question data with correct_answers [{'left_key': '1', 'right_key': 'A'}, ...] or {'1': 'A', ...}
        user_answer: User's matches {'1': 'A', '2': 'C', ...}

    Returns:
        (is_correct, points_earned, feedback)
    """
    # Use correct_answers (unified field), fallback to correct_matches (legacy)
    correct_matches_raw = question.get("correct_answers") or question.get(
        "correct_matches", {}
    )

    # Convert array format to dict if needed
    if isinstance(correct_matches_raw, list):
        correct_matches = {
            item["left_key"]: item["right_key"] for item in correct_matches_raw
        }
    else:
        correct_matches = correct_matches_raw

    user_matches = user_answer.get("matches", {})

    if not correct_matches or not user_matches:
        return False, 0, "No answer provided"

    # Count correct matches
    total_items = len(correct_matches)
    correct_count = 0

    for key, correct_value in correct_matches.items():
        user_value = user_matches.get(key)
        if user_value == correct_value:
            correct_count += 1

    # Calculate points (proportional)
    max_points = question.get("max_points", total_items)
    points_earned = round((correct_count / total_items) * max_points, 2)

    is_correct = correct_count == total_items

    feedback = f"{correct_count}/{total_items} matches correct"
    if not is_correct:
        feedback += f". Score: {points_earned}/{max_points} points"

    return is_correct, points_earned, feedback


def score_completion_question(
    question: Dict[str, Any], user_answer: Dict[str, Any]
) -> Tuple[bool, int, str]:
    """
    Score Completion question (Form/Note/Table completion)

    Flexible matching:
    - Case-insensitive by default
    - Multiple acceptable answers
    - Whitespace normalized

    Args:
        question: Question data with correct_answers [{'blank_key': '1', 'answers': ['ans1', 'ans2']}, ...] or {'1': ['ans1', 'ans2'], ...}
        user_answer: User's answers {'1': 'answer1', '2': 'some text', ...}

    Returns:
        (is_correct, points_earned, feedback)
    """
    correct_answers_raw = question.get("correct_answers", {})

    # Convert array format to dict if needed
    if isinstance(correct_answers_raw, list):
        correct_answers = {
            item["blank_key"]: item["answers"] for item in correct_answers_raw
        }
    else:
        correct_answers = correct_answers_raw

    user_answers = user_answer.get("answers", {})
    case_sensitive = question.get("case_sensitive", False)

    if not correct_answers or not user_answers:
        return False, 0, "No answer provided"

    total_blanks = len(correct_answers)
    correct_count = 0
    incorrect_blanks = []

    for blank_key, acceptable_answers in correct_answers.items():
        user_text = user_answers.get(blank_key, "")

        # Normalize user answer
        normalized_user = normalize_text(user_text, case_sensitive)

        # Check if user answer matches any acceptable answer
        is_match = False
        for acceptable in acceptable_answers:
            normalized_acceptable = normalize_text(acceptable, case_sensitive)
            if normalized_user == normalized_acceptable:
                is_match = True
                break

        if is_match:
            correct_count += 1
        else:
            incorrect_blanks.append(blank_key)

    # Calculate points (proportional)
    max_points = question.get("max_points", total_blanks)
    points_earned = round((correct_count / total_blanks) * max_points, 2)

    is_correct = correct_count == total_blanks

    feedback = f"{correct_count}/{total_blanks} blanks correct"
    if not is_correct:
        feedback += f". Score: {points_earned}/{max_points} points"

    return is_correct, points_earned, feedback


def score_sentence_completion_question(
    question: Dict[str, Any], user_answer: Dict[str, Any]
) -> Tuple[bool, int, str]:
    """
    Score Sentence Completion question

    Similar to completion but each sentence is a separate sub-question

    Args:
        question: Question data with sentences [{'key': '1', 'correct_answers': ['ans1']}, ...]
        user_answer: User's answers {'1': 'answer1', '2': 'answer2', ...}

    Returns:
        (is_correct, points_earned, feedback)
    """
    sentences = question.get("sentences", [])
    user_answers = user_answer.get("answers", {})
    case_sensitive = question.get("case_sensitive", False)

    if not sentences or not user_answers:
        return False, 0, "No answer provided"

    total_sentences = len(sentences)
    correct_count = 0

    for sentence in sentences:
        sentence_key = sentence.get("key")
        acceptable_answers = sentence.get("correct_answers", [])
        user_text = user_answers.get(sentence_key, "")

        # Normalize user answer
        normalized_user = normalize_text(user_text, case_sensitive)

        # Check if user answer matches any acceptable answer
        is_match = False
        for acceptable in acceptable_answers:
            normalized_acceptable = normalize_text(acceptable, case_sensitive)
            if normalized_user == normalized_acceptable:
                is_match = True
                break

        if is_match:
            correct_count += 1

    # Calculate points (proportional)
    max_points = question.get("max_points", total_sentences)
    points_earned = round((correct_count / total_sentences) * max_points, 2)

    is_correct = correct_count == total_sentences

    feedback = f"{correct_count}/{total_sentences} sentences correct"
    if not is_correct:
        feedback += f". Score: {points_earned}/{max_points} points"

    return is_correct, points_earned, feedback


def score_short_answer_question(
    question: Dict[str, Any], user_answer: Dict[str, Any]
) -> Tuple[bool, int, str]:
    """
    Score Short Answer question

    Similar to sentence completion but for direct questions

    Args:
        question: Question data with questions [{'key': '1', 'correct_answers': ['ans1']}, ...]
        user_answer: User's answers {'1': 'answer1', '2': 'answer2', ...}

    Returns:
        (is_correct, points_earned, feedback)
    """
    questions_list = question.get("questions", [])
    user_answers = user_answer.get("answers", {})
    case_sensitive = question.get("case_sensitive", False)

    if not questions_list or not user_answers:
        return False, 0, "No answer provided"

    total_questions = len(questions_list)
    correct_count = 0

    for q in questions_list:
        q_key = q.get("key")
        acceptable_answers = q.get("correct_answers", [])
        user_text = user_answers.get(q_key, "")

        # Normalize user answer
        normalized_user = normalize_text(user_text, case_sensitive)

        # Check if user answer matches any acceptable answer
        is_match = False
        for acceptable in acceptable_answers:
            normalized_acceptable = normalize_text(acceptable, case_sensitive)
            if normalized_user == normalized_acceptable:
                is_match = True
                break

        if is_match:
            correct_count += 1

    # Calculate points (proportional)
    max_points = question.get("max_points", total_questions)
    points_earned = round((correct_count / total_questions) * max_points, 2)

    is_correct = correct_count == total_questions

    feedback = f"{correct_count}/{total_questions} questions correct"
    if not is_correct:
        feedback += f". Score: {points_earned}/{max_points} points"

    return is_correct, points_earned, feedback


def score_map_labeling_question(
    question: Dict[str, Any], user_answer: Dict[str, Any]
) -> Tuple[bool, int, str]:
    """
    Score Map/Diagram Labeling question

    Same logic as matching (label positions to options)

    Args:
        question: Question data with correct_answers [{'label_key': '1', 'option_key': 'A'}, ...] or correct_labels {'1': 'A', ...} (legacy)
        user_answer: User's labels {'1': 'A', '2': 'C', ...}

    Returns:
        (is_correct, points_earned, feedback)
    """
    # Use correct_answers (unified field), fallback to correct_labels (legacy)
    correct_labels_raw = question.get("correct_answers") or question.get(
        "correct_labels", {}
    )

    # Convert array format to dict if needed
    if isinstance(correct_labels_raw, list):
        correct_labels = {
            item.get("label_key")
            or item.get("position_key"): item.get("option_key")
            or item.get("label")
            for item in correct_labels_raw
        }
    else:
        correct_labels = correct_labels_raw

    user_labels = user_answer.get("labels", {})

    if not correct_labels or not user_labels:
        return False, 0, "No answer provided"

    # Count correct labels
    total_positions = len(correct_labels)
    correct_count = 0

    for key, correct_value in correct_labels.items():
        user_value = user_labels.get(key)
        if user_value == correct_value:
            correct_count += 1

    # Calculate points (proportional)
    max_points = question.get("max_points", total_positions)
    points_earned = round((correct_count / total_positions) * max_points, 2)

    is_correct = correct_count == total_positions

    feedback = f"{correct_count}/{total_positions} labels correct"
    if not is_correct:
        feedback += f". Score: {points_earned}/{max_points} points"

    return is_correct, points_earned, feedback


def score_question(
    question: Dict[str, Any], user_answer: Dict[str, Any]
) -> Tuple[bool, int, str]:
    """
    Score a question based on its type

    Routes to appropriate scoring function based on question_type

    Args:
        question: Question data from database
        user_answer: User's answer data

    Returns:
        (is_correct, points_earned, feedback)
    """
    question_type = question.get("question_type", "mcq")

    try:
        if question_type == "mcq":
            return score_mcq_question(question, user_answer)

        elif question_type == "matching":
            return score_matching_question(question, user_answer)

        elif question_type == "completion":
            return score_completion_question(question, user_answer)

        elif question_type == "sentence_completion":
            return score_sentence_completion_question(question, user_answer)

        elif question_type == "short_answer":
            return score_short_answer_question(question, user_answer)

        elif question_type == "map_labeling":
            return score_map_labeling_question(question, user_answer)

        elif question_type == "essay":
            # Essay questions cannot be auto-scored
            return False, 0, "Essay requires manual grading"

        else:
            logger.warning(f"Unknown question type: {question_type}")
            return False, 0, f"Unknown question type: {question_type}"

    except Exception as e:
        logger.error(f"Error scoring question: {e}", exc_info=True)
        return False, 0, f"Scoring error: {str(e)}"


def get_answer_format_for_type(question_type: str) -> Dict[str, Any]:
    """
    Get expected answer format for a question type

    Useful for validation and frontend guidance

    Args:
        question_type: Type of question

    Returns:
        Example answer structure
    """
    formats = {
        "mcq": {
            "question_id": "q1",
            "question_type": "mcq",
            "selected_answer_keys": ["A"],
        },
        "matching": {
            "question_id": "q2",
            "question_type": "matching",
            "matches": {"1": "A", "2": "C", "3": "B"},
        },
        "completion": {
            "question_id": "q3",
            "question_type": "completion",
            "answers": {"1": "John Smith", "2": "25", "3": "Engineer"},
        },
        "sentence_completion": {
            "question_id": "q4",
            "question_type": "sentence_completion",
            "answers": {"1": "8 AM", "2": "5 books"},
        },
        "short_answer": {
            "question_id": "q5",
            "question_type": "short_answer",
            "answers": {"1": "Software Engineer", "2": "5 years", "3": "Python"},
        },
        "map_labeling": {
            "question_id": "q6",
            "question_type": "map_labeling",
            "labels": {"1": "A", "2": "C", "3": "B"},
        },
        "essay": {
            "question_id": "q7",
            "question_type": "essay",
            "answer_text": "Essay answer text here...",
            "media_attachments": [],  # Optional
        },
    }

    return formats.get(question_type, {})
