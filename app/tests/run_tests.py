# app/tests/run_tests.py
"""
Script to run all unit tests for the Autonomous Income Generator.
"""
import unittest
import sys
import os


def run_tests():
    """
    Discover and run all unit tests.

    Returns:
        True if all tests pass, False otherwise
    """
    # Add the parent directory to the path for imports
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

    # Discover all tests in the tests directory
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    suite = loader.discover(start_dir, pattern="test_*.py")

    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Return True if all tests pass, False otherwise
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)