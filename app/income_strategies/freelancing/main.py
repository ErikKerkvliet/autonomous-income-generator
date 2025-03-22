# app/income_strategies/freelancing/main.py
"""
Freelancing Strategy for the Autonomous Income Generator.

This strategy uses Upwork to find, bid on, and complete freelance tasks
autonomously.
"""
import logging
import time
import random
import datetime
from typing import Dict, Any, List, Optional
import json
import re

from app.income_strategies.strategy_base import IncomeStrategy
from app.web.browser_manager import BrowserManager
from app.managers.api_manager import APIManager


class FreelancingStrategy(IncomeStrategy):
    """
    Strategy for generating income through freelancing on Upwork.
    """

    # Strategy metadata
    STRATEGY_NAME = "Upwork Freelancing"
    STRATEGY_DESCRIPTION = "Automatically bids on and completes coding tasks on Upwork"

    # Run every 4 hours
    run_interval = 240

    # Maximum number of active jobs
    MAX_ACTIVE_JOBS = 3

    # Job search criteria
    SEARCH_KEYWORDS = ["python", "automation", "webscraping", "data analysis", "bot"]
    JOB_TYPES = ["fixed", "hourly"]
    MIN_BUDGET = 20  # Minimum budget for fixed-price jobs
    MAX_BUDGET = 500  # Maximum budget for fixed-price jobs
    MIN_HOURLY_RATE = 15  # Minimum hourly rate

    # Bid criteria
    BID_PERCENTAGE = 0.9  # Bid at 90% of the client's budget
    MIN_BID = 20  # Minimum bid amount

    def _initialize(self) -> None:
        """
        Initialize freelancing strategy resources.
        """
        self.api_manager = APIManager(self.config)
        self.browser_manager = BrowserManager(self.config)

        # Load strategy configuration
        self.search_keywords = self.config.get(
            "STRATEGIES",
            "FREELANCING_KEYWORDS",
            ",".join(self.SEARCH_KEYWORDS)
        ).split(",")

        self.job_types = self.config.get(
            "STRATEGIES",
            "FREELANCING_JOB_TYPES",
            ",".join(self.JOB_TYPES)
        ).split(",")

        self.min_budget = float(self.config.get(
            "STRATEGIES",
            "FREELANCING_MIN_BUDGET",
            str(self.MIN_BUDGET)
        ))

        self.max_budget = float(self.config.get(
            "STRATEGIES",
            "FREELANCING_MAX_BUDGET",
            str(self.MAX_BUDGET)
        ))

        self.min_hourly_rate = float(self.config.get(
            "STRATEGIES",
            "FREELANCING_MIN_HOURLY_RATE",
            str(self.MIN_HOURLY_RATE)
        ))

        self.bid_percentage = float(self.config.get(
            "STRATEGIES",
            "FREELANCING_BID_PERCENTAGE",
            str(self.BID_PERCENTAGE)
        ))

        self.max_active_jobs = int(self.config.get(
            "STRATEGIES",
            "FREELANCING_MAX_ACTIVE_JOBS",
            str(self.MAX_ACTIVE_JOBS)
        ))

        # Initialize database tables
        self._initialize_database()

        self.log_info(f"Initialized freelancing strategy with keywords: {self.search_keywords}")

    def _initialize_database(self) -> None:
        """
        Initialize database tables for freelancing strategy.
        """
        # Create jobs table
        self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS freelancing_jobs (
                id VARCHAR(255) PRIMARY KEY,
                title VARCHAR(255),
                client_id VARCHAR(255),
                client_name VARCHAR(255),
                job_type VARCHAR(50),
                budget FLOAT,
                description TEXT,
                requirements TEXT,
                status VARCHAR(50),
                bid_amount FLOAT,
                bid_date DATETIME,
                accepted_date DATETIME,
                completed_date DATETIME,
                deadline DATETIME,
                payment_amount FLOAT,
                payment_date DATETIME,
                last_updated DATETIME
            )
        """)

        # Create job tasks table
        self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS freelancing_tasks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                job_id VARCHAR(255),
                task_description TEXT,
                status VARCHAR(50),
                created_date DATETIME,
                completed_date DATETIME,
                FOREIGN KEY (job_id) REFERENCES freelancing_jobs(id)
            )
        """)

        # Create job messages table
        self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS freelancing_messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                job_id VARCHAR(255),
                sender VARCHAR(50),
                message TEXT,
                timestamp DATETIME,
                FOREIGN KEY (job_id) REFERENCES freelancing_jobs(id)
            )
        """)

    def _login_to_upwork(self, browser) -> bool:
        """
        Log in to Upwork.

        Args:
            browser: Browser instance

        Returns:
            True if login successful, False otherwise
        """
        try:
            # Get Upwork credentials
            credentials = self.config.get_website_credentials("UPWORK")
            if not credentials:
                self.log_error("No credentials found for Upwork")
                return False

            # Navigate to Upwork login page
            browser.get("https://www.upwork.com/ab/account-security/login")
            self.random_delay(2, 4)

            # Enter username/email
            username_field = browser.find_element_by_id("login_username")
            username_field.send_keys(credentials["username"])
            self.random_delay(1, 2)

            # Click continue
            continue_button = browser.find_element_by_id("login_password_continue")
            continue_button.click()
            self.random_delay(2, 4)

            # Enter password
            password_field = browser.find_element_by_id("login_password")
            password_field.send_keys(credentials["password"])
            self.random_delay(1, 2)

            # Click login button
            login_button = browser.find_element_by_id("login_control_continue")
            login_button.click()
            self.random_delay(3, 6)

            # Check if login was successful
            # This might require handling 2FA or checking for specific elements on the dashboard

            # Check if we're on the dashboard
            if "desk" in browser.current_url or "dashboard" in browser.current_url:
                self.log_info("Successfully logged in to Upwork")
                return True
            else:
                # Check for 2FA
                if "security-question" in browser.current_url or "2fa" in browser.current_url:
                    self.log_error("2FA required for Upwork login")
                    return False

                self.log_error("Failed to log in to Upwork")
                return False

        except Exception as e:
            self.log_error(f"Error logging in to Upwork: {str(e)}")
            return False

    def _search_for_jobs(self, browser) -> List[Dict[str, Any]]:
        """
        Search for jobs on Upwork.

        Args:
            browser: Browser instance

        Returns:
            List of job dictionaries
        """
        jobs_found = []

        try:
            for keyword in self.search_keywords:
                self.log_info(f"Searching for jobs with keyword: {keyword}")

                # Navigate to job search page
                search_url = f"https://www.upwork.com/search/jobs/?q={keyword}&sort=recency"
                browser.get(search_url)
                self.random_delay(2, 4)

                # Get job listings
                job_elements = browser.find_elements_by_xpath("//section[contains(@class, 'job-tile')]")
                self.log_info(f"Found {len(job_elements)} job listings for '{keyword}'")

                for job_element in job_elements[:10]:  # Limit to first 10 results
                    try:
                        # Extract job information
                        job_id = job_element.get_attribute("data-job-id") or str(random.randint(10000, 99999))

                        title_element = job_element.find_element_by_xpath(".//h2[contains(@class, 'job-title')]")
                        title = title_element.text.strip()

                        # Extract client information
                        client_element = job_element.find_element_by_xpath(".//div[contains(@class, 'client-name')]")
                        client_info = client_element.text.strip()
                        client_name = client_info.split('\n')[0] if '\n' in client_info else client_info
                        client_id = "client_" + str(random.randint(10000, 99999))

                        # Extract job type and budget
                        terms_element = job_element.find_element_by_xpath(".//div[contains(@class, 'job-price')]")
                        terms_text = terms_element.text.strip()

                        job_type = "fixed" if "Fixed Price" in terms_text else "hourly"
                        budget = 0.0

                        if job_type == "fixed":
                            budget_match = re.search(r'\$(\d+(?:\.\d+)?)', terms_text)
                            if budget_match:
                                budget = float(budget_match.group(1))
                        else:  # hourly
                            rate_match = re.search(r'\$(\d+(?:\.\d+)?)-\$(\d+(?:\.\d+)?)', terms_text)
                            if rate_match:
                                min_rate = float(rate_match.group(1))
                                max_rate = float(rate_match.group(2))
                                budget = (min_rate + max_rate) / 2
                            else:
                                rate_match = re.search(r'\$(\d+(?:\.\d+)?)', terms_text)
                                if rate_match:
                                    budget = float(rate_match.group(1))

                        # Extract description
                        desc_element = job_element.find_element_by_xpath(".//span[contains(@class, 'description')]")
                        description = desc_element.text.strip()

                        # Check if the job meets our criteria
                        if job_type not in self.job_types:
                            continue

                        if job_type == "fixed" and (budget < self.min_budget or budget > self.max_budget):
                            continue

                        if job_type == "hourly" and budget < self.min_hourly_rate:
                            continue

                        # Check if we've already processed this job
                        existing_job = self.db_manager.query(
                            "SELECT id FROM freelancing_jobs WHERE id = %s",
                            (job_id,)
                        )

                        if existing_job:
                            continue

                        # Add job to list
                        jobs_found.append({
                            'id': job_id,
                            'title': title,
                            'client_id': client_id,
                            'client_name': client_name,
                            'job_type': job_type,
                            'budget': budget,
                            'description': description,
                            'requirements': '',  # Will be filled when viewing job details
                            'status': 'found',
                            'bid_amount': 0.0,
                            'bid_date': None,
                            'last_updated': datetime.datetime.now()
                        })

                        self.log_info(f"Found suitable job: {title} (${budget})")

                    except Exception as e:
                        self.log_error(f"Error processing job listing: {str(e)}")
                        continue

                # Wait between keyword searches
                self.random_delay(3, 5)

        except Exception as e:
            self.log_error(f"Error searching for jobs: {str(e)}")

        return jobs_found

    def _view_job_details(self, browser, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        View job details to get additional information.

        Args:
            browser: Browser instance
            job: Job dictionary

        Returns:
            Updated job dictionary
        """
        try:
            # Navigate to job details page
            job_url = f"https://www.upwork.com/jobs/{job['id']}"
            browser.get(job_url)
            self.random_delay(2, 4)

            # Extract detailed description
            description_element = browser.find_element_by_xpath("//div[contains(@class, 'job-description')]")
            description = description_element.text.strip()
            job['description'] = description

            # Extract client details
            client_info_element = browser.find_element_by_xpath("//div[contains(@class, 'client-info')]")
            client_info = client_info_element.text.strip()

            # Extract requirements or skills
            skills_elements = browser.find_elements_by_xpath("//span[contains(@class, 'skill')]")
            skills = [element.text.strip() for element in skills_elements]
            job['requirements'] = ", ".join(skills)

            # Extract any additional details
            job['last_updated'] = datetime.datetime.now()

            return job

        except Exception as e:
            self.log_error(f"Error viewing job details: {str(e)}")
            return job

    def _evaluate_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate a job to determine if we should bid on it.

        Args:
            job: Job dictionary

        Returns:
            Job dictionary with evaluation results
        """
        try:
            # Create a job evaluation prompt
            prompt = f"""
            Evaluate this Upwork job posting to determine if it's suitable for an autonomous Python bot to bid on.

            Job Title: {job['title']}
            Job Type: {job['job_type']}
            Budget: ${job['budget']}
            Client: {job['client_name']}

            Description: {job['description']}

            Requirements: {job['requirements']}

            Please evaluate against these criteria:
            1. Is this task feasible for an automated system to complete?
            2. Is it related to Python, automation, web scraping, or data analysis?
            3. Are there any red flags or unreasonable demands?
            4. What would be a reasonable fixed bid for this job (as a percentage of the budget)?
            5. What skills or experience should be emphasized in the proposal?

            Format your response as a JSON object with these fields:
            {
            "should_bid": true/false,
                "confidence": 0-100,
                "reasons": ["reason1", "reason2"],
                "bid_percentage": 0-100,
                "suggested_bid": dollar_amount,
                "emphasis": ["skill1", "skill2"]
            }
            """

            # Get evaluation from LLM
            response = self.api_manager.generate_text(prompt)

            try:
                # Parse JSON response
                evaluation = json.loads(response)

                # Calculate bid amount
                budget = job['budget']

                if 'bid_percentage' in evaluation and evaluation['bid_percentage']:
                    bid_percentage = float(evaluation['bid_percentage']) / 100
                else:
                    bid_percentage = self.bid_percentage

                suggested_bid = float(evaluation.get('suggested_bid', budget * bid_percentage))

                # Ensure minimum bid
                suggested_bid = max(suggested_bid, self.MIN_BID)

                # Update job with evaluation results
                job['evaluation'] = {
                    'should_bid': evaluation.get('should_bid', False),
                    'confidence': evaluation.get('confidence', 0),
                    'reasons': evaluation.get('reasons', []),
                    'emphasis': evaluation.get('emphasis', [])
                }

                job['bid_amount'] = suggested_bid

                if job['evaluation']['should_bid']:
                    job['status'] = 'approved'
                else:
                    job['status'] = 'rejected'

                return job

            except json.JSONDecodeError:
                self.log_error(f"Error parsing LLM response for job evaluation: {response[:100]}...")

                # Default to not bidding if we can't parse the response
                job['evaluation'] = {
                    'should_bid': False,
                    'confidence': 0,
                    'reasons': ["Error evaluating job"],
                    'emphasis': []
                }

                job['status'] = 'rejected'
                return job

        except Exception as e:
            self.log_error(f"Error evaluating job: {str(e)}")
            job['status'] = 'error'
            return job

    def _generate_proposal(self, job: Dict[str, Any]) -> str:
        """
        Generate a proposal for a job.

        Args:
            job: Job dictionary

        Returns:
            Proposal text
        """
        try:
            # Gather emphasis points from evaluation
            emphasis = job.get('evaluation', {}).get('emphasis', [])
            emphasis_str = ", ".join(emphasis) if emphasis else "Python automation expertise"

            # Create a proposal generation prompt
            prompt = f"""
            Write a compelling Upwork proposal for this job:

            Job Title: {job['title']}
            Job Type: {job['job_type']}
            Budget: ${job['budget']}
            My Bid: ${job['bid_amount']}

            Description: {job['description']}

            Requirements: {job['requirements']}

            Emphasize these skills/experiences: {emphasis_str}

            Guidelines for the proposal:
            1. Keep it concise (250-350 words)
            2. Address the client's specific needs
            3. Explain your approach to solving their problem
            4. Mention relevant experience with similar projects
            5. Explain why your bid amount is appropriate
            6. Ask a thoughtful question about the project
            7. Include a call to action

            Write the proposal in first person as an experienced developer.
            Do not use generic templates or mentions of "I noticed your job posting."
            Focus on substance over fluff.
            """

            # Get proposal from LLM
            proposal = self.api_manager.generate_text(prompt)

            return proposal

        except Exception as e:
            self.log_error(f"Error generating proposal: {str(e)}")
            return "I'm interested in your job posting and believe I have the skills necessary to complete this project successfully. I have experience with similar tasks and can deliver quality results within your timeline. I'd be happy to discuss the project further."

    def _submit_proposal(self, browser, job: Dict[str, Any]) -> bool:
        """
        Submit a proposal for a job.

        Args:
            browser: Browser instance
            job: Job dictionary

        Returns:
            True if proposal was submitted, False otherwise
        """
        try:
            # Generate proposal text
            proposal_text = self._generate_proposal(job)

            # Navigate to job page
            job_url = f"https://www.upwork.com/jobs/{job['id']}"
            browser.get(job_url)
            self.random_delay(2, 4)

            # Find and click the "Submit a Proposal" button
            submit_button = browser.find_element_by_xpath("//a[contains(text(), 'Submit a Proposal')]")
            submit_button.click()
            self.random_delay(3, 5)

            # Fill out proposal form
            # Note: This part will need to be customized based on Upwork's actual form structure

            # Set bid amount
            if job['job_type'] == 'fixed':
                bid_input = browser.find_element_by_xpath("//input[contains(@name, 'amount')]")
                bid_input.clear()
                bid_input.send_keys(str(int(job['bid_amount'])))
            else:  # hourly
                bid_input = browser.find_element_by_xpath("//input[contains(@name, 'hourlyRate')]")
                bid_input.clear()
                bid_input.send_keys(str(int(job['bid_amount'])))

            self.random_delay(1, 2)

            # Fill in proposal text
            proposal_textarea = browser.find_element_by_xpath("//textarea[contains(@name, 'coverLetter')]")
            proposal_textarea.send_keys(proposal_text)
            self.random_delay(2, 3)

            # Click submit button
            submit_proposal_button = browser.find_element_by_xpath("//button[contains(text(), 'Submit')]")
            submit_proposal_button.click()
            self.random_delay(3, 5)

            # Check if submission was successful
            success_elements = browser.find_elements_by_xpath(
                "//div[contains(text(), 'Proposal submitted') or contains(text(), 'Success')]")

            if success_elements:
                self.log_info(f"Successfully submitted proposal for job: {job['title']}")

                # Update job status
                job['status'] = 'bid'
                job['bid_date'] = datetime.datetime.now()

                # Save to database
                self._save_job(job)

                return True
            else:
                self.log_warning(f"May have failed to submit proposal for job: {job['title']}")
                return False

        except Exception as e:
            self.log_error(f"Error submitting proposal: {str(e)}")
            return False

    def _check_active_jobs(self, browser) -> List[Dict[str, Any]]:
        """
        Check status of active jobs.

        Args:
            browser: Browser instance

        Returns:
            List of updated job dictionaries
        """
        updated_jobs = []

        try:
            # Navigate to My Jobs page
            browser.get("https://www.upwork.com/nx/find-work/my-jobs/")
            self.random_delay(2, 4)

            # Check active contracts
            browser.find_element_by_xpath("//a[contains(text(), 'Active Contracts')]").click()
            self.random_delay(2, 4)

            # Get active job elements
            job_elements = browser.find_elements_by_xpath("//section[contains(@class, 'job-tile')]")

            for job_element in job_elements:
                try:
                    job_link = job_element.find_element_by_xpath(".//a[contains(@class, 'job-title')]")
                    title = job_link.text.strip()

                    # Extract job ID from link
                    job_url = job_link.get_attribute("href")
                    job_id_match = re.search(r'/jobs/([^/]+)', job_url)
                    job_id = job_id_match.group(1) if job_id_match else None

                    if not job_id:
                        continue

                    # Look up job in database
                    result = self.db_manager.query(
                        "SELECT * FROM freelancing_jobs WHERE id = %s",
                        (job_id,)
                    )

                    if not result:
                        # This is a new job that we didn't track before
                        continue

                    job = dict(result[0])

                    # Check if there are any messages
                    messages_element = job_element.find_elements_by_xpath(".//span[contains(text(), 'New message')]")
                    if messages_element:
                        # There are new messages, navigate to the job
                        job_link.click()
                        self.random_delay(2, 4)

                        # Process messages
                        self._process_job_messages(browser, job)

                        # Go back to jobs list
                        browser.get("https://www.upwork.com/nx/find-work/my-jobs/")
                        self.random_delay(2, 4)
                        browser.find_element_by_xpath("//a[contains(text(), 'Active Contracts')]").click()
                        self.random_delay(2, 4)

                    # Update job status
                    job['status'] = 'active'
                    job['last_updated'] = datetime.datetime.now()

                    # Add to updated jobs
                    updated_jobs.append(job)

                    # Save to database
                    self._save_job(job)

                except Exception as e:
                    self.log_error(f"Error processing active job: {str(e)}")

            # Check offers/invitations
            browser.get("https://www.upwork.com/nx/find-work/offers")
            self.random_delay(2, 4)

            # Get offer elements
            offer_elements = browser.find_elements_by_xpath("//section[contains(@class, 'offer-tile')]")

            for offer_element in offer_elements:
                try:
                    offer_title_element = offer_element.find_element_by_xpath(".//a[contains(@class, 'job-title')]")
                    title = offer_title_element.text.strip()

                    # Extract job ID
                    job_url = offer_title_element.get_attribute("href")
                    job_id_match = re.search(r'/jobs/([^/]+)', job_url)
                    job_id = job_id_match.group(1) if job_id_match else None

                    if not job_id:
                        continue

                    # Check if job exists in database
                    result = self.db_manager.query(
                        "SELECT * FROM freelancing_jobs WHERE id = %s",
                        (job_id,)
                    )

                    job = {}

                    if result:
                        job = dict(result[0])
                        job['status'] = 'offer'
                    else:
                        # This is a new job offer
                        budget_element = offer_element.find_element_by_xpath(".//span[contains(@class, 'budget')]")
                        budget_text = budget_element.text.strip()

                        budget = 0.0
                        budget_match = re.search(r'\$(\d+(?:\.\d+)?)', budget_text)
                        if budget_match:
                            budget = float(budget_match.group(1))

                        job = {
                            'id': job_id,
                            'title': title,
                            'client_id': f"client_{random.randint(10000, 99999)}",
                            'client_name': "Client",
                            'job_type': 'fixed' if 'Fixed Price' in budget_text else 'hourly',
                            'budget': budget,
                            'description': "Job offer",
                            'requirements': "",
                            'status': 'offer',
                            'bid_amount': budget,
                            'bid_date': None,
                            'last_updated': datetime.datetime.now()
                        }

                    # Navigate to the offer
                    offer_title_element.click()
                    self.random_delay(3, 5)

                    # Extract more details
                    try:
                        description_element = browser.find_element_by_xpath(
                            "//div[contains(@class, 'job-description')]")
                        job['description'] = description_element.text.strip()
                    except:
                        pass

                    # Check if we should accept the offer
                    job = self._evaluate_job(job)

                    if job['evaluation']['should_bid']:
                        # Accept the offer
                        accept_button = browser.find_element_by_xpath("//button[contains(text(), 'Accept')]")
                        accept_button.click()
                        self.random_delay(2, 4)

                        # Confirm acceptance if needed
                        confirm_buttons = browser.find_elements_by_xpath("//button[contains(text(), 'Confirm')]")
                        if confirm_buttons:
                            confirm_buttons[0].click()
                            self.random_delay(2, 4)

                        job['status'] = 'active'
                        job['accepted_date'] = datetime.datetime.now()

                        self.log_info(f"Accepted job offer: {job['title']}")
                    else:
                        # Decline the offer
                        job['status'] = 'declined'
                        self.log_info(f"Declined job offer: {job['title']}")

                    # Add to updated jobs
                    updated_jobs.append(job)

                    # Save to database
                    self._save_job(job)

                    # Go back to offers list
                    browser.get("https://www.upwork.com/nx/find-work/offers")
                    self.random_delay(2, 4)

                except Exception as e:
                    self.log_error(f"Error processing job offer: {str(e)}")

            # Check active proposals
            browser.get("https://www.upwork.com/nx/find-work/proposals")
            self.random_delay(2, 4)

            # Get proposal elements
            proposal_elements = browser.find_elements_by_xpath("//section[contains(@class, 'job-tile')]")

            for proposal_element in proposal_elements:
                try:
                    proposal_title_element = proposal_element.find_element_by_xpath(
                        ".//a[contains(@class, 'job-title')]")
                    title = proposal_title_element.text.strip()

                    # Extract job ID
                    job_url = proposal_title_element.get_attribute("href")
                    job_id_match = re.search(r'/jobs/([^/]+)', job_url)
                    job_id = job_id_match.group(1) if job_id_match else None

                    if not job_id:
                        continue

                    # Check if job exists in database
                    result = self.db_manager.query(
                        "SELECT * FROM freelancing_jobs WHERE id = %s",
                        (job_id,)
                    )

                    if not result:
                        continue

                    job = dict(result[0])

                    # Check if there's been a response
                    response_elements = proposal_element.find_elements_by_xpath(
                        ".//span[contains(text(), 'Invitation to interview') or contains(text(), 'Message')]")

                    if response_elements:
                        # Navigate to the proposal
                        proposal_title_element.click()
                        self.random_delay(2, 4)

                        # Process messages
                        self._process_job_messages(browser, job)

                        # Check if we've been hired
                        hired_elements = browser.find_elements_by_xpath(
                            "//div[contains(text(), 'You have been hired for this job')]")

                        if hired_elements:
                            job['status'] = 'active'
                            job['accepted_date'] = datetime.datetime.now()
                            self.log_info(f"Hired for job: {job['title']}")
                        else:
                            job['status'] = 'bid'

                        # Go back to proposals list
                        browser.get("https://www.upwork.com/nx/find-work/proposals")
                        self.random_delay(2, 4)

                    # Update last updated
                    job['last_updated'] = datetime.datetime.now()

                    # Add to updated jobs
                    updated_jobs.append(job)

                    # Save to database
                    self._save_job(job)

                except Exception as e:
                    self.log_error(f"Error processing job proposal: {str(e)}")

        except Exception as e:
            self.log_error(f"Error checking active jobs: {str(e)}")

        return updated_jobs

    def _process_job_messages(self, browser, job: Dict[str, Any]) -> None:
        """
        Process messages for a job.

        Args:
            browser: Browser instance
            job: Job dictionary
        """
        try:
            # Look for messages
            message_elements = browser.find_elements_by_xpath("//div[contains(@class, 'message-bubble')]")

            if not message_elements:
                return

            client_messages = []

            for message_element in message_elements:
                try:
                    # Determine if this is from the client (not us)
                    sender_elements = message_element.find_elements_by_xpath(".//div[contains(@class, 'sender-info')]")

                    if not sender_elements:
                        continue

                    sender_info = sender_elements[0].text.strip()

                    if job['client_name'] in sender_info or "Client" in sender_info:
                        # This is a message from the client
                        message_content = message_element.find_element_by_xpath(
                            ".//div[contains(@class, 'message-content')]")
                        message_text = message_content.text.strip()

                        # Save the message
                        timestamp = datetime.datetime.now()

                        self.db_manager.execute(
                            """
                            INSERT INTO freelancing_messages
                            (job_id, sender, message, timestamp)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (job['id'], 'client', message_text, timestamp)
                        )

                        client_messages.append(message_text)

                        self.log_info(f"Received message from client: {message_text[:50]}...")

                except Exception as e:
                    self.log_error(f"Error processing message: {str(e)}")

            # If we received messages from the client, respond
            if client_messages:
                self._respond_to_messages(browser, job, client_messages)

        except Exception as e:
            self.log_error(f"Error processing job messages: {str(e)}")

    def _respond_to_messages(self, browser, job: Dict[str, Any], client_messages: List[str]) -> None:
        """
        Respond to client messages.

        Args:
            browser: Browser instance
            job: Job dictionary
            client_messages: List of client messages
        """
        try:
            # Combine messages for context
            messages_context = "\n".join([f"Client: {msg}" for msg in client_messages])

            # Create a prompt for the LLM
            prompt = f"""
            You need to respond to these messages from a client on Upwork.

            Job Title: {job['title']}
            Job Description: {job['description']}

            Recent messages:
            {messages_context}

            Please write a professional, helpful response that addresses the client's questions or concerns.
            Keep the response concise (100-150 words) but thorough.
            Be positive and solution-oriented.
            If the client is asking for project updates, provide a general status update.
            If the client is asking specific technical questions, provide helpful insights.

            Write the response in first person as a professional freelancer.
            Do not use generic templates or mention that you are an AI.
            """

            # Get response from LLM
            response = self.api_manager.generate_text(prompt)

            # Find the message input field
            message_input = browser.find_element_by_xpath("//textarea[contains(@placeholder, 'Type a message')]")
            message_input.send_keys(response)
            self.random_delay(2, 3)

            # Click send button
            send_button = browser.find_element_by_xpath("//button[contains(@aria-label, 'Send message')]")
            send_button.click()
            self.random_delay(1, 3)

            # Save our response
            self.db_manager.execute(
                """
                INSERT INTO freelancing_messages
                (job_id, sender, message, timestamp)
                VALUES (%s, %s, %s, %s)
                """,
                (job['id'], 'me', response, datetime.datetime.now())
            )

            self.log_info(f"Sent response to client: {response[:50]}...")

        except Exception as e:
            self.log_error(f"Error responding to messages: {str(e)}")

    def _complete_active_tasks(self, browser, active_jobs: List[Dict[str, Any]]) -> float:
        """
        Work on and complete active tasks.

        Args:
            browser: Browser instance
            active_jobs: List of active job dictionaries

        Returns:
            Total income earned from completed tasks
        """
        total_income = 0.0

        for job in active_jobs:
            if job['status'] != 'active':
                continue

            try:
                self.log_info(f"Working on active job: {job['title']}")

                # Check if we've already created tasks for this job
                result = self.db_manager.query(
                    "SELECT * FROM freelancing_tasks WHERE job_id = %s",
                    (job['id'],)
                )

                tasks = []

                if not result:
                    # Create tasks for this job
                    tasks = self._create_tasks_for_job(job)
                else:
                    # Get existing tasks
                    tasks = [dict(task) for task in result]

                # Process incomplete tasks
                incomplete_tasks = [task for task in tasks if task['status'] != 'completed']

                for task in incomplete_tasks:
                    # Work on the task
                    task = self._work_on_task(browser, job, task)

                    # If task is completed, update the database
                    if task['status'] == 'completed':
                        self.db_manager.execute(
                            """
                            UPDATE freelancing_tasks
                            SET status = %s, completed_date = %s
                            WHERE id = %s
                            """,
                            ('completed', datetime.datetime.now(), task['id'])
                        )

                # Check if all tasks are completed
                all_completed = all(task['status'] == 'completed' for task in tasks)

                if all_completed and job['status'] == 'active':
                    # Job is complete, submit for payment
                    job = self._submit_job_completion(browser, job)

                    if job['status'] == 'completed':
                        # Record income
                        total_income += job['payment_amount']

                        self.log_info(f"Completed job: {job['title']} - Earned: ${job['payment_amount']}")

            except Exception as e:
                self.log_error(f"Error working on job {job['title']}: {str(e)}")

        return total_income

    def _create_tasks_for_job(self, job: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Create tasks for a job.

        Args:
            job: Job dictionary

        Returns:
            List of task dictionaries
        """
        tasks = []

        try:
            # Create a prompt for the LLM to break down the job into tasks
            prompt = f"""
            Break down this Upwork job into specific, actionable tasks that can be completed programmatically.

            Job Title: {job['title']}
            Job Description: {job['description']}
            Requirements: {job['requirements']}

            Please create a list of 3-7 sequential tasks that would be needed to complete this job.
            Format your response as a JSON array of task objects, where each task has a description:

            [
                {{"task_description": "Task 1 description"}},
                {{"task_description": "Task 2 description"}},
                ...
            ]

            Make sure the tasks are specific, clear, and technically feasible.
            """

            # Get response from LLM
            response = self.api_manager.generate_text(prompt)

            try:
                # Parse JSON response
                task_list = json.loads(response)

                # Insert tasks into database
                now = datetime.datetime.now()

                for task_info in task_list:
                    description = task_info.get('task_description', '')

                    if not description:
                        continue

                    self.db_manager.execute(
                        """
                        INSERT INTO freelancing_tasks
                        (job_id, task_description, status, created_date)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (job['id'], description, 'pending', now)
                    )

                    # Get the inserted task ID
                    result = self.db_manager.query(
                        """
                        SELECT LAST_INSERT_ID() as id
                        """
                    )

                    task_id = result[0]['id'] if result else 0

                    tasks.append({
                        'id': task_id,
                        'job_id': job['id'],
                        'task_description': description,
                        'status': 'pending',
                        'created_date': now,
                        'completed_date': None
                    })

                self.log_info(f"Created {len(tasks)} tasks for job: {job['title']}")

                return tasks

            except json.JSONDecodeError:
                self.log_error(f"Error parsing LLM response for task creation: {response[:100]}...")

                # Create a default task
                self.db_manager.execute(
                    """
                    INSERT INTO freelancing_tasks
                    (job_id, task_description, status, created_date)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (job['id'], "Complete the job requirements", 'pending', datetime.datetime.now())
                )

                # Get the inserted task ID
                result = self.db_manager.query(
                    """
                    SELECT LAST_INSERT_ID() as id
                    """
                )

                task_id = result[0]['id'] if result else 0

                tasks.append({
                    'id': task_id,
                    'job_id': job['id'],
                    'task_description': "Complete the job requirements",
                    'status': 'pending',
                    'created_date': datetime.datetime.now(),
                    'completed_date': None
                })

                return tasks

        except Exception as e:
            self.log_error(f"Error creating tasks for job: {str(e)}")
            return tasks

    def _work_on_task(self, browser, job: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Work on a specific task.

        Args:
            browser: Browser instance
            job: Job dictionary
            task: Task dictionary

        Returns:
            Updated task dictionary
        """
        try:
            self.log_info(f"Working on task: {task['task_description']}")

            # Update task status
            task['status'] = 'in_progress'

            self.db_manager.execute(
                """
                UPDATE freelancing_tasks
                SET status = %s
                WHERE id = %s
                """,
                ('in_progress', task['id'])
            )

            # Create a prompt for the LLM to solve the task
            prompt = f"""
            You need to complete this task for an Upwork job:

            Job Title: {job['title']}
            Job Description: {job['description']}

            Task: {task['task_description']}

            Please provide a detailed solution for this task, including:
            1. Steps taken to complete the task
            2. Any code or scripts needed (in Python)
            3. Results or output from the solution
            4. Explanation of how this addresses the client's requirements

            If this task involves coding, please provide working, well-commented code.
            """

            # Get solution from LLM
            solution = self.api_manager.generate_text(prompt, max_tokens=2000)

            # Simulate time spent working on the task
            work_time = random.randint(20, 120)  # 20 seconds to 2 minutes
            self.log_info(f"Working on task for {work_time} seconds...")
            time.sleep(min(10, work_time))  # Cap at 10 seconds for testing

            # Save the solution in the database
            # This would typically be in a solutions table, but we'll update the task for simplicity
            self.db_manager.execute(
                """
                UPDATE freelancing_tasks
                SET status = %s
                WHERE id = %s
                """,
                ('completed', task['id'])
            )

            # Update the task status
            task['status'] = 'completed'
            task['completed_date'] = datetime.datetime.now()

            # Send a message to the client about progress
            if random.random() < 0.3:  # 30% chance to send an update
                self._send_progress_update(browser, job, task, solution)

            self.log_info(f"Completed task: {task['task_description']}")

            return task

        except Exception as e:
            self.log_error(f"Error working on task: {str(e)}")
            return task

    def _send_progress_update(self, browser, job: Dict[str, Any], task: Dict[str, Any], solution: str) -> None:
        """
        Send a progress update to the client.

        Args:
            browser: Browser instance
            job: Job dictionary
            task: Task dictionary
            solution: Task solution
        """
        try:
            # Navigate to the job messages
            browser.get(f"https://www.upwork.com/messages/rooms/job_{job['id']}")
            self.random_delay(2, 4)

            # Create a progress update prompt
            prompt = f"""
            Write a brief progress update to the client for this completed task:

            Job: {job['title']}
            Task: {task['task_description']}

            Provide a concise 3-4 sentence update that:
            1. Explains what has been completed
            2. Mentions any challenges that were overcome
            3. Indicates what will be worked on next

            Keep it professional and positive. Do not include any specific code unless necessary.
            """

            # Get update message from LLM
            update_message = self.api_manager.generate_text(prompt)

            # Find the message input field
            message_input = browser.find_element_by_xpath("//textarea[contains(@placeholder, 'Type a message')]")
            message_input.send_keys(update_message)
            self.random_delay(2, 3)

            # Click send button
            send_button = browser.find_element_by_xpath("//button[contains(@aria-label, 'Send message')]")
            send_button.click()
            self.random_delay(1, 3)

            # Save our update message
            self.db_manager.execute(
                """
                INSERT INTO freelancing_messages
                (job_id, sender, message, timestamp)
                VALUES (%s, %s, %s, %s)
                """,
                (job['id'], 'me', update_message, datetime.datetime.now())
            )

            self.log_info(f"Sent progress update to client: {update_message[:50]}...")

        except Exception as e:
            self.log_error(f"Error sending progress update: {str(e)}")

    def _submit_job_completion(self, browser, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit job completion for payment.

        Args:
            browser: Browser instance
            job: Job dictionary

        Returns:
            Updated job dictionary
        """
        try:
            self.log_info(f"Submitting job completion: {job['title']}")

            # Navigate to the job page
            browser.get(f"https://www.upwork.com/ab/jobs/search/details/{job['id']}")
            self.random_delay(2, 4)

            # Click on the "Submit Work for Payment" button
            submit_button = browser.find_element_by_xpath(
                "//button[contains(text(), 'Submit Work') or contains(text(), 'Submit for Payment')]")
            submit_button.click()
            self.random_delay(2, 4)

            # Fill out the submission form
            # Create a summary prompt
            prompt = f"""
            Write a concise summary of the work completed for this Upwork job:

            Job Title: {job['title']}
            Job Description: {job['description']}

            The summary should:
            1. List the main tasks that were completed
            2. Highlight the deliverables provided
            3. Mention how the solution meets the client's requirements
            4. Thank the client for the opportunity

            Keep it professional and under 200 words.
            """

            # Get summary from LLM
            summary = self.api_manager.generate_text(prompt)

            # Find the submission textarea
            submission_textarea = browser.find_element_by_xpath(
                "//textarea[contains(@placeholder, 'Describe the work')]")
            submission_textarea.send_keys(summary)
            self.random_delay(2, 3)

            # Click the submit button
            final_submit_button = browser.find_element_by_xpath(
                "//button[contains(text(), 'Submit') and @type='submit']")
            final_submit_button.click()
            self.random_delay(3, 5)

            # Check if submission was successful
            success_elements = browser.find_elements_by_xpath(
                "//div[contains(text(), 'submitted') or contains(text(), 'Success')]")

            if success_elements:
                # Update job status
                job['status'] = 'completed'
                job['completed_date'] = datetime.datetime.now()
                job['payment_amount'] = job['bid_amount']

                # Save to database
                self._save_job(job)

                self.log_info(f"Successfully submitted job completion: {job['title']}")
            else:
                self.log_warning(f"May have failed to submit job completion: {job['title']}")

            return job

        except Exception as e:
            self.log_error(f"Error submitting job completion: {str(e)}")
            return job

    def _check_earnings(self, browser) -> float:
        """
        Check current earnings on Upwork.

        Args:
            browser: Browser instance

        Returns:
            Total earnings
        """
        try:
            # Navigate to Reports page
            browser.get("https://www.upwork.com/nx/reports/earnings")
            self.random_delay(2, 4)

            # Extract earnings information
            earnings_element = browser.find_element_by_xpath("//div[contains(@data-test, 'earnings-to-date')]")
            earnings_text = earnings_element.text.strip()

            # Parse earnings amount
            import re
            earnings_match = re.search(r'\$(\d+(?:\.\d+)?)', earnings_text)

            if earnings_match:
                earnings = float(earnings_match.group(1))
                self.log_info(f"Total Upwork earnings: ${earnings}")
                return earnings
            else:
                self.log_warning("Could not parse earnings amount")
                return 0.0

        except Exception as e:
            self.log_error(f"Error checking earnings: {str(e)}")
            return 0.0

    def _save_job(self, job: Dict[str, Any]) -> None:
        """
        Save job information to the database.

        Args:
            job: Job dictionary
        """
        try:
            # Check if job already exists
            result = self.db_manager.query(
                "SELECT id FROM freelancing_jobs WHERE id = %s",
                (job['id'],)
            )

            if result:
                # Update existing job
                self.db_manager.execute(
                    """
                    UPDATE freelancing_jobs
                    SET title = %s, client_id = %s, client_name = %s, job_type = %s,
                        budget = %s, description = %s, requirements = %s, status = %s,
                        bid_amount = %s, bid_date = %s, accepted_date = %s, completed_date = %s,
                        deadline = %s, payment_amount = %s, payment_date = %s, last_updated = %s
                    WHERE id = %s
                    """,
                    (
                        job.get('title', ''),
                        job.get('client_id', ''),
                        job.get('client_name', ''),
                        job.get('job_type', ''),
                        job.get('budget', 0.0),
                        job.get('description', ''),
                        job.get('requirements', ''),
                        job.get('status', ''),
                        job.get('bid_amount', 0.0),
                        job.get('bid_date'),
                        job.get('accepted_date'),
                        job.get('completed_date'),
                        job.get('deadline'),
                        job.get('payment_amount', 0.0),
                        job.get('payment_date'),
                        datetime.datetime.now(),
                        job['id']
                    )
                )
            else:
                # Insert new job
                self.db_manager.execute(
                    """
                    INSERT INTO freelancing_jobs
                    (id, title, client_id, client_name, job_type, budget, description, requirements,
                     status, bid_amount, bid_date, accepted_date, completed_date, deadline,
                     payment_amount, payment_date, last_updated)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        job['id'],
                        job.get('title', ''),
                        job.get('client_id', ''),
                        job.get('client_name', ''),
                        job.get('job_type', ''),
                        job.get('budget', 0.0),
                        job.get('description', ''),
                        job.get('requirements', ''),
                        job.get('status', ''),
                        job.get('bid_amount', 0.0),
                        job.get('bid_date'),
                        job.get('accepted_date'),
                        job.get('completed_date'),
                        job.get('deadline'),
                        job.get('payment_amount', 0.0),
                        job.get('payment_date'),
                        datetime.datetime.now()
                    )
                )

        except Exception as e:
            self.log_error(f"Error saving job to database: {str(e)}")

    def run(self) -> Dict[str, Any]:
        """
        Execute the freelancing strategy.

        Returns:
            Dictionary with the result of the execution
        """
        self.log_info("Running freelancing strategy")

        try:
            # Initialize browser
            browser = self.browser_manager.get_browser()

            try:
                # Login to Upwork
                if not self._login_to_upwork(browser):
                    self.log_error("Failed to log in to Upwork")
                    return {
                        'success': False,
                        'income': 0,
                        'currency': 'USD',
                        'description': 'Failed to log in to Upwork',
                        'details': {'error': 'Login failed'}
                    }

                # Check active jobs
                active_jobs = self._check_active_jobs(browser)
                self.log_info(f"Found {len(active_jobs)} active jobs")

                # Work on active jobs
                income_earned = self._complete_active_tasks(browser, active_jobs)

                # Count active jobs
                active_job_count = len([job for job in active_jobs if job['status'] == 'active'])

                # Search for new jobs if below max active jobs
                if active_job_count < self.max_active_jobs:
                    # Search for jobs
                    new_jobs = self._search_for_jobs(browser)
                    self.log_info(f"Found {len(new_jobs)} potential new jobs")

                    # Process new jobs
                    for job in new_jobs:
                        # View job details
                        job = self._view_job_details(browser, job)

                        # Evaluate job
                        job = self._evaluate_job(job)

                        # Save job to database
                        self._save_job(job)

                        # If job is approved and we're still below max active jobs
                        if job['status'] == 'approved' and active_job_count < self.max_active_jobs:
                            # Submit proposal
                            if self._submit_proposal(browser, job):
                                active_job_count += 1

                # Check overall earnings
                total_earnings = self._check_earnings(browser)

                return {
                    'success': True,
                    'income': income_earned,
                    'currency': 'USD',
                    'description': 'Income from completed Upwork jobs',
                    'details': {
                        'active_jobs': active_job_count,
                        'total_earnings': total_earnings
                    }
                }

            finally:
                # Always close the browser
                self.browser_manager.close_browser(browser)

        except Exception as e:
            self.log_error(f"Error executing freelancing strategy: {str(e)}")
            return {
                'success': False,
                'income': 0,
                'currency': 'USD',
                'description': 'Freelancing strategy execution failed',
                'details': {'error': str(e)}
            }