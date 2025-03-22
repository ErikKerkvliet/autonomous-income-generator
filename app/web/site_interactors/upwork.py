# app/web/site_interactors/upwork.py
"""
Upwork site interactor for the Autonomous Income Generator.

This module provides utilities for interacting with Upwork's website.
"""
import logging
import time
import random
from typing import Dict, Any, Optional, List
from selenium.webdriver.common.by import By
import re
import json


class UpworkInteractor:
    """
    Utilities for interacting with Upwork's website.
    """

    def __init__(self, browser_manager, captcha_solver, config):
        """
        Initialize the Upwork interactor.

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
        self.credentials = self.config.get_website_credentials("UPWORK")

        if not self.credentials:
            self.logger.warning("No Upwork credentials found")

    def login(self, browser) -> bool:
        """
        Log in to Upwork.

        Args:
            browser: Browser instance

        Returns:
            True if login successful, False otherwise
        """
        try:
            if not self.credentials:
                self.logger.error("No Upwork credentials available")
                return False

            # Navigate to login page
            browser.get("https://www.upwork.com/ab/account-security/login")
            time.sleep(random.uniform(2, 4))

            # Enter username
            username_field = browser.find_element(By.ID, "login_username")
            username_field.send_keys(self.credentials["username"])
            time.sleep(random.uniform(1, 2))

            # Click continue
            continue_button = browser.find_element(By.ID, "login_password_continue")
            continue_button.click()
            time.sleep(random.uniform(2, 4))

            # Enter password
            password_field = browser.find_element(By.ID, "login_password")
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
                            website_url="https://www.upwork.com/ab/account-security/login",
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
                            website_url="https://www.upwork.com/ab/account-security/login",
                            website_key=site_key
                        )

                        if token:
                            # Inject token
                            self.captcha_solver.inject_hcaptcha_token(browser, token)
                        else:
                            self.logger.error("Failed to solve hCAPTCHA")
                            return False

            # Click login button
            login_button = browser.find_element(By.ID, "login_control_continue")
            login_button.click()
            time.sleep(random.uniform(3, 6))

            # Check if login was successful
            if "desk" in browser.current_url or "dashboard" in browser.current_url:
                self.logger.info("Successfully logged in to Upwork")
                return True

            # Check for 2FA
            if "security-question" in browser.current_url or "2fa" in browser.current_url:
                self.logger.error("2FA required for Upwork login")
                return False

            self.logger.error("Failed to log in to Upwork")
            return False

        except Exception as e:
            self.logger.error(f"Error logging in to Upwork: {str(e)}")
            return False

    def search_jobs(self, browser, keywords: List[str], job_types: List[str], min_budget: float, max_budget: float) -> \
    List[Dict[str, Any]]:
        """
        Search for jobs on Upwork.

        Args:
            browser: Browser instance
            keywords: List of keywords to search for
            job_types: List of job types to include
            min_budget: Minimum budget
            max_budget: Maximum budget

        Returns:
            List of job dictionaries
        """
        jobs_found = []

        try:
            for keyword in keywords:
                self.logger.info(f"Searching for jobs with keyword: {keyword}")

                # Navigate to job search page
                search_url = f"https://www.upwork.com/search/jobs/?q={keyword}&sort=recency"
                browser.get(search_url)
                time.sleep(random.uniform(2, 4))

                # Get job listings
                job_elements = browser.find_elements(By.XPATH,  "//section[contains(@class, 'job-tile')]")
                self.logger.info(f"Found {len(job_elements)} job listings")

                for job_element in job_elements[:10]:  # Limit to first 10 results
                    try:
                        # Extract job information (implementation details omitted for brevity)
                        job = {
                            'id': job_element.get_attribute("data-job-id") or str(random.randint(10000, 99999)),
                            'title': job_element.find_element(By.XPATH, 
                                ".//h2[contains(@class, 'job-title')]").text.strip(),
                            # Additional job details...
                        }

                        jobs_found.append(job)

                    except Exception as e:
                        self.logger.error(f"Error processing job listing: {str(e)}")

                # Wait between searches
                time.sleep(random.uniform(2, 4))

            return jobs_found

        except Exception as e:
            self.logger.error(f"Error searching for jobs: {str(e)}")
            return jobs_found
