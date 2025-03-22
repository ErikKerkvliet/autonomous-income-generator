# app/core/app_controller.py
"""
Application Controller for the Autonomous Income Generator

This module serves as the main entry point and orchestrator for the application.
"""
import logging
import threading
import time
import schedule
from typing import Dict, List, Any, Optional
import importlib

from app.core.config_manager import ConfigManager
from app.core.monitoring import MonitoringSystem
from app.core.module_loader import ModuleLoader
from app.managers.db_manager import DatabaseManager
from app.managers.finance_manager import FinanceManager


class AppController:
    """
    Main application controller that orchestrates all components.
    """

    def __init__(self, config_path: str = ".env"):
        """
        Initialize the application controller.

        Args:
            config_path: Path to the configuration file
        """
        # Set up logger
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing Autonomous Income Generator")

        # Load configuration
        self.config_manager = ConfigManager(config_path)

        # Initialize monitoring system
        self.monitoring = MonitoringSystem(
            enable_web=True,
            web_port=int(self.config_manager.get("MONITORING", "WEB_PORT", 8080))
        )

        # Initialize module loader
        self.module_loader = ModuleLoader()

        # Initialize database manager
        db_config = self.config_manager.get_all("DATABASE")
        self.db_manager = DatabaseManager(
            host=db_config.get("HOST", "localhost"),
            port=int(db_config.get("PORT", 3306)),
            user=db_config.get("USER", "root"),
            password=db_config.get("PASSWORD", ""),
            database=db_config.get("NAME", "income_generator")
        )

        # Initialize finance manager
        self.finance_manager = FinanceManager(
            self.db_manager,
            btc_balance=float(self.config_manager.get("FINANCIAL", "BTC_BALANCE", 0)),
            amazon_balance=float(self.config_manager.get("FINANCIAL", "AMAZON_BALANCE", 0)),
            amazon_currency=self.config_manager.get("FINANCIAL", "AMAZON_CURRENCY", "EUR")
        )

        # Store active strategy instances
        self.strategies = {}

        # Flag to control the main loop
        self.running = False

    def start(self) -> None:
        """
        Start the application.
        """
        self.logger.info("Starting Autonomous Income Generator")

        # Discover available strategies
        available_strategies = self.module_loader.discover_strategies()
        self.logger.info(f"Found {len(available_strategies)} available strategies")

        # Load enabled strategies
        for strategy_name in available_strategies:
            if self.config_manager.is_strategy_enabled(strategy_name):
                self.load_strategy(strategy_name)

        # Start the main loop in a separate thread
        self.running = True
        threading.Thread(target=self._main_loop, daemon=True).start()

        # Record application start event
        self.monitoring.record_event(
            "info",
            "AppController",
            "Application started successfully"
        )

        # Block main thread until interrupted
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def _main_loop(self) -> None:
        """
        Main application loop for scheduling and running tasks.
        """
        # Set up scheduling
        for strategy_name, strategy in self.strategies.items():
            # Schedule strategy execution based on its run_interval
            run_interval = getattr(strategy, 'run_interval', 60)  # Default to 60 mins

            schedule.every(run_interval).minutes.do(
                self._execute_strategy, strategy_name
            )

            self.logger.info(
                f"Scheduled strategy '{strategy_name}' to run every {run_interval} minutes"
            )

        # Schedule finance update
        schedule.every(30).minutes.do(self._update_finances)

        # Run initial strategy execution
        for strategy_name in self.strategies:
            self._execute_strategy(strategy_name)

        # Initial finance update
        self._update_finances()

        # Main scheduling loop
        while self.running:
            schedule.run_pending()
            time.sleep(1)

    def _execute_strategy(self, strategy_name: str) -> None:
        """
        Execute a specific strategy.

        Args:
            strategy_name: Name of the strategy to execute
        """
        if strategy_name not in self.strategies:
            self.logger.warning(f"Strategy '{strategy_name}' not found")
            return

        strategy = self.strategies[strategy_name]
        self.logger.info(f"Executing strategy: {strategy_name}")

        try:
            # Run the strategy
            result = strategy.run()

            # Update monitoring
            self.monitoring.record_metric(
                "strategy_execution",
                strategy_name,
                1 if result.get('success', False) else 0
            )

            # Record income if generated
            income = result.get('income', 0)
            if income > 0:
                self.monitoring.record_income(
                    strategy_name,
                    income,
                    result.get('currency', 'USD'),
                    result.get('description', 'Income generated')
                )

                # Update finances
                self.finance_manager.add_income(
                    source=strategy_name,
                    amount=income,
                    currency=result.get('currency', 'USD'),
                    description=result.get('description', 'Income generated')
                )

            self.logger.info(f"Strategy '{strategy_name}' executed successfully")
        except Exception as e:
            self.logger.error(f"Error executing strategy '{strategy_name}': {str(e)}")
            self.monitoring.record_event(
                "error",
                f"Strategy:{strategy_name}",
                f"Execution error: {str(e)}"
            )

    def _update_finances(self) -> None:
        """
        Update financial status in monitoring.
        """
        finances = self.finance_manager.get_summary()

        # Record metrics for monitoring
        self.monitoring.record_metric(
            "finances", "total_income", finances['total_income']
        )
        self.monitoring.record_metric(
            "finances", "btc_balance", finances['btc_balance']
        )
        self.monitoring.record_metric(
            "finances", "amazon_balance", finances['amazon_balance']
        )

        self.logger.debug("Financial status updated in monitoring")

    def load_strategy(self, strategy_name: str) -> bool:
        """
        Load and initialize a strategy.

        Args:
            strategy_name: Name of the strategy to load

        Returns:
            True if the strategy was loaded successfully, False otherwise
        """
        strategy_class = self.module_loader.load_strategy(strategy_name)

        if not strategy_class:
            self.logger.error(f"Failed to load strategy: {strategy_name}")
            return False

        try:
            # Initialize strategy with dependencies
            strategy = strategy_class(
                config=self.config_manager,
                monitoring=self.monitoring,
                db_manager=self.db_manager,
                finance_manager=self.finance_manager
            )

            # Store the strategy instance
            self.strategies[strategy_name] = strategy

            self.logger.info(f"Strategy '{strategy_name}' loaded successfully")
            self.monitoring.record_event(
                "info",
                "AppController",
                f"Loaded strategy: {strategy_name}"
            )

            return True
        except Exception as e:
            self.logger.error(f"Error initializing strategy '{strategy_name}': {str(e)}")
            return False

    def unload_strategy(self, strategy_name: str) -> bool:
        """
        Unload a strategy.

        Args:
            strategy_name: Name of the strategy to unload

        Returns:
            True if the strategy was unloaded successfully, False otherwise
        """
        if strategy_name not in self.strategies:
            self.logger.warning(f"Strategy '{strategy_name}' not loaded")
            return False

        try:
            # Get the strategy instance
            strategy = self.strategies[strategy_name]

            # Call cleanup method if available
            if hasattr(strategy, 'cleanup') and callable(strategy.cleanup):
                strategy.cleanup()

            # Remove from active strategies
            del self.strategies[strategy_name]

            self.logger.info(f"Strategy '{strategy_name}' unloaded successfully")
            self.monitoring.record_event(
                "info",
                "AppController",
                f"Unloaded strategy: {strategy_name}"
            )

            return True
        except Exception as e:
            self.logger.error(f"Error unloading strategy '{strategy_name}': {str(e)}")
            return False

    def stop(self) -> None:
        """
        Stop the application.
        """
        self.logger.info("Stopping Autonomous Income Generator")

        # Set running flag too False to stop the main loop
        self.running = False

        # Unload all strategies
        for strategy_name in list(self.strategies.keys()):
            self.unload_strategy(strategy_name)

        # Record application stop event
        self.monitoring.record_event(
            "info",
            "AppController",
            "Application stopped"
        )