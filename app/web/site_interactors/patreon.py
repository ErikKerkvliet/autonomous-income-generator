# app/web/site_interactors/patreon.py
"""
Patreon site interactor for the Autonomous Income Generator.

This module provides utilities for interacting with Patreon's website.
"""
import logging
import time
import random
from typing import Dict, Any, Optional, List
from selenium.webdriver.common.by import By
import re
import json


class PatreonInteractor:
    """
    Utilities for interacting with Patreon's website.
    """

    def __init__(self, browser_manager, captcha_solver, config):
        """
        Initialize the Patreon interactor.

        Args:
            browser_manager: Browser manager instance
            captcha_solver: Captcha solver instance
            config: Configuration manager instance
        """
        self.browser_manager = browser_manager
        self.captcha_solver = captcha_solver
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Load credentials
        self.credentials = self.config.get_website_credentials("PATREON")

        if not self.credentials:
            self.logger.warning("No Patreon credentials found")

    def login(self, browser) -> bool:
        """
        Log in to Patreon.

        Args:
            browser: Browser instance

        Returns:
            True if login successful, False otherwise
        """
        try:
            if not self.credentials:
                self.logger.error("No Patreon credentials available")
                return False

            # Navigate to login page
            browser.get("https://www.patreon.com/login")
            time.sleep(random.uniform(2, 4))

            # Enter email
            email_field = browser.find_element(By.ID, "email")
            email_field.send_keys(self.credentials["username"])
            time.sleep(random.uniform(1, 2))

            # Enter password
            password_field = browser.find_element(By.ID, "password")
            password_field.send_keys(self.credentials["password"])
            time.sleep(random.uniform(1, 2))

            # Check for CAPTCHA
            captcha_elements = browser.find_elements(By.XPATH,  
                "//iframe[contains(@src, 'recaptcha') or contains(@src, 'hcaptcha')]")

            if captcha_elements:
                self.logger.info("CAPTCHA detected, attempting to solve")

                # Determine captcha type
                captcha_src = captcha_elements[0].get_attribute("src")

                if "recaptcha" in captcha_src:
                    # Find site key
                    site_key_match = re.search(r'k=([^&]+)', captcha_src)
                    if site_key_match:
                        site_key = site_key_match.group(1)

                        # Solve reCAPTCHA
                        token = self.captcha_solver.solve_recaptcha_v2(
                            website_url="https://www.patreon.com/login",
                            website_key=site_key
                        )

                        if token:
                            # Inject token
                            self.captcha_solver.inject_recaptcha_token(browser, token)
                        else:
                            self.logger.error("Failed to solve reCAPTCHA")
                            return False

                elif "hcaptcha" in captcha_src:
                    # Find site key
                    site_key_match = re.search(r'sitekey=([^&]+)', captcha_src)
                    if site_key_match:
                        site_key = site_key_match.group(1)

                        # Solve hCAPTCHA
                        token = self.captcha_solver.solve_hcaptcha(
                            website_url="https://www.patreon.com/login",
                            website_key=site_key
                        )

                        if token:
                            # Inject token
                            self.captcha_solver.inject_hcaptcha_token(browser, token)
                        else:
                            self.logger.error("Failed to solve hCAPTCHA")
                            return False

            # Click login button
            login_button = browser.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            time.sleep(random.uniform(3, 5))

            # Check if login was successful
            if "dashboard" in browser.current_url or "creator-home" in browser.current_url:
                self.logger.info("Successfully logged in to Patreon")
                return True

            self.logger.error("Failed to log in to Patreon")
            return False

        except Exception as e:
            self.logger.error(f"Error logging in to Patreon: {str(e)}")
            return False

    def create_post(self, browser, title: str, content: str, access_level: str = "public") -> bool:
        """
        Create a new post on Patreon.

        Args:
            browser: Browser instance
            title: Post title
            content: Post content
            access_level: Access level (public, patrons, specific_tier)

        Returns:
            True if post created successfully, False otherwise
        """
        try:
            # Navigate to new post page
            browser.get("https://www.patreon.com/posts/new")
            time.sleep(random.uniform(2, 4))

            # Enter title
            title_field = browser.find_element(By.XPATH, "//input[@placeholder='Title']")
            title_field.send_keys(title)
            time.sleep(random.uniform(1, 2))

            # Enter content (assuming a rich text editor)
            content_iframe = browser.find_element(By.XPATH, "//iframe[contains(@class, 'editor-frame')]")
            browser.switch_to.frame(content_iframe)

            content_field = browser.find_element(By.XPATH, "//div[@contenteditable='true']")
            content_field.send_keys(content)

            # Switch back to main frame
            browser.switch_to.default_content()
            time.sleep(random.uniform(1, 2))

            # Set access level
            if access_level != "public":
                # Click access level dropdown
                access_dropdown = browser.find_element(By.XPATH, 
                    "//button[contains(@class, 'access-dropdown') or contains(text(), 'Public')]")
                access_dropdown.click()
                time.sleep(random.uniform(1, 2))

                # Select access level
                if access_level == "patrons":
                    patrons_option = browser.find_element(By.XPATH, "//div[contains(text(), 'All patrons')]")
                    patrons_option.click()
                elif access_level == "specific_tier":
                    tier_option = browser.find_element(By.XPATH, "//div[contains(text(), 'Specific tiers')]")
                    tier_option.click()
                    # Would need additional logic to select specific tiers

                time.sleep(random.uniform(1, 2))

            # Click publish button
            publish_button = browser.find_element(By.XPATH, "//button[contains(text(), 'Publish')]")
            publish_button.click()
            time.sleep(random.uniform(3, 5))

            # Check if post was created
            success_elements = browser.find_elements(By.XPATH,  
                "//div[contains(text(), 'successfully') or contains(text(), 'published')]")

            if success_elements:
                self.logger.info(f"Successfully created Patreon post: {title}")
                return True

            self.logger.warning(f"May have failed to create Patreon post: {title}")
            return False

        except Exception as e:
            self.logger.error(f"Error creating Patreon post: {str(e)}")
            return False

    def check_earnings(self, browser) -> Dict[str, Any]:
        """
        Check earnings on Patreon.

        Args:
            browser: Browser instance

        Returns:
            Dictionary with earnings information
        """
        try:
            # Navigate to income page
            browser.get("https://www.patreon.com/dashboard/earnings")
            time.sleep(random.uniform(3, 5))

            # Extract earnings information
            earnings_element = browser.find_element(By.XPATH, 
                "//div[contains(@class, 'earnings') or contains(@class, 'amount')]")
            earnings_text = earnings_element.text.strip()

            # Parse earnings amount
            earnings_match = re.search(r'\$(\d+(\.\d+)?)', earnings_text)
            earnings = float(earnings_match.group(1)) if earnings_match else 0

            # Extract patron count
            patrons_element = browser.find_element(By.XPATH, 
                "//div[contains(@class, 'patrons') or contains(text(), 'patrons')]")
            patrons_text = patrons_element.text.strip()

            patrons_match = re.search(r'(\d+)', patrons_text)
            patrons = int(patrons_match.group(1)) if patrons_match else 0

            self.logger.info(f"Patreon earnings: ${earnings} from {patrons} patrons")

            return {
                "success": True,
                "earnings": earnings,
                "patrons": patrons
            }

        except Exception as e:
            self.logger.error(f"Error checking Patreon earnings: {str(e)}")
            return {
                "success": False,
                "earnings": 0,
                "patrons": 0
            }