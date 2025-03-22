# app/web/captcha_solver.py
"""
Captcha Solver for the Autonomous Income Generator.

This module provides captcha solving capabilities using CapSolver service.
"""
import logging
import time
import json
import requests
from typing import Dict, Any, Optional


class CaptchaSolver:
    """
    Captcha solver using CapSolver API.
    """

    # CapSolver API endpoint
    API_URL = "https://api.capsolver.com"

    def __init__(self, config):
        """
        Initialize the captcha solver.

        Args:
            config: Configuration manager instance
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Get API key from configuration
        self.api_key = self.config.get("WEB_AUTOMATION", "CAPSOLVER_API_KEY", "")

        if not self.api_key:
            self.logger.warning("No CapSolver API key provided, captcha solving will not work")

    def solve_recaptcha_v2(self, website_url: str, website_key: str, invisible: bool = False) -> Optional[str]:
        """
        Solve reCAPTCHA v2 challenge.

        Args:
            website_url: URL of the website with captcha
            website_key: reCAPTCHA site key
            invisible: Whether it's an invisible reCAPTCHA

        Returns:
            reCAPTCHA response token or None if failed
        """
        if not self.api_key:
            self.logger.error("Cannot solve captcha: No API key provided")
            return None

        try:
            self.logger.info(f"Solving reCAPTCHA v2 for {website_url}")

            # Create task
            task_data = {
                "clientKey": self.api_key,
                "task": {
                    "type": "ReCaptchaV2TaskProxyLess",
                    "websiteURL": website_url,
                    "websiteKey": website_key,
                    "isInvisible": invisible
                }
            }

            # Create task
            response = requests.post(
                f"{self.API_URL}/createTask",
                json=task_data,
                timeout=30
            )

            response_data = response.json()

            if response_data.get("errorId") > 0:
                self.logger.error(f"Error creating captcha task: {response_data.get('errorDescription')}")
                return None

            task_id = response_data.get("taskId")

            if not task_id:
                self.logger.error("No task ID returned")
                return None

            # Wait for the result
            max_attempts = 60
            for attempt in range(max_attempts):
                time.sleep(3)  # Wait 3 seconds between checks

                result_data = {
                    "clientKey": self.api_key,
                    "taskId": task_id
                }

                response = requests.post(
                    f"{self.API_URL}/getTaskResult",
                    json=result_data,
                    timeout=30
                )

                result = response.json()

                if result.get("errorId") > 0:
                    self.logger.error(f"Error checking captcha task: {result.get('errorDescription')}")
                    return None

                status = result.get("status")

                if status == "ready":
                    g_recaptcha_response = result.get("solution", {}).get("gRecaptchaResponse")
                    if g_recaptcha_response:
                        self.logger.info("Successfully solved reCAPTCHA")
                        return g_recaptcha_response
                    else:
                        self.logger.error("No solution found in response")
                        return None

                self.logger.debug(f"Captcha solving in progress, status: {status}")

            self.logger.error("Captcha solving timed out")
            return None

        except Exception as e:
            self.logger.error(f"Error solving captcha: {str(e)}")
            return None

    def solve_recaptcha_v3(self, website_url: str, website_key: str, action: str, min_score: float = 0.3) -> Optional[
        str]:
        """
        Solve reCAPTCHA v3 challenge.

        Args:
            website_url: URL of the website with captcha
            website_key: reCAPTCHA site key
            action: reCAPTCHA action
            min_score: Minimum score threshold

        Returns:
            reCAPTCHA response token or None if failed
        """
        if not self.api_key:
            self.logger.error("Cannot solve captcha: No API key provided")
            return None

        try:
            self.logger.info(f"Solving reCAPTCHA v3 for {website_url}")

            # Create task
            task_data = {
                "clientKey": self.api_key,
                "task": {
                    "type": "ReCaptchaV3TaskProxyLess",
                    "websiteURL": website_url,
                    "websiteKey": website_key,
                    "pageAction": action,
                    "minScore": min_score
                }
            }

            # Create task
            response = requests.post(
                f"{self.API_URL}/createTask",
                json=task_data,
                timeout=30
            )

            response_data = response.json()

            if response_data.get("errorId") > 0:
                self.logger.error(f"Error creating captcha task: {response_data.get('errorDescription')}")
                return None

            task_id = response_data.get("taskId")

            if not task_id:
                self.logger.error("No task ID returned")
                return None

            # Wait for the result
            max_attempts = 20
            for attempt in range(max_attempts):
                time.sleep(3)  # Wait 3 seconds between checks

                result_data = {
                    "clientKey": self.api_key,
                    "taskId": task_id
                }

                response = requests.post(
                    f"{self.API_URL}/getTaskResult",
                    json=result_data,
                    timeout=30
                )

                result = response.json()

                if result.get("errorId") > 0:
                    self.logger.error(f"Error checking captcha task: {result.get('errorDescription')}")
                    return None

                status = result.get("status")

                if status == "ready":
                    g_recaptcha_response = result.get("solution", {}).get("gRecaptchaResponse")
                    if g_recaptcha_response:
                        self.logger.info("Successfully solved reCAPTCHA v3")
                        return g_recaptcha_response
                    else:
                        self.logger.error("No solution found in response")
                        return None

                self.logger.debug(f"Captcha solving in progress, status: {status}")

            self.logger.error("Captcha solving timed out")
            return None

        except Exception as e:
            self.logger.error(f"Error solving captcha: {str(e)}")
            return None

    def solve_hcaptcha(self, website_url: str, website_key: str) -> Optional[str]:
        """
        Solve hCaptcha challenge.

        Args:
            website_url: URL of the website with captcha
            website_key: hCaptcha site key

        Returns:
            hCaptcha response token or None if failed
        """
        if not self.api_key:
            self.logger.error("Cannot solve captcha: No API key provided")
            return None

        try:
            self.logger.info(f"Solving hCaptcha for {website_url}")

            # Create task
            task_data = {
                "clientKey": self.api_key,
                "task": {
                    "type": "HCaptchaTaskProxyLess",
                    "websiteURL": website_url,
                    "websiteKey": website_key
                }
            }

            # Create task
            response = requests.post(
                f"{self.API_URL}/createTask",
                json=task_data,
                timeout=30
            )

            response_data = response.json()

            if response_data.get("errorId") > 0:
                self.logger.error(f"Error creating captcha task: {response_data.get('errorDescription')}")
                return None

            task_id = response_data.get("taskId")

            if not task_id:
                self.logger.error("No task ID returned")
                return None

            # Wait for the result
            max_attempts = 30
            for attempt in range(max_attempts):
                time.sleep(3)  # Wait 3 seconds between checks

                result_data = {
                    "clientKey": self.api_key,
                    "taskId": task_id
                }

                response = requests.post(
                    f"{self.API_URL}/getTaskResult",
                    json=result_data,
                    timeout=30
                )

                result = response.json()

                if result.get("errorId") > 0:
                    self.logger.error(f"Error checking captcha task: {result.get('errorDescription')}")
                    return None

                status = result.get("status")

                if status == "ready":
                    captcha_response = result.get("solution", {}).get("gRecaptchaResponse")
                    if captcha_response:
                        self.logger.info("Successfully solved hCaptcha")
                        return captcha_response
                    else:
                        self.logger.error("No solution found in response")
                        return None

                self.logger.debug(f"Captcha solving in progress, status: {status}")

            self.logger.error("Captcha solving timed out")
            return None

        except Exception as e:
            self.logger.error(f"Error solving captcha: {str(e)}")
            return None

    def inject_recaptcha_token(self, browser, token: str) -> bool:
        """
        Inject reCAPTCHA token into the page.

        Args:
            browser: Selenium WebDriver instance
            token: reCAPTCHA token

        Returns:
            True if successful, False otherwise
        """
        try:
            # Inject token using JavaScript
            script = f"""
            document.querySelector('[name="g-recaptcha-response"]').value = "{token}";

            // For invisible reCAPTCHA
            if (typeof window.___grecaptcha_cfg !== 'undefined') {{
                Object.keys(window.___grecaptcha_cfg.clients).forEach(function(key) {{
                    var client = window.___grecaptcha_cfg.clients[key];
                    Object.keys(client).forEach(function(k) {{
                        if (key === '0' && typeof client[k].callback === 'function') {{
                            client[k].callback('{token}');
                        }}
                    }});
                }});
            }}
            """

            browser.execute_script(script)
            self.logger.info("Injected reCAPTCHA token into page")
            return True

        except Exception as e:
            self.logger.error(f"Error injecting reCAPTCHA token: {str(e)}")
            return False

    def inject_hcaptcha_token(self, browser, token: str) -> bool:
        """
        Inject hCaptcha token into the page.

        Args:
            browser: Selenium WebDriver instance
            token: hCaptcha token

        Returns:
            True if successful, False otherwise
        """
        try:
            # Inject token using JavaScript
            script = f"""
            document.querySelector('[name="h-captcha-response"]').value = "{token}";

            // Trigger callback
            if (window.hcaptcha) {{
                var iframe = document.querySelector('iframe[src*="hcaptcha.com"]');
                if (iframe) {{
                    var widgetId = iframe.getAttribute('data-hcaptcha-widget-id');
                    if (widgetId && window.hcaptcha.getResponse && window.hcaptcha.getResponse(widgetId) === "") {{
                        // Call callback if defined
                        if (window.hcaptcha.callbacks && window.hcaptcha.callbacks[widgetId]) {{
                            window.hcaptcha.callbacks[widgetId]("{token}");
                        }}
                    }}
                }}
            }}
            """

            browser.execute_script(script)
            self.logger.info("Injected hCaptcha token into page")
            return True

        except Exception as e:
            self.logger.error(f"Error injecting hCaptcha token: {str(e)}")
            return False