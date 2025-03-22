# app/tests/test_simulated_strategy.py
"""
Unit tests for income generation strategies with simulated funds.
"""
import unittest
from unittest.mock import MagicMock, patch
from app.income_strategies.content_creation.main import ContentCreationStrategy


class TestSimulatedContentCreationStrategy(unittest.TestCase):
    """Test cases for the ContentCreationStrategy with simulated funds."""

    def setUp(self):
        """Set up test environment."""
        # Create mock dependencies
        self.mock_config = MagicMock()
        self.mock_monitoring = MagicMock()
        self.mock_db_manager = MagicMock()
        self.mock_finance_manager = MagicMock()
        self.mock_api_manager = MagicMock()

        # Mock config values
        self.mock_config.get.return_value = "fiction"
        self.mock_config.get_website_credentials.return_value = {
            "username": "test_user",
            "password": "test_pass"
        }

        # Create a patch for the APIManager
        self.api_manager_patch = patch(
            'app.managers.api_manager.APIManager',
            return_value=self.mock_api_manager
        )
        self.api_manager_patch.start()

        # Initialize the strategy
        self.strategy = ContentCreationStrategy(
            self.mock_config,
            self.mock_monitoring,
            self.mock_db_manager,
            self.mock_finance_manager
        )

        # Replace the browser_manager with a mock
        self.strategy.browser_manager = MagicMock()

    def tearDown(self):
        """Clean up after tests."""
        self.api_manager_patch.stop()

    def test_generate_content_idea(self):
        """Test generating a content idea."""
        # Mock the API response
        self.mock_api_manager.generate_text.return_value = """
        {
            "title": "Test Series",
            "synopsis": "A test synopsis",
            "characters": [
                {
                    "name": "Character 1",
                    "description": "A test character"
                }
            ],
            "plot_points": [
                "Plot point 1",
                "Plot point 2"
            ]
        }
        """

        # Call the method
        result = self.strategy._generate_content_idea()

        # Check the result
        self.assertEqual(result["title"], "Test Series")
        self.assertEqual(result["synopsis"], "A test synopsis")

        # Check that the API was called
        self.mock_api_manager.generate_text.assert_called_once()

    def test_simulated_content_publishing(self):
        """Test simulated content publishing."""
        # Mock database queries
        self.mock_db_manager.query.return_value = None

        # Set up other mocks
        self.mock_api_manager.generate_text.return_value = """
        {
            "title": "Test Series",
            "synopsis": "A test synopsis"
        }
        """

        # Mock browser
        mock_browser = MagicMock()
        self.strategy.browser_manager.get_browser.return_value = mock_browser

        # Run the strategy
        result = self.strategy.run()

        # Check the result
        self.assertTrue(result['success'])
        self.assertGreaterEqual(result['income'], 0)
        self.assertEqual(result['currency'], 'USD')

        # Check that the finance manager was not called (simulated mode)
        self.mock_finance_manager.add_income.assert_not_called()
