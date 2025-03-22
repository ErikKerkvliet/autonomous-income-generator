# app/web/browser_manager.py
"""
Browser Manager for the Autonomous Income Generator.

This module provides utilities for managing web browser instances
with anti-detection features.
"""
import os
import logging
import time
from typing import Dict, Any, Optional, List
import random
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import undetected_chromedriver as uc
from selenium_stealth import stealth


class BrowserManager:
    """
    Manages browser instances with anti-detection capabilities.
    """

    def __init__(self, config):
        """
        Initialize the browser manager.

        Args:
            config: Configuration manager instance
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.active_browsers = {}

        # Load browser configuration
        self.use_undetected = self.config.get(
            "WEB_AUTOMATION",
            "USE_UNDETECTED_CHROME",
            "true"
        ).lower() == "true"

        self.use_stealth = self.config.get(
            "WEB_AUTOMATION",
            "USE_SELENIUM_STEALTH",
            "true"
        ).lower() == "true"

        self.headless = self.config.get(
            "WEB_AUTOMATION",
            "HEADLESS",
            "false"
        ).lower() == "true"

        self.user_agents = self._load_user_agents()
        self.logger.info(
            f"Initialized browser manager (undetected: {self.use_undetected}, stealth: {self.use_stealth})")

    def _load_user_agents(self) -> List[str]:
        """
        Load a list of user agents to randomize browser fingerprints.

        Returns:
            List of user agent strings
        """
        # Default user agents (most common Chrome/Firefox on Windows/Mac)
        default_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0"
        ]

        # Try to load user agents from configuration
        user_agents_str = self.config.get("WEB_AUTOMATION", "USER_AGENTS", "")

        if user_agents_str:
            try:
                user_agents = json.loads(user_agents_str)
                if isinstance(user_agents, list) and len(user_agents) > 0:
                    return user_agents
            except json.JSONDecodeError:
                self.logger.warning("Error parsing USER_AGENTS configuration")
                pass

        return default_agents

    def get_browser(self, profile_name: Optional[str] = None) -> webdriver.Chrome:
        """
        Get a browser instance with anti-detection features.

        Args:
            profile_name: Name of the browser profile to use (for session persistence)

        Returns:
            Selenium WebDriver instance
        """
        # Generate a unique browser ID
        browser_id = profile_name or f"browser_{len(self.active_browsers) + 1}"

        # Check if browser already exists
        if browser_id in self.active_browsers:
            return self.active_browsers[browser_id]

        try:
            browser = None

            if self.use_undetected:
                # Use undetected-chromedriver for better bot detection evasion
                options = uc.ChromeOptions()

                if self.headless:
                    options.add_argument("--headless")

                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")

                # Set a random user agent
                user_agent = random.choice(self.user_agents)
                options.add_argument(f"--user-agent={user_agent}")

                # Create profile directory if using a profile
                if profile_name:
                    profile_dir = os.path.join("browser_profiles", profile_name)
                    os.makedirs(profile_dir, exist_ok=True)
                    options.add_argument(f"--user-data-dir={profile_dir}")

                browser = uc.Chrome(options=options)

            else:
                # Use regular Selenium with stealth
                options = Options()

                if self.headless:
                    options.add_argument("--headless")

                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")

                # Set a random user agent
                user_agent = random.choice(self.user_agents)
                options.add_argument(f"--user-agent={user_agent}")

                # Create profile directory if using a profile
                if profile_name:
                    profile_dir = os.path.join("browser_profiles", profile_name)
                    os.makedirs(profile_dir, exist_ok=True)
                    options.add_argument(f"--user-data-dir={profile_dir}")

                # Initialize the browser with ChromeDriverManager
                browser = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()),
                    options=options
                )

                # Apply stealth if enabled
                if self.use_stealth:
                    stealth(
                        browser,
                        user_agent=user_agent,
                        languages=["en-US", "en"],
                        vendor="Google Inc.",
                        platform="Win32",
                        webgl_vendor="Intel Inc.",
                        renderer="Intel Iris OpenGL Engine",
                        fix_hairline=True
                    )

            # Set window size
            browser.set_window_size(1920, 1080)

            # Add to active browsers
            self.active_browsers[browser_id] = browser

            # Set default timeouts
            browser.implicitly_wait(10)
            browser.set_page_load_timeout(30)

            self.logger.info(f"Created new browser instance: {browser_id}")
            return browser

        except Exception as e:
            self.logger.error(f"Error creating browser instance: {str(e)}")

            # Attempt to create a fallback browser
            if self.use_undetected:
                self.logger.info("Trying fallback to regular Selenium")
                self.use_undetected = False
                return self.get_browser(profile_name)

            raise

    def close_browser(self, browser) -> None:
        """
        Close a browser instance.

        Args:
            browser: Browser instance to close
        """
        # Find the browser ID
        browser_id = None
        for bid, b in self.active_browsers.items():
            if b == browser:
                browser_id = bid
                break

        if browser_id:
            try:
                browser.quit()
                del self.active_browsers[browser_id]
                self.logger.info(f"Closed browser instance: {browser_id}")
            except Exception as e:
                self.logger.error(f"Error closing browser instance {browser_id}: {str(e)}")
        else:
            try:
                browser.quit()
                self.logger.info("Closed untracked browser instance")
            except Exception as e:
                self.logger.error(f"Error closing untracked browser instance: {str(e)}")

    def close_all_browsers(self) -> None:
        """
        Close all active browser instances.
        """
        for browser_id, browser in list(self.active_browsers.items()):
            try:
                browser.quit()
                self.logger.info(f"Closed browser instance: {browser_id}")
            except Exception as e:
                self.logger.error(f"Error closing browser instance {browser_id}: {str(e)}")

        self.active_browsers = {}