# app/income_strategies/paid_surveys/main.py
"""
Paid Surveys Strategy for the Autonomous Income Generator.

This strategy automates participation in paid online surveys.
"""
import logging
import time
import random
import datetime
from typing import Dict, Any, List, Optional
import re
import json
import os

from app.income_strategies.strategy_base import IncomeStrategy
from app.web.browser_manager import BrowserManager
from app.managers.api_manager import APIManager


class PaidSurveysStrategy(IncomeStrategy):
    """
    Strategy for generating income through paid online surveys.
    """

    # Strategy metadata
    STRATEGY_NAME = "Paid Surveys"
    STRATEGY_DESCRIPTION = "Automates participation in paid online surveys"

    # Run every 3 hours
    run_interval = 180

    # Survey platforms
    SURVEY_PLATFORMS = ["euroclix", "panelclix", "toluna", "surveyjunkie"]

    # Survey selection criteria
    MIN_PAYOUT = 0.50  # Minimum payout in platform's currency
    MAX_DURATION = 20  # Maximum survey duration in minutes

    def _initialize(self) -> None:
        """
        Initialize paid surveys strategy resources.
        """
        self.api_manager = APIManager(self.config)
        self.browser_manager = BrowserManager(self.config)

        # Load strategy configuration
        self.survey_platforms = self.config.get(
            "STRATEGIES",
            "PAID_SURVEYS_PLATFORMS",
            ",".join(self.SURVEY_PLATFORMS)
        ).split(",")

        self.min_payout = float(self.config.get(
            "STRATEGIES",
            "PAID_SURVEYS_MIN_PAYOUT",
            str(self.MIN_PAYOUT)
        ))

        self.max_duration = int(self.config.get(
            "STRATEGIES",
            "PAID_SURVEYS_MAX_DURATION",
            str(self.MAX_DURATION)
        ))

        # Maximum surveys per day per platform
        self.max_daily_surveys = int(self.config.get(
            "STRATEGIES",
            "PAID_SURVEYS_MAX_DAILY",
            "5"
        ))

        # Initialize database tables
        self._initialize_database()

        # Generate or load persona profile data
        self._initialize_persona()

        self.log_info(f"Initialized paid surveys strategy with platforms: {self.survey_platforms}")

    def _initialize_database(self) -> None:
        """
        Initialize database tables for paid surveys strategy.
        """
        # Create surveys table
        self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS paid_surveys (
                id INT AUTO_INCREMENT PRIMARY KEY,
                survey_id VARCHAR(255),
                platform VARCHAR(50),
                title VARCHAR(255),
                reward FLOAT,
                currency VARCHAR(10),
                duration INT,
                status VARCHAR(50),
                start_time DATETIME,
                completion_time DATETIME,
                payout_received BOOLEAN,
                payment_amount FLOAT,
                payment_date DATETIME,
                notes TEXT
            )
        """)

        # Create platforms table
        self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS survey_platforms (
                id INT AUTO_INCREMENT PRIMARY KEY,
                platform VARCHAR(50),
                username VARCHAR(255),
                last_login DATETIME,
                total_earnings FLOAT,
                currency VARCHAR(10),
                available_surveys INT,
                surveys_completed INT,
                surveys_disqualified INT,
                last_checked DATETIME
            )
        """)

        # Create persona data table
        self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS survey_persona (
                id INT AUTO_INCREMENT PRIMARY KEY,
                field VARCHAR(255),
                value TEXT,
                last_updated DATETIME
            )
        """)

    def _initialize_persona(self) -> None:
        """
        Initialize or load survey persona data.
        """
        # Check if persona data exists
        result = self.db_manager.query(
            "SELECT COUNT(*) as count FROM survey_persona"
        )

        if result and result[0]['count'] > 0:
            self.log_info("Loaded existing survey persona")
            return

        # Generate a new persona
        self.log_info("Generating new survey persona")

        # Create a prompt for the LLM to generate a realistic persona
        prompt = """
        Generate a realistic persona for participating in online surveys. The persona should be consistent but not stand out as unusual or suspicious.

        Create a JSON object with the following fields:
        - personal: basic demographics (age, gender, marital status, etc.)
        - location: where they live (country, city, type of residence)
        - work: employment details (job, industry, income bracket)
        - education: educational background
        - household: family composition, number of people
        - interests: hobbies, activities
        - shopping: buying habits, preferred stores
        - technology: devices owned, usage patterns
        - media: media consumption habits
        - health: general health information

        Make all fields realistic, consistent, and appropriate for someone who might regularly take online surveys. Give it enough specificity to be believable but keep it general enough that it could represent a common demographic profile.

        Format your response as a valid JSON object with these main categories as keys, and with appropriate nested fields.
        """

        # Generate persona using LLM
        response = self.api_manager.generate_text(prompt)

        try:
            # Parse JSON response
            persona = json.loads(response)

            # Flatten the persona data for storage
            now = datetime.datetime.now()

            for category, data in persona.items():
                if isinstance(data, dict):
                    for field, value in data.items():
                        key = f"{category}.{field}"
                        self.db_manager.execute(
                            """
                            INSERT INTO survey_persona (field, value, last_updated)
                            VALUES (%s, %s, %s)
                            """,
                            (key, str(value), now)
                        )
                else:
                    self.db_manager.execute(
                        """
                        INSERT INTO survey_persona (field, value, last_updated)
                        VALUES (%s, %s, %s)
                        """,
                        (category, str(data), now)
                    )

            self.log_info("Successfully created and stored survey persona")

        except json.JSONDecodeError:
            self.log_error(f"Error parsing LLM response for persona creation: {response[:100]}...")

    def _get_persona_field(self, field: str) -> str:
        """
        Get a specific field from the persona data.

        Args:
            field: Field name (e.g., 'personal.age')

        Returns:
            Field value or empty string if not found
        """
        result = self.db_manager.query(
            """
            SELECT value FROM survey_persona
            WHERE field = %s
            """,
            (field,)
        )

        if result:
            return result[0]['value']
        return ""

    def _get_persona_category(self, category: str) -> Dict[str, str]:
        """
        Get all fields for a specific category from the persona data.

        Args:
            category: Category name (e.g., 'personal')

        Returns:
            Dictionary of field values
        """
        result = self.db_manager.query(
            """
            SELECT field, value FROM survey_persona
            WHERE field LIKE %s
            """,
            (f"{category}.%",)
        )

        category_data = {}
        for row in result:
            field_name = row['field'].split('.')[1]
            category_data[field_name] = row['value']

        return category_data

    def _login_to_platform(self, browser, platform: str) -> bool:
        """
        Log in to a survey platform.

        Args:
            browser: Browser instance
            platform: Platform name

        Returns:
            True if login successful, False otherwise
        """
        try:
            # Get platform credentials
            credentials = self.config.get_website_credentials(platform.upper())
            if not credentials:
                self.log_error(f"No credentials found for {platform}")
                return False

            # Platform-specific login logic
            if platform.lower() == "euroclix":
                return self._login_to_euroclix(browser, credentials)
            elif platform.lower() == "panelclix":
                return self._login_to_panelclix(browser, credentials)
            elif platform.lower() == "toluna":
                return self._login_to_toluna(browser, credentials)
            elif platform.lower() == "surveyjunkie":
                return self._login_to_surveyjunkie(browser, credentials)
            else:
                self.log_error(f"Unsupported platform: {platform}")
                return False

        except Exception as e:
            self.log_error(f"Error logging in to {platform}: {str(e)}")
            return False

    def _login_to_euroclix(self, browser, credentials: Dict[str, str]) -> bool:
        """
        Log in to EuroClix.

        Args:
            browser: Browser instance
            credentials: Login credentials

        Returns:
            True if login successful, False otherwise
        """
        try:
            # Navigate to login page
            browser.get("https://www.euroclix.nl/inloggen/")
            self.random_delay(2, 4)

            # Accept cookies if prompted
            cookie_buttons = browser.find_elements_by_xpath(
                "//button[contains(text(), 'Accept') or contains(text(), 'Accepteer')]")
            if cookie_buttons:
                cookie_buttons[0].click()
                self.random_delay(1, 2)

            # Enter email
            email_field = browser.find_element_by_id("email") or browser.find_element_by_name("email")
            email_field.send_keys(credentials["username"])
            self.random_delay(1, 2)

            # Enter password
            password_field = browser.find_element_by_id("password") or browser.find_element_by_name("password")
            password_field.send_keys(credentials["password"])
            self.random_delay(1, 2)

            # Click login button
            login_button = browser.find_element_by_xpath("//button[@type='submit' or contains(text(), 'Inloggen')]")
            login_button.click()
            self.random_delay(3, 5)

            # Check if login was successful
            if "mijn-account" in browser.current_url or "dashboard" in browser.current_url:
                self.log_info("Successfully logged in to EuroClix")

                # Update last login in database
                self._update_platform_status("euroclix", "last_login", datetime.datetime.now())

                return True
            else:
                self.log_error("Failed to log in to EuroClix")
                return False

        except Exception as e:
            self.log_error(f"Error logging in to EuroClix: {str(e)}")
            return False

    def _login_to_panelclix(self, browser, credentials: Dict[str, str]) -> bool:
        """
        Log in to PanelClix.

        Args:
            browser: Browser instance
            credentials: Login credentials

        Returns:
            True if login successful, False otherwise
        """
        try:
            # Navigate to login page
            browser.get("https://www.panelclix.nl/leden-login")
            self.random_delay(2, 4)

            # Accept cookies if prompted
            cookie_buttons = browser.find_elements_by_xpath(
                "//button[contains(text(), 'Accept') or contains(text(), 'Accepteer')]")
            if cookie_buttons:
                cookie_buttons[0].click()
                self.random_delay(1, 2)

            # Enter email
            email_field = browser.find_element_by_id("username") or browser.find_element_by_name("username")
            email_field.send_keys(credentials["username"])
            self.random_delay(1, 2)

            # Enter password
            password_field = browser.find_element_by_id("password") or browser.find_element_by_name("password")
            password_field.send_keys(credentials["password"])
            self.random_delay(1, 2)

            # Click login button
            login_button = browser.find_element_by_xpath(
                "//button[@type='submit' or contains(text(), 'Login') or contains(text(), 'Inloggen')]")
            login_button.click()
            self.random_delay(3, 5)

            # Check if login was successful
            if "dashboard" in browser.current_url or "member" in browser.current_url or "account" in browser.current_url:
                self.log_info("Successfully logged in to PanelClix")

                # Update last login in database
                self._update_platform_status("panelclix", "last_login", datetime.datetime.now())

                return True
            else:
                self.log_error("Failed to log in to PanelClix")
                return False

        except Exception as e:
            self.log_error(f"Error logging in to PanelClix: {str(e)}")
            return False

    def _login_to_toluna(self, browser, credentials: Dict[str, str]) -> bool:
        """
        Log in to Toluna.

        Args:
            browser: Browser instance
            credentials: Login credentials

        Returns:
            True if login successful, False otherwise
        """
        try:
            # Navigate to login page
            browser.get("https://us.toluna.com/login")
            self.random_delay(2, 4)

            # Accept cookies if prompted
            cookie_buttons = browser.find_elements_by_xpath(
                "//button[contains(text(), 'Accept') or contains(text(), 'Accepteer') or contains(text(), 'Got it')]")
            if cookie_buttons:
                cookie_buttons[0].click()
                self.random_delay(1, 2)

            # Enter email
            email_field = browser.find_element_by_id("email") or browser.find_element_by_name("email")
            email_field.send_keys(credentials["username"])
            self.random_delay(1, 2)

            # Enter password
            password_field = browser.find_element_by_id("password") or browser.find_element_by_name("password")
            password_field.send_keys(credentials["password"])
            self.random_delay(1, 2)

            # Click login button
            login_button = browser.find_element_by_xpath(
                "//button[@type='submit' or contains(text(), 'Sign in') or contains(text(), 'Login')]")
            login_button.click()
            self.random_delay(3, 5)

            # Check if login was successful
            if "dashboard" in browser.current_url or "member" in browser.current_url:
                self.log_info("Successfully logged in to Toluna")

                # Update last login in database
                self._update_platform_status("toluna", "last_login", datetime.datetime.now())

                return True
            else:
                self.log_error("Failed to log in to Toluna")
                return False

        except Exception as e:
            self.log_error(f"Error logging in to Toluna: {str(e)}")
            return False

    def _login_to_surveyjunkie(self, browser, credentials: Dict[str, str]) -> bool:
        """
        Log in to Survey Junkie.

        Args:
            browser: Browser instance
            credentials: Login credentials

        Returns:
            True if login successful, False otherwise
        """
        try:
            # Navigate to login page
            browser.get("https://www.surveyjunkie.com/login")
            self.random_delay(2, 4)

            # Accept cookies if prompted
            cookie_buttons = browser.find_elements_by_xpath(
                "//button[contains(text(), 'Accept') or contains(text(), 'Got it')]")
            if cookie_buttons:
                cookie_buttons[0].click()
                self.random_delay(1, 2)

            # Enter email
            email_field = browser.find_element_by_id("email") or browser.find_element_by_name("email")
            email_field.send_keys(credentials["username"])
            self.random_delay(1, 2)

            # Enter password
            password_field = browser.find_element_by_id("password") or browser.find_element_by_name("password")
            password_field.send_keys(credentials["password"])
            self.random_delay(1, 2)

            # Click login button
            login_button = browser.find_element_by_xpath(
                "//button[@type='submit' or contains(text(), 'Sign in') or contains(text(), 'Log in')]")
            login_button.click()
            self.random_delay(3, 5)

            # Check if login was successful
            if "dashboard" in browser.current_url or "surveys" in browser.current_url:
                self.log_info("Successfully logged in to Survey Junkie")

                # Update last login in database
                self._update_platform_status("surveyjunkie", "last_login", datetime.datetime.now())

                return True
            else:
                self.log_error("Failed to log in to Survey Junkie")
                return False

        except Exception as e:
            self.log_error(f"Error logging in to Survey Junkie: {str(e)}")
            return False

    def _update_platform_status(self, platform: str, field: str, value: Any) -> None:
        """
        Update a specific field in the platform status.

        Args:
            platform: Platform name
            field: Field to update
            value: New value
        """
        # Check if platform exists in database
        result = self.db_manager.query(
            """
            SELECT id FROM survey_platforms
            WHERE platform = %s
            """,
            (platform,)
        )

        if result:
            # Update existing record
            if field == "last_login":
                self.db_manager.execute(
                    """
                    UPDATE survey_platforms
                    SET last_login = %s
                    WHERE platform = %s
                    """,
                    (value, platform)
                )
            elif field == "total_earnings":
                self.db_manager.execute(
                    """
                    UPDATE survey_platforms
                    SET total_earnings = %s
                    WHERE platform = %s
                    """,
                    (value, platform)
                )
            elif field == "currency":
                self.db_manager.execute(
                    """
                    UPDATE survey_platforms
                    SET currency = %s
                    WHERE platform = %s
                    """,
                    (value, platform)
                )
            elif field == "available_surveys":
                self.db_manager.execute(
                    """
                    UPDATE survey_platforms
                    SET available_surveys = %s
                    WHERE platform = %s
                    """,
                    (value, platform)
                )
            elif field == "surveys_completed":
                self.db_manager.execute(
                    """
                    UPDATE survey_platforms
                    SET surveys_completed = %s
                    WHERE platform = %s
                    """,
                    (value, platform)
                )
            elif field == "surveys_disqualified":
                self.db_manager.execute(
                    """
                    UPDATE survey_platforms
                    SET surveys_disqualified = %s
                    WHERE platform = %s
                    """,
                    (value, platform)
                )
            elif field == "last_checked":
                self.db_manager.execute(
                    """
                    UPDATE survey_platforms
                    SET last_checked = %s
                    WHERE platform = %s
                    """,
                    (value, platform)
                )
        else:
            # Create new record with default values
            self.db_manager.execute(
                """
                INSERT INTO survey_platforms
                (platform, username, last_login, total_earnings, currency, available_surveys, surveys_completed, surveys_disqualified, last_checked)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    platform,
                    self.config.get_website_credentials(platform.upper())[
                        "username"] if self.config.get_website_credentials(platform.upper()) else "",
                    datetime.datetime.now() if field == "last_login" else None,
                    value if field == "total_earnings" else 0.0,
                    value if field == "currency" else "EUR",
                    value if field == "available_surveys" else 0,
                    value if field == "surveys_completed" else 0,
                    value if field == "surveys_disqualified" else 0,
                    datetime.datetime.now() if field == "last_checked" else None
                )
            )

    def _get_available_surveys(self, browser, platform: str) -> List[Dict[str, Any]]:
        """
        Get available surveys on a platform.

        Args:
            browser: Browser instance
            platform: Platform name

        Returns:
            List of survey dictionaries
        """
        available_surveys = []

        try:
            if platform.lower() == "euroclix":
                available_surveys = self._get_euroclix_surveys(browser)
            elif platform.lower() == "panelclix":
                available_surveys = self._get_panelclix_surveys(browser)
            elif platform.lower() == "toluna":
                available_surveys = self._get_toluna_surveys(browser)
            elif platform.lower() == "surveyjunkie":
                available_surveys = self._get_surveyjunkie_surveys(browser)

            # Update available surveys count in database
            self._update_platform_status(platform, "available_surveys", len(available_surveys))
            self._update_platform_status(platform, "last_checked", datetime.datetime.now())

            self.log_info(f"Found {len(available_surveys)} available surveys on {platform}")

            return available_surveys

        except Exception as e:
            self.log_error(f"Error getting available surveys on {platform}: {str(e)}")
            return []

    def _get_euroclix_surveys(self, browser) -> List[Dict[str, Any]]:
        """
        Get available surveys on EuroClix.

        Args:
            browser: Browser instance

        Returns:
            List of survey dictionaries
        """
        surveys = []

        try:
            # Navigate to surveys page
            browser.get("https://www.euroclix.nl/enquetes/")
            self.random_delay(2, 4)

            # Find survey elements
            survey_elements = browser.find_elements_by_xpath(
                "//div[contains(@class, 'survey') or contains(@class, 'enquete')]")

            for element in survey_elements:
                try:
                    # Extract survey information
                    survey_id = element.get_attribute("data-id") or str(random.randint(10000, 99999))

                    title_element = element.find_element_by_xpath(".//h3 or .//div[contains(@class, 'title')]")
                    title = title_element.text.strip()

                    # Extract reward
                    reward_element = element.find_element_by_xpath(
                        ".//span[contains(@class, 'reward') or contains(@class, 'points') or contains(@class, 'clix')]")
                    reward_text = reward_element.text.strip()

                    reward = 0.0
                    reward_match = re.search(r'(\d+[.,]?\d*)', reward_text)
                    if reward_match:
                        reward = float(reward_match.group(1).replace(',', '.'))

                    # Extract duration if available
                    duration = 0
                    duration_elements = element.find_elements_by_xpath(
                        ".//span[contains(@class, 'duration') or contains(@class, 'time') or contains(text(), 'min')]")
                    if duration_elements:
                        duration_text = duration_elements[0].text.strip()
                        duration_match = re.search(r'(\d+)', duration_text)
                        if duration_match:
                            duration = int(duration_match.group(1))

                    # Check if the survey meets our criteria
                    if reward >= self.min_payout and (duration == 0 or duration <= self.max_duration):
                        surveys.append({
                            'id': survey_id,
                            'platform': 'euroclix',
                            'title': title,
                            'reward': reward,
                            'currency': 'EUR',
                            'duration': duration,
                            'url': browser.current_url,
                            'element': element  # Store element reference for later
                        })

                except Exception as e:
                    self.log_error(f"Error processing EuroClix survey: {str(e)}")

            return surveys

        except Exception as e:
            self.log_error(f"Error getting EuroClix surveys: {str(e)}")
            return []

    def _get_panelclix_surveys(self, browser) -> List[Dict[str, Any]]:
        """
        Get available surveys on PanelClix.

        Args:
            browser: Browser instance

        Returns:
            List of survey dictionaries
        """
        surveys = []

        try:
            # Navigate to surveys page
            browser.get("https://www.panelclix.nl/surveys")
            self.random_delay(2, 4)

            # Find survey elements
            survey_elements = browser.find_elements_by_xpath(
                "//div[contains(@class, 'survey') or contains(@class, 'enquete')]")

            for element in survey_elements:
                try:
                    # Extract survey information (implementation similar to EuroClix)
                    survey_id = element.get_attribute("data-id") or str(random.randint(10000, 99999))

                    title_element = element.find_element_by_xpath(".//h3 or .//div[contains(@class, 'title')]")
                    title = title_element.text.strip()

                    # Extract reward
                    reward_element = element.find_element_by_xpath(
                        ".//span[contains(@class, 'reward') or contains(@class, 'points') or contains(@class, 'clix')]")
                    reward_text = reward_element.text.strip()

                    reward = 0.0
                    reward_match = re.search(r'(\d+[.,]?\d*)', reward_text)
                    if reward_match:
                        reward = float(reward_match.group(1).replace(',', '.'))

                    # Extract duration if available
                    duration = 0
                    duration_elements = element.find_elements_by_xpath(
                        ".//span[contains(@class, 'duration') or contains(@class, 'time') or contains(text(), 'min')]")
                    if duration_elements:
                        duration_text = duration_elements[0].text.strip()
                        duration_match = re.search(r'(\d+)', duration_text)
                        if duration_match:
                            duration = int(duration_match.group(1))

                    # Check if the survey meets our criteria
                    if reward >= self.min_payout and (duration == 0 or duration <= self.max_duration):
                        surveys.append({
                            'id': survey_id,
                            'platform': 'panelclix',
                            'title': title,
                            'reward': reward,
                            'currency': 'EUR',
                            'duration': duration,
                            'url': browser.current_url,
                            'element': element
                        })

                except Exception as e:
                    self.log_error(f"Error processing PanelClix survey: {str(e)}")

            return surveys

        except Exception as e:
            self.log_error(f"Error getting PanelClix surveys: {str(e)}")
            return []

    def _get_toluna_surveys(self, browser) -> List[Dict[str, Any]]:
        """
        Get available surveys on Toluna.

        Args:
            browser: Browser instance

        Returns:
            List of survey dictionaries
        """
        surveys = []

        try:
            # Navigate to surveys page
            browser.get("https://us.toluna.com/surveys")
            self.random_delay(2, 4)

            # Find survey elements
            survey_elements = browser.find_elements_by_xpath("//div[contains(@class, 'survey-item')]")

            for element in survey_elements:
                try:
                    # Extract survey information
                    survey_id = element.get_attribute("data-survey-id") or str(random.randint(10000, 99999))

                    title_element = element.find_element_by_xpath(".//div[contains(@class, 'title')] or .//h4")
                    title = title_element.text.strip()

                    # Extract reward
                    reward_element = element.find_element_by_xpath(
                        ".//span[contains(@class, 'reward') or contains(@class, 'points')]")
                    reward_text = reward_element.text.strip()

                    reward = 0.0
                    reward_match = re.search(r'(\d+[.,]?\d*)', reward_text)
                    if reward_match:
                        reward = float(reward_match.group(1).replace(',', '.'))
                        # Convert points to EUR (simplified conversion)
                        reward = reward / 100.0

                    # Extract duration if available
                    duration = 0
                    duration_elements = element.find_elements_by_xpath(
                        ".//span[contains(@class, 'duration') or contains(@class, 'time') or contains(text(), 'min')]")
                    if duration_elements:
                        duration_text = duration_elements[0].text.strip()
                        duration_match = re.search(r'(\d+)', duration_text)
                        if duration_match:
                            duration = int(duration_match.group(1))

                    # Check if the survey meets our criteria
                    if reward >= self.min_payout and (duration == 0 or duration <= self.max_duration):
                        surveys.append({
                            'id': survey_id,
                            'platform': 'toluna',
                            'title': title,
                            'reward': reward,
                            'currency': 'EUR',
                            'duration': duration,
                            'url': browser.current_url,
                            'element': element
                        })

                except Exception as e:
                    self.log_error(f"Error processing Toluna survey: {str(e)}")

            return surveys

        except Exception as e:
            self.log_error(f"Error getting Toluna surveys: {str(e)}")
            return []

    def _get_surveyjunkie_surveys(self, browser) -> List[Dict[str, Any]]:
        """
        Get available surveys on Survey Junkie.

        Args:
            browser: Browser instance

        Returns:
            List of survey dictionaries
        """
        surveys = []

        try:
            # Navigate to surveys page
            browser.get("https://www.surveyjunkie.com/member/surveys")
            self.random_delay(2, 4)

            # Find survey elements
            survey_elements = browser.find_elements_by_xpath("//div[contains(@class, 'survey-item')]")

            for element in survey_elements:
                try:
                    # Extract survey information
                    survey_id = element.get_attribute("data-survey-id") or str(random.randint(10000, 99999))

                    title_element = element.find_element_by_xpath(".//div[contains(@class, 'title')] or .//h3")
                    title = title_element.text.strip()

                    # Extract reward
                    reward_element = element.find_element_by_xpath(
                        ".//span[contains(@class, 'reward') or contains(@class, 'points')]")
                    reward_text = reward_element.text.strip()

                    reward = 0.0
                    reward_match = re.search(r'(\d+[.,]?\d*)', reward_text)
                    if reward_match:
                        reward = float(reward_match.group(1).replace(',', '.'))
                        # Convert points to USD (simplified conversion)
                        reward = reward / 100.0

                    # Extract duration if available
                    duration = 0
                    duration_elements = element.find_elements_by_xpath(
                        ".//span[contains(@class, 'duration') or contains(@class, 'time') or contains(text(), 'min')]")
                    if duration_elements:
                        duration_text = duration_elements[0].text.strip()
                        duration_match = re.search(r'(\d+)', duration_text)
                        if duration_match:
                            duration = int(duration_match.group(1))

                    # Check if the survey meets our criteria
                    if reward >= self.min_payout and (duration == 0 or duration <= self.max_duration):
                        surveys.append({
                            'id': survey_id,
                            'platform': 'surveyjunkie',
                            'title': title,
                            'reward': reward,
                            'currency': 'USD',
                            'duration': duration,
                            'url': browser.current_url,
                            'element': element
                        })

                except Exception as e:
                    self.log_error(f"Error processing Survey Junkie survey: {str(e)}")

            return surveys

        except Exception as e:
            self.log_error(f"Error getting Survey Junkie surveys: {str(e)}")
            return []

    def _complete_survey(self, browser, survey: Dict[str, Any]) -> Dict[str, Any]:
        """
        Complete a survey.

        Args:
            browser: Browser instance
            survey: Survey dictionary

        Returns:
            Dictionary with the result of the completion
        """
        platform = survey['platform']
        survey_id = survey['id']

        try:
            self.log_info(f"Starting survey {survey_id} on {platform}")

            # Record the start of the survey
            start_time = datetime.datetime.now()

            # Save survey in database
            self.db_manager.execute(
                """
                INSERT INTO paid_surveys
                (survey_id, platform, title, reward, currency, duration, status, start_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    survey_id,
                    platform,
                    survey['title'],
                    survey['reward'],
                    survey['currency'],
                    survey['duration'],
                    'started',
                    start_time
                )
            )

            # Get the inserted survey database ID
            result = self.db_manager.query(
                """
                SELECT id FROM paid_surveys
                WHERE survey_id = %s AND platform = %s AND start_time = %s
                """,
                (survey_id, platform, start_time)
            )

            if not result:
                self.log_error(f"Failed to get database ID for survey {survey_id}")
                return {
                    'success': False,
                    'status': 'error',
                    'message': 'Failed to get database ID'
                }

            db_id = result[0]['id']

            # Click on the survey to start it
            try:
                if 'element' in survey and survey['element']:
                    # Find clickable element within the survey item
                    clickable = survey['element'].find_element_by_xpath(
                        ".//a[contains(@class, 'btn') or contains(@class, 'button')] or .//button")
                    clickable.click()
                    self.random_delay(4, 7)
                else:
                    self.log_error(f"No element reference for survey {survey_id}")
                    return {
                        'success': False,
                        'status': 'error',
                        'message': 'No element reference'
                    }
            except Exception as e:
                self.log_error(f"Error clicking survey {survey_id}: {str(e)}")
                return {
                    'success': False,
                    'status': 'error',
                    'message': f'Error clicking survey: {str(e)}'
                }

            # Check if we were redirected to an external survey site
            # Most surveys redirect to external sites with their own formats
            # This is a simplified implementation

            # Wait for the survey to load
            self.random_delay(5, 8)

            # Use the LLM to analyze the survey and generate responses
            completion_result = self._process_survey_content(browser, survey)

            if completion_result['success']:
                # Survey completed successfully
                completion_time = datetime.datetime.now()

                # Update survey status in database
                self.db_manager.execute(
                    """
                    UPDATE paid_surveys
                    SET status = %s, completion_time = %s
                    WHERE id = %s
                    """,
                    ('completed', completion_time, db_id)
                )

                # Update platform statistics
                self._increment_platform_stat(platform, "surveys_completed")

                # Calculate time spent
                time_spent = (completion_time - start_time).total_seconds() / 60.0

                self.log_info(f"Successfully completed survey {survey_id} on {platform} in {time_spent:.1f} minutes")

                return {
                    'success': True,
                    'status': 'completed',
                    'reward': survey['reward'],
                    'currency': survey['currency'],
                    'time_spent': time_spent
                }
            else:
                # Survey not completed
                status = completion_result.get('status', 'failed')

                # Update survey status in database
                self.db_manager.execute(
                    """
                    UPDATE paid_surveys
                    SET status = %s, notes = %s
                    WHERE id = %s
                    """,
                    (status, completion_result.get('message', ''), db_id)
                )

                # If disqualified, update platform statistics
                if status == 'disqualified':
                    self._increment_platform_stat(platform, "surveys_disqualified")

                self.log_info(
                    f"Survey {survey_id} on {platform} not completed: {completion_result.get('message', 'Unknown error')}")

                return completion_result

        except Exception as e:
            self.log_error(f"Error completing survey {survey_id} on {platform}: {str(e)}")

            # Update survey status in database if we have a db_id
            if 'db_id' in locals():
                self.db_manager.execute(
                    """
                    UPDATE paid_surveys
                    SET status = %s, notes = %s
                    WHERE id = %s
                    """,
                    ('error', str(e), db_id)
                )

            return {
                'success': False,
                'status': 'error',
                'message': str(e)
            }

    def _increment_platform_stat(self, platform: str, stat: str) -> None:
        """
        Increment a platform statistic.

        Args:
            platform: Platform name
            stat: Statistic to increment
        """
        # Get current value
        result = self.db_manager.query(
            f"""
            SELECT {stat} FROM survey_platforms
            WHERE platform = %s
            """,
            (platform,)
        )

        if not result:
            # Create platform record with default values
            self._update_platform_status(platform, stat, 1)
            return

        # Increment value
        current_value = result[0][stat] or 0
        new_value = current_value + 1

        # Update value
        self._update_platform_status(platform, stat, new_value)

    def _process_survey_content(self, browser, survey: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process survey content and respond to questions.

        Args:
            browser: Browser instance
            survey: Survey dictionary

        Returns:
            Dictionary with the result of the processing
        """
        try:
            # Check if we're disqualified or redirected
            if self._check_disqualification(browser):
                return {
                    'success': False,
                    'status': 'disqualified',
                    'message': 'Disqualified from survey'
                }

            # Get persona data for answering questions
            persona = {}
            categories = ['personal', 'location', 'work', 'education', 'household', 'interests', 'shopping',
                          'technology', 'media', 'health']

            for category in categories:
                persona[category] = self._get_persona_category(category)

            # This is a simplified implementation of survey processing
            # In a real implementation, we would need to:
            # 1. Analyze the current page to identify question types
            # 2. Extract questions and answer options
            # 3. Determine appropriate answers based on our persona
            # 4. Fill in the answers
            # 5. Navigate to the next page
            # 6. Repeat until the survey is complete

            # For this simplified version, we'll simulate going through a few pages

            # Number of pages to process (random for simulation)
            num_pages = random.randint(5, 15) if survey['duration'] > 0 else random.randint(10, 25)

            for page in range(num_pages):
                self.log_info(f"Processing survey page {page + 1} of approximately {num_pages}")

                # Process the current page
                success = self._process_survey_page(browser, persona)

                if not success:
                    return {
                        'success': False,
                        'status': 'error',
                        'message': f'Failed to process page {page + 1}'
                    }

                # Click Next/Submit button
                next_buttons = browser.find_elements_by_xpath(
                    "//button[contains(text(), 'Next') or contains(text(), 'Continue') or contains(text(), 'Submit')]"
                )

                if next_buttons:
                    next_buttons[0].click()
                    self.random_delay(3, 6)
                else:
                    # Try alternative buttons
                    alt_buttons = browser.find_elements_by_xpath(
                        "//button[@type='submit'] or //input[@type='submit']"
                    )

                    if alt_buttons:
                        alt_buttons[0].click()
                        self.random_delay(3, 6)
                    else:
                        # No obvious next button, check if we're on a completion page
                        if self._check_completion(browser):
                            return {
                                'success': True,
                                'status': 'completed',
                                'message': 'Survey completed successfully'
                            }
                        else:
                            # Try to find any button that might be next
                            all_buttons = browser.find_elements_by_xpath("//button or //input[@type='button']")
                            if all_buttons:
                                all_buttons[-1].click()  # Try the last button
                                self.random_delay(3, 6)
                            else:
                                return {
                                    'success': False,
                                    'status': 'error',
                                    'message': 'Could not find next button'
                                }

                # Check for disqualification after each page
                if self._check_disqualification(browser):
                    return {
                        'success': False,
                        'status': 'disqualified',
                        'message': 'Disqualified from survey'
                    }

                # Check for completion page
                if self._check_completion(browser):
                    return {
                        'success': True,
                        'status': 'completed',
                        'message': 'Survey completed successfully'
                    }

            # If we've gone through all pages and didn't hit a clear completion page
            # Check final page for completion indicators
            if self._check_completion(browser):
                return {
                    'success': True,
                    'status': 'completed',
                    'message': 'Survey completed successfully'
                }
            else:
                return {
                    'success': False,
                    'status': 'incomplete',
                    'message': 'Reached end of simulated pages but no clear completion'
                }

        except Exception as e:
            self.log_error(f"Error processing survey content: {str(e)}")
            return {
                'success': False,
                'status': 'error',
                'message': str(e)
            }

    def _process_survey_page(self, browser, persona: Dict[str, Dict[str, str]]) -> bool:
        """
        Process a single survey page.

        Args:
            browser: Browser instance
            persona: Persona data for answering questions

        Returns:
            True if successful, False otherwise
        """
        try:
            # Look for different question types and answer them

            # Multiple choice questions (radio buttons)
            radio_buttons = browser.find_elements_by_xpath("//input[@type='radio']")
            if radio_buttons:
                # Group radio buttons by name attribute
                radio_groups = {}
                for button in radio_buttons:
                    name = button.get_attribute("name")
                    if name not in radio_groups:
                        radio_groups[name] = []
                    radio_groups[name].append(button)

                # Answer each question group
                for name, buttons in radio_groups.items():
                    # Randomly select an option (weighted towards middle options)
                    if len(buttons) > 2:
                        # Prefer middle options for Likert scales
                        weights = []
                        mid_index = len(buttons) // 2
                        for i in range(len(buttons)):
                            # Calculate weight based on distance from middle
                            weight = 1.0 - min(abs(i - mid_index) / len(buttons), 0.7)
                            weights.append(weight)

                        # Normalize weights
                        total_weight = sum(weights)
                        weights = [w / total_weight for w in weights]

                        # Select based on weights
                        selected_index = random.choices(range(len(buttons)), weights=weights)[0]
                    else:
                        # For binary choices, select randomly
                        selected_index = random.randint(0, len(buttons) - 1)

                    # Click the selected option
                    buttons[selected_index].click()
                    self.random_delay(0.5, 1.5)

            # Checkboxes
            checkboxes = browser.find_elements_by_xpath("//input[@type='checkbox']")
            if checkboxes:
                # Group checkboxes by name attribute
                checkbox_groups = {}
                for checkbox in checkboxes:
                    name = checkbox.get_attribute("name")
                    if name not in checkbox_groups:
                        checkbox_groups[name] = []
                    checkbox_groups[name].append(checkbox)

                # Answer each question group
                for name, boxes in checkbox_groups.items():
                    # Decide how many to select (1-3 or 30-60% of options)
                    if len(boxes) <= 5:
                        num_to_select = random.randint(1, min(3, len(boxes)))
                    else:
                        num_to_select = int(len(boxes) * random.uniform(0.3, 0.6))

                    # Select random checkboxes
                    selected_indices = random.sample(range(len(boxes)), num_to_select)
                    for idx in selected_indices:
                        boxes[idx].click()
                        self.random_delay(0.5, 1.0)

            # Dropdown selects
            selects = browser.find_elements_by_xpath("//select")
            if selects:
                for select in selects:
                    # Find all options
                    options = select.find_elements_by_xpath(".//option")

                    # Filter out placeholder options (usually the first one)
                    valid_options = [opt for opt in options if opt.get_attribute("value")]

                    if valid_options:
                        # Select a random option
                        option_to_select = random.choice(valid_options)
                        option_to_select.click()
                        self.random_delay(0.5, 1.5)

            # Text inputs
            text_inputs = browser.find_elements_by_xpath("//input[@type='text'] or //textarea")
            if text_inputs:
                for text_input in text_inputs:
                    # Try to determine what kind of information is needed based on attributes
                    name = text_input.get_attribute("name").lower() if text_input.get_attribute("name") else ""
                    placeholder = text_input.get_attribute("placeholder").lower() if text_input.get_attribute(
                        "placeholder") else ""

                    # Generate appropriate text based on input type
                    if "name" in name or "name" in placeholder:
                        text_input.send_keys(persona["personal"].get("name", "John Smith"))
                    elif "age" in name or "age" in placeholder:
                        text_input.send_keys(persona["personal"].get("age", "35"))
                    elif "city" in name or "city" in placeholder:
                        text_input.send_keys(persona["location"].get("city", "Amsterdam"))
                    elif "zip" in name or "postal" in name or "post" in placeholder:
                        text_input.send_keys(persona["location"].get("postal_code", "1000 AA"))
                    elif "email" in name or "email" in placeholder:
                        text_input.send_keys(persona["personal"].get("email", "example@example.com"))
                    elif "phone" in name or "phone" in placeholder:
                        text_input.send_keys(persona["personal"].get("phone", "0612345678"))
                    elif "occupation" in name or "job" in name or "work" in placeholder:
                        text_input.send_keys(persona["work"].get("occupation", "Office Manager"))
                    elif "education" in name or "school" in placeholder:
                        text_input.send_keys(persona["education"].get("level", "Bachelor's Degree"))
                    elif "income" in name or "salary" in placeholder:
                        text_input.send_keys(persona["work"].get("income", "45000"))
                    else:
                        # Generic response for unknown fields - short text
                        if text_input.tag_name == "textarea":
                            # Longer text for textareas
                            text_input.send_keys(
                                "I find this topic interesting. I have some experience with this and would like to share my perspective. Overall, I think it depends on the specific situation and context.")
                        else:
                            # Shorter text for regular inputs
                            text_input.send_keys("Varies depending on situation")

                    self.random_delay(1, 2)

            # Range sliders
            sliders = browser.find_elements_by_xpath("//input[@type='range']")
            if sliders:
                for slider in sliders:
                    # Get the min, max, and step values
                    min_val = float(slider.get_attribute("min") or "0")
                    max_val = float(slider.get_attribute("max") or "100")

                    # Prefer values in the middle range (40-60% of the way)
                    range_size = max_val - min_val
                    middle_value = min_val + range_size * random.uniform(0.4, 0.6)

                    # Use JavaScript to set the value (more reliable than trying to drag)
                    browser.execute_script(f"arguments[0].value = {middle_value};", slider)
                    self.random_delay(0.5, 1.5)

            # Star ratings
            star_ratings = browser.find_elements_by_xpath(
                "//div[contains(@class, 'rating') or contains(@class, 'stars')]//input")
            if star_ratings:
                # Group by name attribute
                rating_groups = {}
                for rating in star_ratings:
                    name = rating.get_attribute("name")
                    if name not in rating_groups:
                        rating_groups[name] = []
                    rating_groups[name].append(rating)

                # Answer each rating group
                for name, ratings in rating_groups.items():
                    # Prefer slightly positive ratings (70% chance of 4-5 stars)
                    if random.random() < 0.7 and len(ratings) >= 5:
                        # High rating
                        ratings[-1].click() if random.random() < 0.5 else ratings[-2].click()
                    else:
                        # Random rating
                        random.choice(ratings).click()

                    self.random_delay(0.5, 1.5)

            return True

        except Exception as e:
            self.log_error(f"Error processing survey page: {str(e)}")
            return False

    def _check_disqualification(self, browser) -> bool:
        """
        Check if we've been disqualified from the survey.

        Args:
            browser: Browser instance

        Returns:
            True if disqualified, False otherwise
        """
        # Look for common disqualification indicators
        disq_texts = [
            "not qualify", "disqualified", "does not match", "not eligible",
            "not suitable", "does not fit", "quota full", "thank you for your interest",
            "unfortunately", "sorry", "closed", "already completed"
        ]

        page_text = browser.page_source.lower()

        # Check for disqualification text
        for text in disq_texts:
            if text in page_text:
                return True

        # Check for redirect to dashboard or homepage
        current_url = browser.current_url.lower()
        if "dashboard" in current_url or "home" in current_url or "profile" in current_url:
            # We've been redirected away from the survey
            return True

        return False

    def _check_completion(self, browser) -> bool:
        """
        Check if the survey has been completed.

        Args:
            browser: Browser instance

        Returns:
            True if completed, False otherwise
        """
        # Look for common completion indicators
        completion_texts = [
            "thank you", "survey complete", "successfully completed",
            "survey submitted", "your responses have been recorded",
            "you will receive", "points awarded", "reward", "credit"
        ]

        page_text = browser.page_source.lower()

        # Check for completion text
        for text in completion_texts:
            if text in page_text:
                return True

        # Check for redirect to completion page
        current_url = browser.current_url.lower()
        if "complete" in current_url or "finished" in current_url or "thank" in current_url:
            return True

        return False

    def _check_earnings(self, browser, platform: str) -> float:
        """
        Check current earnings on a platform.

        Args:
            browser: Browser instance
            platform: Platform name

        Returns:
            Current earnings amount
        """
        try:
            earnings = 0.0
            currency = "EUR"

            if platform.lower() == "euroclix":
                # Navigate to account or balance page
                browser.get("https://www.euroclix.nl/mijn-account/")
                self.random_delay(2, 4)

                # Look for balance element
                balance_elements = browser.find_elements_by_xpath(
                    "//div[contains(@class, 'balance') or contains(@class, 'saldo')]"
                )

                if balance_elements:
                    balance_text = balance_elements[0].text.strip()
                    balance_match = re.search(r'€\s*(\d+[.,]?\d*)', balance_text)
                    if balance_match:
                        earnings = float(balance_match.group(1).replace(',', '.'))

            elif platform.lower() == "panelclix":
                # Navigate to account page
                browser.get("https://www.panelclix.nl/account")
                self.random_delay(2, 4)

                # Look for balance element
                balance_elements = browser.find_elements_by_xpath(
                    "//div[contains(@class, 'balance') or contains(@class, 'saldo')]"
                )

                if balance_elements:
                    balance_text = balance_elements[0].text.strip()
                    balance_match = re.search(r'€\s*(\d+[.,]?\d*)', balance_text)
                    if balance_match:
                        earnings = float(balance_match.group(1).replace(',', '.'))

            elif platform.lower() == "toluna":
                # Navigate to points page
                browser.get("https://us.toluna.com/account")
                self.random_delay(2, 4)

                # Look for points element
                points_elements = browser.find_elements_by_xpath(
                    "//div[contains(@class, 'points') or contains(@class, 'balance')]"
                )

                if points_elements:
                    points_text = points_elements[0].text.strip()
                    points_match = re.search(r'(\d+[.,]?\d*)', points_text)
                    if points_match:
                        points = float(points_match.group(1).replace(',', ''))
                        # Convert points to EUR (simplified conversion)
                        earnings = points / 100.0

            elif platform.lower() == "surveyjunkie":
                # Navigate to account page
                browser.get("https://www.surveyjunkie.com/account")
                self.random_delay(2, 4)

                # Look for balance element
                balance_elements = browser.find_elements_by_xpath(
                    "//div[contains(@class, 'balance') or contains(@class, 'points')]"
                )

                if balance_elements:
                    balance_text = balance_elements[0].text.strip()
                    balance_match = re.search(r'\$\s*(\d+[.,]?\d*)', balance_text)
                    if balance_match:
                        earnings = float(balance_match.group(1))
                        currency = "USD"

            # Update earnings in database
            self._update_platform_status(platform, "total_earnings", earnings)
            self._update_platform_status(platform, "currency", currency)

            self.log_info(f"Current earnings on {platform}: {earnings} {currency}")

            return earnings

        except Exception as e:
            self.log_error(f"Error checking earnings on {platform}: {str(e)}")
            return 0.0

    def _survey_limit_reached(self, platform: str) -> bool:
        """
        Check if we've reached the daily survey limit for a platform.

        Args:
            platform: Platform name

        Returns:
            True if limit reached, False otherwise
        """
        # Get today's date at midnight
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Get surveys completed today
        result = self.db_manager.query(
            """
            SELECT COUNT(*) as count FROM paid_surveys
            WHERE platform = %s AND status = 'completed' AND start_time >= %s
            """,
            (platform, today)
        )

        if not result:
            return False

        surveys_today = result[0]['count']

        return surveys_today >= self.max_daily_surveys

    def run(self) -> Dict[str, Any]:
        """
        Execute the paid surveys strategy.

        Returns:
            Dictionary with the result of the execution
        """
        self.log_info("Running paid surveys strategy")

        total_income = 0.0
        total_currency = "EUR"
        surveys_completed = 0

        try:
            # Initialize browser
            browser = self.browser_manager.get_browser()

            try:
                # Process each platform
                for platform in self.survey_platforms:
                    try:
                        # Check if we've reached the daily limit for this platform
                        if self._survey_limit_reached(platform):
                            self.log_info(f"Daily survey limit reached for {platform}")
                            continue

                        # Log in to platform
                        if not self._login_to_platform(browser, platform):
                            self.log_error(f"Failed to log in to {platform}")
                            continue

                        # Get available surveys
                        available_surveys = self._get_available_surveys(browser, platform)

                        if not available_surveys:
                            self.log_info(f"No available surveys on {platform}")

                            # Check earnings
                            self._check_earnings(browser, platform)

                            continue

                        # Sort surveys by reward (highest first)
                        available_surveys.sort(key=lambda s: s['reward'], reverse=True)

                        # Take up to 2 surveys per platform
                        surveys_to_take = min(len(available_surveys), 2)
                        platform_surveys_completed = 0

                        for i in range(surveys_to_take):
                            survey = available_surveys[i]

                            # Complete the survey
                            result = self._complete_survey(browser, survey)

                            if result['success']:
                                # Completed successfully
                                platform_surveys_completed += 1
                                surveys_completed += 1

                                # Add to total income
                                reward = result.get('reward', survey['reward'])
                                currency = result.get('currency', survey['currency'])

                                if currency == total_currency:
                                    total_income += reward
                                elif total_currency == "EUR" and currency == "USD":
                                    # Convert USD to EUR (simplified)
                                    total_income += reward * 0.85
                                elif total_currency == "USD" and currency == "EUR":
                                    # Convert EUR to USD and change total currency
                                    total_income = (total_income * 1.18) + reward
                                    total_currency = "USD"

                                self.log_info(f"Completed survey {i + 1}/{surveys_to_take} on {platform}")
                            else:
                                self.log_info(
                                    f"Survey {i + 1}/{surveys_to_take} on {platform} not completed: {result.get('status', 'error')}")

                            # If we've reached the daily limit, stop
                            if self._survey_limit_reached(platform):
                                self.log_info(f"Daily survey limit reached for {platform}")
                                break

                        # Check earnings after completing surveys
                        self._check_earnings(browser, platform)

                    except Exception as e:
                        self.log_error(f"Error processing platform {platform}: {str(e)}")

                # Return the results
                return {
                    'success': surveys_completed > 0,
                    'income': total_income,
                    'currency': total_currency,
                    'description': f'Income from {surveys_completed} completed surveys',
                    'details': {
                        'surveys_completed': surveys_completed,
                        'platforms_processed': len(self.survey_platforms)
                    }
                }

            finally:
                # Always close the browser
                self.browser_manager.close_browser(browser)

        except Exception as e:
            self.log_error(f"Error executing paid surveys strategy: {str(e)}")
            return {
                'success': False,
                'income': 0,
                'currency': 'EUR',
                'description': 'Paid surveys strategy failed',
                'details': {'error': str(e)}
            }