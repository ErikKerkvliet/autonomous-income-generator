# app/core/config_manager.py
"""
Configuration Manager for the Autonomous Income Generator

This module is responsible for loading and managing configuration settings
from environment variables and .env files.
"""
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import json
import logging


class ConfigManager:
    """
    Manages application configuration settings from .env files and environment variables.
    """

    def __init__(self, env_path: str = ".env"):
        """
        Initialize the configuration manager.

        Args:
            env_path: Path to the .env file (default: ".env")
        """
        self.env_path = env_path
        self.config = {}
        self.logger = logging.getLogger(__name__)
        self._load_config()

    def _load_config(self) -> None:
        """
        Load configuration from .env file and environment variables.
        """
        # Load variables from .env file
        if os.path.exists(self.env_path):
            load_dotenv(self.env_path)
            self.logger.info(f"Loaded configuration from {self.env_path}")
        else:
            self.logger.warning(f".env file not found at {self.env_path}")

        # Required config categories
        categories = [
            "FINANCIAL", "LLM_API", "DATABASE", "WEBSITE_CREDENTIALS",
            "WEB_AUTOMATION", "STRATEGIES"
        ]

        # Load configuration for each category
        for category in categories:
            self.config[category] = {}
            prefix = f"{category}_"
            for key, value in os.environ.items():
                if key.startswith(prefix):
                    config_key = key[len(prefix):]

                    # Try to parse as JSON if it looks like a JSON structure
                    if value.startswith('{') or value.startswith('['):
                        try:
                            value = json.loads(value)
                        except json.JSONDecodeError:
                            pass

                    self.config[category][config_key] = value

    def get(self, category: str, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            category: Configuration category (e.g. "FINANCIAL", "LLM_API")
            key: Configuration key
            default: Default value if the key doesn't exist

        Returns:
            The configuration value or the default value
        """
        return self.config.get(category, {}).get(key, default)

    def get_all(self, category: str) -> Dict[str, Any]:
        """
        Get all configuration values for a category.

        Args:
            category: Configuration category

        Returns:
            Dictionary of all configurations in the category
        """
        return self.config.get(category, {})

    def get_website_credentials(self, site: str) -> Dict[str, str]:
        """
        Get login credentials for a specific website.

        Args:
            site: Website name (e.g. "UPWORK", "PATREON")

        Returns:
            Dictionary with username and password keys
        """
        credentials = {}
        username_key = f"{site.upper()}_USERNAME"
        password_key = f"{site.upper()}_PASSWORD"

        username = self.get("WEBSITE_CREDENTIALS", username_key)
        password = self.get("WEBSITE_CREDENTIALS", password_key)

        if username and password:
            credentials = {
                "username": username,
                "password": password
            }

        return credentials

    def is_strategy_enabled(self, strategy: str) -> bool:
        """
        Check if a specific income generation strategy is enabled.

        Args:
            strategy: Strategy name

        Returns:
            True if the strategy is enabled, False otherwise
        """
        return self.get("STRATEGIES", f"{strategy.upper()}_ENABLED", "false").lower() == "true"