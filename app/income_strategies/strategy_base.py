# app/income_strategies/strategy_base.py
"""
Base class for income generation strategies.

All income strategies should inherit from this class and implement
the required methods.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import time
import random


class IncomeStrategy(ABC):
    """
    Abstract base class for income generation strategies.
    """

    # Strategy metadata
    STRATEGY_NAME = "Base Strategy"
    STRATEGY_DESCRIPTION = "Abstract base class for income strategies"

    # Default run interval in minutes
    run_interval = 60

    def __init__(self, config, monitoring, db_manager, finance_manager):
        """
        Initialize the income strategy.

        Args:
            config: Configuration manager instance
            monitoring: Monitoring system instance
            db_manager: Database manager instance
            finance_manager: Finance manager instance
        """
        self.config = config
        self.monitoring = monitoring
        self.db_manager = db_manager
        self.finance_manager = finance_manager
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Initialize strategy-specific resources
        self._initialize()

    def _initialize(self) -> None:
        """
        Initialize strategy-specific resources.
        This method can be overridden by subclasses.
        """
        pass

    @abstractmethod
    def run(self) -> Dict[str, Any]:
        """
        Execute the income generation strategy.

        Returns:
            Dictionary containing the result of the execution:
            {
                'success': bool,
                'income': float,
                'currency': str,
                'description': str,
                'details': dict
            }
        """
        pass

    def cleanup(self) -> None:
        """
        Cleanup strategy resources.
        This method can be overridden by subclasses.
        """
        pass

    def log_info(self, message: str) -> None:
        """
        Log an informational message and record it in monitoring.

        Args:
            message: Message to log
        """
        self.logger.info(message)
        self.monitoring.record_event("info", self.STRATEGY_NAME, message)

    def log_warning(self, message: str) -> None:
        """
        Log a warning message and record it in monitoring.

        Args:
            message: Message to log
        """
        self.logger.warning(message)
        self.monitoring.record_event("warning", self.STRATEGY_NAME, message)

    def log_error(self, message: str) -> None:
        """
        Log an error message and record it in monitoring.

        Args:
            message: Message to log
        """
        self.logger.error(message)
        self.monitoring.record_event("error", self.STRATEGY_NAME, message)

    def random_delay(self, min_seconds: int = 1, max_seconds: int = 5) -> None:
        """
        Add a random delay to mimic human behavior.

        Args:
            min_seconds: Minimum delay in seconds
            max_seconds: Maximum delay in seconds
        """
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)