"""
Natural Language Generation module for AI Sales Agent

This module handles question generation, conversation flow management,
and response formatting for the banking loan assessment process.
"""

from .generator import NLGGenerator
from .question_templates import (
    STEP_1_1_TEMPLATES,
    STEP_1_2_TEMPLATES, 
    STEP_2_1_TEMPLATES,
    STEP_2_2_TEMPLATES,
    FIELD_DISPLAY_NAMES,
    FIELD_SUGGESTIONS,
    FIELD_EXAMPLES
)

__all__ = [
    'NLGGenerator',
    'STEP_1_1_TEMPLATES',
    'STEP_1_2_TEMPLATES',
    'STEP_2_1_TEMPLATES', 
    'STEP_2_2_TEMPLATES',
    'FIELD_DISPLAY_NAMES',
    'FIELD_SUGGESTIONS',
    'FIELD_EXAMPLES'
]
