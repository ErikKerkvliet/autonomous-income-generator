# app/tests/test_strategy_base.py
"""
Unit tests for the IncomeStrategy base class.
"""
import unittest
from unittest.mock import MagicMock
from app.income_strategies.strategy_base import IncomeStrategy


class TestIncomeStrategy(unittest.TestCase):
    """Test cases for the IncomeStrategy base class."""

    def setUp(self):
        """Set up test environment."""
        # Create mock dependencies
        self.mock_config = MagicMock()
        self.mock_monitoring = MagicMock()
        self.mock_db_manager = MagicMock()
        self.mock_finance_manager = MagicMock()

        # Create a concrete implementation of the abstract base class
        class ConcreteStrategy(IncomeStrategy):
            STRATEGY_NAME = "Test Strategy"
            STRATEGY_DESCRIPTION = "Test strategy for unit tests"

            def run(self):
                return {
                    'success': True,
                    'income': 50.0,
                    'currency': 'USD',
                    'description': 'Test income',
                    'details': {}
                }

        # Initialize the concrete strategy
        self.strategy = ConcreteStrategy(
            self.mock_config,
            self.mock_monitoring,
            self.mock_db_manager,
            self.mock_finance_manager
        )

    def test_strategy_initialization(self):
        """Test strategy initialization."""
        # Check that the strategy name and description are set
        self.assertEqual(self.strategy.STRATEGY_NAME, "Test Strategy")
        self.assertEqual(self.strategy.STRATEGY_DESCRIPTION, "Test strategy for unit tests")

        # Check that dependencies are properly assigned
        self.assertEqual(self.strategy.config, self.mock_config)
        self.assertEqual(self.strategy.monitoring, self.mock_monitoring)
        self.assertEqual(self.strategy.db_manager, self.mock_db_manager)
        self.assertEqual(self.strategy.finance_manager, self.mock_finance_manager)

    def test_run_method(self):
        """Test the run method."""
        # Call the run method
        result = self.strategy.run()

        # Check the result
        self.assertTrue(result['success'])
        self.assertEqual(result['income'], 50.0)
        self.assertEqual(result['currency'], 'USD')
        self.assertEqual(result['description'], 'Test income')

    def test_log_methods(self):
        """Test the logging methods."""
        # Call the log methods
        self.strategy.log_info("Info message")
        self.strategy.log_warning("Warning message")
        self.strategy.log_error("Error message")

        # Check that the monitoring methods were called
        self.mock_monitoring.record_event.assert_any_call(
            "info", "Test Strategy", "Info message"
        )
        self.mock_monitoring.record_event.assert_any_call(
            "warning", "Test Strategy", "Warning message"
        )
        self.mock_monitoring.record_event.assert_any_call(
            "error", "Test Strategy", "Error message"
        )

