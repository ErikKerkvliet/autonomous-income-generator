# app/tests/test_module_loader.py
"""
Unit tests for the ModuleLoader.
"""
import os
import sys
import unittest
import tempfile
import shutil
from app.core.module_loader import ModuleLoader


class TestModuleLoader(unittest.TestCase):
    """Test cases for the ModuleLoader."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test modules
        self.temp_dir = tempfile.mkdtemp()

        # Create a test strategy directory structure
        self.test_strategy_dir = os.path.join(self.temp_dir, "test_strategy")
        os.makedirs(self.test_strategy_dir)

        # Create a main.py file with a test strategy class
        with open(os.path.join(self.test_strategy_dir, "main.py"), "w") as f:
            f.write("""
class TestStrategy:
    STRATEGY_NAME = "Test Strategy"
    STRATEGY_DESCRIPTION = "A test strategy for unit tests"

    def __init__(self, config, monitoring, db_manager, finance_manager):
        self.config = config
        self.monitoring = monitoring
        self.db_manager = db_manager
        self.finance_manager = finance_manager

    def run(self):
        return {
            'success': True,
            'income': 100.0,
            'currency': 'USD',
            'description': 'Test income',
            'details': {}
        }
""")

        # Add the temp directory to the Python path
        sys.path.insert(0, self.temp_dir)

        # Initialize the module loader
        self.module_loader = ModuleLoader(self.temp_dir)

    def tearDown(self):
        """Clean up after tests."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)

        # Remove the temp directory from the Python path
        sys.path.remove(self.temp_dir)

    def test_discover_strategies(self):
        """Test discovering strategies."""
        # Call the discover_strategies method
        strategies = self.module_loader.discover_strategies()

        # Check that the test strategy was discovered
        self.assertIn("test_strategy", strategies)
        self.assertEqual(strategies["test_strategy"]["name"], "Test Strategy")
        self.assertEqual(
            strategies["test_strategy"]["description"],
            "A test strategy for unit tests"
        )

    def test_load_strategy(self):
        """Test loading a strategy."""
        # First discover strategies
        self.module_loader.discover_strategies()

        # Then load the test strategy
        strategy_class = self.module_loader.load_strategy("test_strategy")

        # Check that the strategy class was loaded
        self.assertIsNotNone(strategy_class)
        self.assertEqual(strategy_class.STRATEGY_NAME, "Test Strategy")
        self.assertEqual(
            strategy_class.STRATEGY_DESCRIPTION,
            "A test strategy for unit tests"
        )

    def test_load_nonexistent_strategy(self):
        """Test loading a non-existent strategy."""
        # Try to load a non-existent strategy
        strategy_class = self.module_loader.load_strategy("nonexistent")

        # Check that the result is None
        self.assertIsNone(strategy_class)
