# app/tests/test_config.py
"""
Unit tests for the ConfigManager.
"""
import os
import unittest
import tempfile
from app.core.config_manager import ConfigManager


class TestConfigManager(unittest.TestCase):
    """Test cases for the ConfigManager."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary .env file for testing
        self.temp_env = tempfile.NamedTemporaryFile(delete=False)
        self.temp_env.write(b"""
        FINANCIAL_BTC_BALANCE=500.0
        LLM_API_CLAUDE_API_KEY=test_api_key
        STRATEGIES_CONTENT_CREATION_ENABLED=true
        WEBSITE_CREDENTIALS_UPWORK_USERNAME=test_user
        WEBSITE_CREDENTIALS_UPWORK_PASSWORD=test_pass
        """)
        self.temp_env.close()

        # Initialize the config manager with the temporary file
        self.config = ConfigManager(self.temp_env.name)

    def tearDown(self):
        """Clean up after tests."""
        # Remove the temporary file
        os.unlink(self.temp_env.name)

    def test_get_config_value(self):
        """Test getting configuration values."""
        # Test getting a simple configuration value
        btc_balance = self.config.get("FINANCIAL", "BTC_BALANCE", "0.0")
        self.assertEqual(btc_balance, "500.0")

        # Test getting a value with a default
        amazon_balance = self.config.get("FINANCIAL", "AMAZON_BALANCE", "0.0")
        self.assertEqual(amazon_balance, "0.0")

        # Test getting an API key
        api_key = self.config.get("LLM_API", "CLAUDE_API_KEY", "")
        self.assertEqual(api_key, "test_api_key")

    def test_get_all_config_category(self):
        """Test getting all configuration values in a category."""
        # Get all financial configs
        financial_configs = self.config.get_all("FINANCIAL")
        self.assertIn("BTC_BALANCE", financial_configs)
        self.assertEqual(financial_configs["BTC_BALANCE"], "500.0")

    def test_get_website_credentials(self):
        """Test getting website credentials."""
        # Get Upwork credentials
        credentials = self.config.get_website_credentials("UPWORK")
        self.assertIsNotNone(credentials)
        self.assertEqual(credentials["username"], "test_user")
        self.assertEqual(credentials["password"], "test_pass")

        # Test getting non-existent credentials
        credentials = self.config.get_website_credentials("NONEXISTENT")
        self.assertEqual(credentials, {})

    def test_is_strategy_enabled(self):
        """Test checking if strategies are enabled."""
        # Test an enabled strategy
        self.assertTrue(self.config.is_strategy_enabled("CONTENT_CREATION"))

        # Test a non-existent strategy (should default to False)
        self.assertFalse(self.config.is_strategy_enabled("NONEXISTENT"))

