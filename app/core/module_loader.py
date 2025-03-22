# app/core/module_loader.py
"""
Module Loader for the Autonomous Income Generator

This module is responsible for dynamically loading and managing
income generation strategies.
"""
import importlib
import os
import inspect
import logging
from typing import Dict, List, Type, Any, Optional
import importlib.util
import sys


class ModuleLoader:
    """
    Dynamically loads and manages income generation strategies and modules.
    """

    def __init__(self, strategies_dir: str = "app/income_strategies"):
        """
        Initialize the module loader.

        Args:
            strategies_dir: Directory containing income strategy modules
        """
        self.strategies_dir = strategies_dir
        self.strategies = {}
        self.logger = logging.getLogger(__name__)

    def discover_strategies(self) -> Dict[str, Dict[str, Any]]:
        """
        Discover available income generation strategies.

        Returns:
            Dictionary of strategy metadata indexed by strategy name
        """
        self.strategies = {}

        # Navigate the strategies directory
        for item in os.listdir(self.strategies_dir):
            item_path = os.path.join(self.strategies_dir, item)

            # Skip if not a directory or starts with an underscore
            if not os.path.isdir(item_path) or item.startswith('_'):
                continue

            # Look for a main.py or __init__.py file
            strategy_module = None
            if os.path.exists(os.path.join(item_path, "main.py")):
                strategy_module = f"app.income_strategies.{item}.main"
            elif os.path.exists(os.path.join(item_path, "__init__.py")):
                strategy_module = f"app.income_strategies.{item}"

            if strategy_module:
                try:
                    # Import the module
                    module = importlib.import_module(strategy_module)

                    # Look for the strategy class
                    strategy_class = None
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and
                                hasattr(obj, 'STRATEGY_NAME') and
                                hasattr(obj, 'STRATEGY_DESCRIPTION')):
                            strategy_class = obj
                            break

                    if strategy_class:
                        self.strategies[item] = {
                            'name': getattr(strategy_class, 'STRATEGY_NAME', item),
                            'description': getattr(strategy_class, 'STRATEGY_DESCRIPTION', ''),
                            'module': strategy_module,
                            'class': strategy_class.__name__
                        }
                        self.logger.info(f"Discovered strategy: {item}")
                except ImportError as e:
                    self.logger.error(f"Error importing strategy {item}: {str(e)}")

        return self.strategies

    def load_strategy(self, strategy_name: str) -> Optional[Type]:
        """
        Load a specific income generation strategy class.

        Args:
            strategy_name: Name of the strategy to load

        Returns:
            Strategy class or None if not found
        """
        if strategy_name not in self.strategies:
            self.discover_strategies()

        if strategy_name not in self.strategies:
            self.logger.error(f"Strategy not found: {strategy_name}")
            return None

        strategy_info = self.strategies[strategy_name]

        try:
            module = importlib.import_module(strategy_info['module'])
            strategy_class = getattr(module, strategy_info['class'])
            self.logger.info(f"Loaded strategy: {strategy_name}")
            return strategy_class
        except (ImportError, AttributeError) as e:
            self.logger.error(f"Error loading strategy {strategy_name}: {str(e)}")
            return None

    def load_dynamic_code(self, code: str, module_name: str = "dynamic_module") -> Any:
        """
        Dynamically load and execute Python code at runtime.

        Args:
            code: Python code to load
            module_name: Name for the dynamic module

        Returns:
            The loaded module object
        """
        # Create a unique module name to avoid conflicts
        unique_module_name = f"{module_name}_{id(code)}"

        try:
            # Create a new module spec
            spec = importlib.util.spec_from_loader(
                unique_module_name,
                loader=None
            )
            module = importlib.util.module_from_spec(spec)

            # Add the module to sys.modules
            sys.modules[unique_module_name] = module

            # Execute the code in the module
            exec(code, module.__dict__)

            self.logger.info(f"Dynamically loaded code as module: {unique_module_name}")
            return module
        except Exception as e:
            self.logger.error(f"Error loading dynamic code: {str(e)}")
            return None