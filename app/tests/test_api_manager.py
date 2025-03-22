# app/tests/test_api_manager.py
"""
Unit tests for the APIManager using the local Gemma model.
"""
import unittest
from unittest.mock import MagicMock, patch
import requests
from app.managers.api_manager import APIManager


class TestAPIManager(unittest.TestCase):
    """Test cases for the APIManager."""

    def setUp(self):
        """Set up test environment."""
        # Create mock config
        self.mock_config = MagicMock()

        # Configure the mock to return appropriate values
        self.mock_config.get.side_effect = self._mock_get_config

        # Initialize the API manager
        self.api_manager = APIManager(self.mock_config)

        # Replace the actual API calls with mocks
        self.api_manager._generate_with_local_gemma = MagicMock(
            return_value="Test response from local Gemma"
        )

    def _mock_get_config(self, category, key, default=None):
        """
        Mock implementation of config.get.

        Args:
            category: Configuration category
            key: Configuration key
            default: Default value

        Returns:
            Configuration value
        """
        if category == "LLM_API" and key == "USE_LOCAL_GEMMA":
            return "true"
        elif category == "LLM_API" and key == "DEFAULT_MODEL":
            return "gemma"
        elif category == "LLM_API" and key == "TEMPERATURE":
            return "0.7"
        elif category == "LLM_API" and key == "RATE_LIMIT_DELAY":
            return "0.1"
        elif category == "LLM_API" and key == "LOCAL_GEMMA_ENDPOINT":
            return "http://localhost:8000/generate"
        return default

    def test_generate_text_with_local_gemma(self):
        """Test generating text with the local Gemma model."""
        # Call generate_text
        response = self.api_manager.generate_text(
            "Test prompt",
            model="gemma",
            max_tokens=100,
            temperature=0.5
        )

        # Check the response
        self.assertEqual(response, "Test response from local Gemma")

        # Check that the local Gemma method was called
        self.api_manager._generate_with_local_gemma.assert_called_once_with(
            "Test prompt", 100, 0.5, None
        )

    @patch('requests.post')
    def test_generate_with_local_gemma_integration(self, mock_post):
        """Test the integration with the local Gemma model."""
        # Set up the mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Generated text from Gemma"}
        mock_post.return_value = mock_response

        # Restore the original method
        self.api_manager._generate_with_local_gemma = APIManager._generate_with_local_gemma.__get__(
            self.api_manager, APIManager
        )

        # Call generate_text
        response = self.api_manager.generate_text(
            "Test prompt",
            model="gemma",
            max_tokens=100,
            temperature=0.5
        )

        # Check the response
        self.assertEqual(response, "Generated text from Gemma")

        # Check that the requests.post method was called with the correct arguments
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "http://localhost:8000/generate")
        self.assertEqual(kwargs["json"]["prompt"], "User: Test prompt\n\nAssistant:")
        self.assertEqual(kwargs["json"]["max_tokens"], 100)
        self.assertEqual(kwargs["json"]["temperature"], 0.5)

    @patch('requests.post')
    def test_error_handling(self, mock_post):
        """Test error handling in API calls."""
        # Set up the mock to raise an exception
        mock_post.side_effect = requests.exceptions.RequestException("Test error")

        # Restore the original method
        self.api_manager._generate_with_local_gemma = APIManager._generate_with_local_gemma.__get__(
            self.api_manager, APIManager
        )

        # Call generate_text
        response = self.api_manager.generate_text(
            "Test prompt",
            model="gemma",
            max_tokens=100,
            temperature=0.5
        )

        # Check that the response contains an error message
        self.assertIn("I apologize", response)
        self.assertIn("error", response.lower())
