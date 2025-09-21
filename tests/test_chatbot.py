import pytest
from unittest.mock import patch, MagicMock
from src.rag.chatbot import Chatbot

class TestChatbot:
    @patch('src.rag.chatbot.requests.post')
    def test_generate_response(self, mock_post):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}]
        }
        mock_post.return_value = mock_response
        
        # Test
        chatbot = Chatbot(api_key="test_key")
        response = chatbot.generate_response("test query")
        
        assert response == "Test response"
        mock_post.assert_called_once()
