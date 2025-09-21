"""
AI Sales Agent for Banking Loan Assessment

A flexible conversation system for automating loan application conversations
with Vietnamese language support and priority-based data collection.

Components:
- AI Provider: Flexible information extraction and response generation
- NLG (Natural Language Generation): Generate contextual questions and responses  
- API: FastAPI endpoints for conversation management
- Services: Core business logic for loan assessment

Usage:
    from ai_sales_agent.api.routes import router
    from ai_sales_agent.nlg.generator import NLGGenerator
"""

# Import main components
from .nlg.generator import NLGGenerator
from .api.routes import router

__version__ = "1.0.0"

__all__ = [
    'NLUProcessor',
    'NLGGenerator', 
    'router',
    'NLURequest',
    'NLUResponse',
    'StepSubQuestion',
    'STEP_CONFIGS'
]
