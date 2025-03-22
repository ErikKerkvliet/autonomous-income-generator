# app/income_strategies/content_creation/main.py
"""
Content Creation Strategy for the Autonomous Income Generator.

This strategy generates and publishes content on various platforms and
manages a Patreon account for income generation.
"""
import logging
import random
import time
from typing import Dict, Any, List, Optional
from selenium.webdriver.common.by import By
import datetime
import json

from app.income_strategies.strategy_base import IncomeStrategy
from app.web.browser_manager import BrowserManager
from app.managers.api_manager import APIManager


class ContentCreationStrategy(IncomeStrategy):
    """
    Strategy for generating income through content creation and Patreon.
    """

    # Strategy metadata
    STRATEGY_NAME = "Content Creation"
    STRATEGY_DESCRIPTION = "Generates and publishes content to attract Patreon subscribers"

    # Run every 12 hours
    run_interval = 720

    # Content platforms
    PLATFORMS = ["novel.net", "webnovel.com", "scribblehub.com"]

    def _initialize(self) -> None:
        """
        Initialize content creation strategy resources.
        """
        self.api_manager = APIManager(self.config)
        self.browser_manager = BrowserManager(self.config)

        # Load strategy configuration
        self.content_type = self.config.get(
            "STRATEGIES",
            "CONTENT_CREATION_TYPE",
            "fiction"
        )
        self.content_genre = self.config.get(
            "STRATEGIES",
            "CONTENT_CREATION_GENRE",
            "fantasy"
        )
        self.content_length = int(self.config.get(
            "STRATEGIES",
            "CONTENT_CREATION_LENGTH",
            "2000"
        ))
        self.publish_interval = int(self.config.get(
            "STRATEGIES",
            "CONTENT_CREATION_PUBLISH_INTERVAL",
            "3"
        ))

        # Store content state in database
        self._initialize_content_state()

        self.log_info(f"Initialized content creation strategy: {self.content_type}/{self.content_genre}")

    def _initialize_content_state(self) -> None:
        """
        Initialize or load content state from the database.
        """
        # Create content_creation table if not exists
        self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS content_creation (
                id VARCHAR(255) PRIMARY KEY,
                title VARCHAR(255),
                type VARCHAR(50),
                genre VARCHAR(50),
                platform VARCHAR(50),
                chapters INT,
                last_published DATETIME,
                patreon_link VARCHAR(255),
                subscribers INT,
                state TEXT
            )
        """)

        # Create content_chapters table if not exists
        self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS content_chapters (
                id INT AUTO_INCREMENT PRIMARY KEY,
                content_id VARCHAR(255),
                chapter_number INT,
                title VARCHAR(255),
                published_at DATETIME,
                word_count INT,
                published BOOLEAN,
                platforms TEXT,
                FOREIGN KEY (content_id) REFERENCES content_creation(id)
            )
        """)

        # Load active content
        result = self.db_manager.query(
            "SELECT * FROM content_creation WHERE state='active' LIMIT 1"
        )

        if not result:
            # No active content, create a new one
            self._create_new_content()
        else:
            self.log_info(f"Loaded existing content: {result[0]['title']}")

    def _create_new_content(self) -> Dict[str, Any]:
        """
        Create a new content series.

        Returns:
            Dictionary with content information
        """
        # Generate a content idea using LLM
        content_idea = self._generate_content_idea()

        # Create a unique ID for the content
        content_id = f"content_{int(time.time())}"

        # Choose a platform for initial publication
        platform = random.choice(self.PLATFORMS)

        # Current time
        now = datetime.datetime.now()

        # Insert into database
        self.db_manager.execute(
            """
            INSERT INTO content_creation 
            (id, title, type, genre, platform, chapters, last_published, subscribers, state) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                content_id,
                content_idea['title'],
                self.content_type,
                self.content_genre,
                platform,
                0,  # chapters
                now,  # last_published
                0,  # subscribers
                "active"
            )
        )

        self.log_info(f"Created new content: {content_idea['title']} on {platform}")

        content_info = {
            'id': content_id,
            'title': content_idea['title'],
            'synopsis': content_idea['synopsis'],
            'type': self.content_type,
            'genre': self.content_genre,
            'platform': platform,
            'chapters': 0,
            'last_published': now,
            'subscribers': 0
        }

        # Create the initial chapter
        self._create_new_chapter(content_info)

        return content_info

    def _generate_content_idea(self) -> Dict[str, Any]:
        """
        Generate a content idea using LLM.

        Returns:
            Dictionary with title and synopsis
        """
        self.log_info("Generating content idea using LLM")

        # Create a prompt for the LLM
        prompt = f"""
        Generate a compelling {self.content_type} series idea in the {self.content_genre} genre.

        Please provide:
        1. A catchy title
        2. A brief synopsis (2-3 paragraphs)
        3. Main characters (2-3)
        4. Key plot points (3-5)

        Format the response as JSON with the following structure:
        {{
            "title": "Title of the series",
            "synopsis": "Synopsis of the series",
            "characters": [
                {{
                    "name": "Character Name",
                    "description": "Brief character description"
                }}
            ],
            "plot_points": [
                "Plot point 1",
                "Plot point 2"
            ]
        }}
        """

        # Get response from LLM
        response = self.api_manager.generate_text(prompt)

        try:
            # Parse the JSON response
            content_idea = json.loads(response)

            # Validate required fields
            required_fields = ["title", "synopsis"]
            for field in required_fields:
                if field not in content_idea:
                    raise ValueError(f"Missing required field: {field}")

            return content_idea
        except Exception as e:
            self.log_error(f"Error parsing LLM response: {str(e)}")

            # Fallback content idea
            return {
                "title": f"{self.content_genre.capitalize()} Adventures",
                "synopsis": f"A thrilling {self.content_genre} story that will captivate readers."
            }

    def _create_new_chapter(self, content_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new chapter for the content.

        Args:
            content_info: Content information dictionary

        Returns:
            Dictionary with chapter information
        """
        # Get the next chapter number
        chapter_number = content_info['chapters'] + 1

        # Generate chapter title
        chapter_title = self._generate_chapter_title(content_info, chapter_number)

        # Current time
        now = datetime.datetime.now()

        # Insert into database (but not published yet)
        self.db_manager.execute(
            """
            INSERT INTO content_chapters
            (content_id, chapter_number, title, published_at, word_count, published, platforms)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                content_info['id'],
                chapter_number,
                chapter_title,
                now,
                0,  # word_count (will be updated after generation)
                False,  # published
                json.dumps([])  # platforms
            )
        )

        # Update content info
        self.db_manager.execute(
            "UPDATE content_creation SET chapters = %s WHERE id = %s",
            (chapter_number, content_info['id'])
        )

        self.log_info(f"Created new chapter: {chapter_title} for {content_info['title']}")

        return {
            'content_id': content_info['id'],
            'chapter_number': chapter_number,
            'title': chapter_title
        }

    def _generate_chapter_title(self, content_info: Dict[str, Any], chapter_number: int) -> str:
        """
        Generate a title for a new chapter.

        Args:
            content_info: Content information dictionary
            chapter_number: Chapter number

        Returns:
            Chapter title
        """
        # Create a prompt for the LLM
        prompt = f"""
        Generate a compelling title for Chapter {chapter_number} of "{content_info['title']}".

        Brief synopsis of the series:
        {content_info['synopsis']}

        This is a {content_info['type']} in the {content_info['genre']} genre.

        Return ONLY the title, nothing else.
        """

        # Get response from LLM
        response = self.api_manager.generate_text(prompt)

        # Clean up the response
        title = response.strip().strip('"')

        # Fallback if the title is empty or too long
        if not title or len(title) > 100:
            title = f"Chapter {chapter_number}: The Journey Continues"

        return title

    def _generate_chapter_content(self, content_info: Dict[str, Any], chapter_info: Dict[str, Any]) -> str:
        """
        Generate content for a chapter using LLM.

        Args:
            content_info: Content information dictionary
            chapter_info: Chapter information dictionary

        Returns:
            Generated chapter content
        """
        self.log_info(f"Generating content for chapter {chapter_info['chapter_number']}")

        # Get previous chapter info if not the first chapter
        previous_content = ""
        if chapter_info['chapter_number'] > 1:
            previous_result = self.db_manager.query(
                """
                SELECT id FROM content_chapters 
                WHERE content_id = %s AND chapter_number = %s
                """,
                (content_info['id'], chapter_info['chapter_number'] - 1)
            )

            if previous_result:
                previous_chapter_id = previous_result[0]['id']
                # Get the content of the previous chapter (from a content table or storage)
                # This is a placeholder - you'd need to actually fetch the content
                previous_content = "In the previous chapter, the story continued..."

        # Create a prompt for the LLM
        prompt = f"""
        Write Chapter {chapter_info['chapter_number']}: "{chapter_info['title']}" for the {content_info['type']} series "{content_info['title']}".

        Series synopsis:
        {content_info['synopsis']}

        {previous_content}

        Guidelines:
        - Write approximately {self.content_length} words.
        - This is a {content_info['genre']} story.
        - End with a hook or cliffhanger to keep readers engaged.
        - Write in an engaging, descriptive style.
        - Include dialogue and character development.

        Start writing the chapter directly, no additional notes or commentary.
        """

        # Get response from LLM
        chapter_content = self.api_manager.generate_text(
            prompt,
            max_tokens=self.content_length * 2  # Adjust based on LLM token mapping
        )

        # Update word count in database
        word_count = len(chapter_content.split())
        self.db_manager.execute(
            "UPDATE content_chapters SET word_count = %s WHERE content_id = %s AND chapter_number = %s",
            (word_count, content_info['id'], chapter_info['chapter_number'])
        )

        self.log_info(f"Generated {word_count} words for chapter {chapter_info['chapter_number']}")

        return chapter_content

    def _publish_to_platform(self, content_info: Dict[str, Any], chapter_info: Dict[str, Any], platform: str,
                             chapter_content: str) -> bool:
        """
        Publish a chapter to a specific platform.

        Args:
            content_info: Content information dictionary
            chapter_info: Chapter information dictionary
            platform: Platform to publish to
            chapter_content: Content to publish

        Returns:
            True if published successfully, False otherwise
        """
        self.log_info(f"Publishing chapter {chapter_info['chapter_number']} to {platform}")

        try:
            # Get platform credentials
            credentials = self.config.get_website_credentials(platform)
            if not credentials:
                self.log_error(f"No credentials found for {platform}")
                return False

            # Initialize browser
            browser = self.browser_manager.get_browser()

            # Log in to the platform
            if platform == "novel.net":
                return self._publish_to_novel_net(browser, credentials, content_info, chapter_info, chapter_content)
            elif platform == "webnovel.com":
                return self._publish_to_webnovel(browser, credentials, content_info, chapter_info, chapter_content)
            elif platform == "scribblehub.com":
                return self._publish_to_scribblehub(browser, credentials, content_info, chapter_info, chapter_content)
            else:
                self.log_error(f"Unsupported platform: {platform}")
                return False
        except Exception as e:
            self.log_error(f"Error publishing to {platform}: {str(e)}")
            return False
        finally:
            # Always close the browser
            self.browser_manager.close_browser(browser)

    def _publish_to_novel_net(self, browser, credentials, content_info, chapter_info, chapter_content):
        """
        Publish content to Novel.net.

        Args:
            browser: Browser instance
            credentials: Login credentials
            content_info: Content information
            chapter_info: Chapter information
            chapter_content: Chapter content

        Returns:
            True if published successfully, False otherwise
        """
        try:
            # Implementation would use selenium to:
            # 1. Navigate to novel.net
            # 2. Log in with credentials
            # 3. Navigate to story management or create a new story
            # 4. Add a new chapter
            # 5. Submit the content

            # This is a placeholder for the actual implementation
            self.log_info("Novel.net publishing not fully implemented")

            # Update published platforms in database
            self._update_published_platforms(content_info['id'], chapter_info['chapter_number'], "novel.net")

            return True
        except Exception as e:
            self.log_error(f"Error publishing to Novel.net: {str(e)}")
            return False

    def _publish_to_webnovel(self, browser, credentials, content_info, chapter_info, chapter_content):
        """
        Publish content to Webnovel.com.

        Args:
            browser: Browser instance
            credentials: Login credentials
            content_info: Content information
            chapter_info: Chapter information
            chapter_content: Chapter content

        Returns:
            True if published successfully, False otherwise
        """
        try:
            # Implementation would use selenium to:
            # 1. Navigate to webnovel.com
            # 2. Log in with credentials
            # 3. Navigate to story management or create a new story
            # 4. Add a new chapter
            # 5. Submit the content

            # This is a placeholder for the actual implementation
            self.log_info("Webnovel.com publishing not fully implemented")

            # Update published platforms in database
            self._update_published_platforms(content_info['id'], chapter_info['chapter_number'], "webnovel.com")

            return True
        except Exception as e:
            self.log_error(f"Error publishing to Webnovel.com: {str(e)}")
            return False

    def _publish_to_scribblehub(self, browser, credentials, content_info, chapter_info, chapter_content):
        """
        Publish content to ScribbleHub.com.

        Args:
            browser: Browser instance
            credentials: Login credentials
            content_info: Content information
            chapter_info: Chapter information
            chapter_content: Chapter content

        Returns:
            True if published successfully, False otherwise
        """
        try:
            # Implementation would use selenium to:
            # 1. Navigate to scribblehub.com
            # 2. Log in with credentials
            # 3. Navigate to story management or create a new story
            # 4. Add a new chapter
            # 5. Submit the content

            # This is a placeholder for the actual implementation
            self.log_info("ScribbleHub.com publishing not fully implemented")

            # Update published platforms in database
            self._update_published_platforms(content_info['id'], chapter_info['chapter_number'], "scribblehub.com")

            return True
        except Exception as e:
            self.log_error(f"Error publishing to ScribbleHub.com: {str(e)}")
            return False

    def _update_published_platforms(self, content_id, chapter_number, platform):
        """
        Update the list of platforms where a chapter has been published.

        Args:
            content_id: Content ID
            chapter_number: Chapter number
            platform: Platform name
        """
        # Get current platforms
        result = self.db_manager.query(
            """
            SELECT platforms FROM content_chapters
            WHERE content_id = %s AND chapter_number = %s
            """,
            (content_id, chapter_number)
        )

        if result:
            try:
                platforms = json.loads(result[0]['platforms'])
            except json.JSONDecodeError:
                platforms = []

            # Add platform if not already in the list
            if platform not in platforms:
                platforms.append(platform)

            # Update database
            self.db_manager.execute(
                """
                UPDATE content_chapters 
                SET platforms = %s, published = 1 
                WHERE content_id = %s AND chapter_number = %s
                """,
                (json.dumps(platforms), content_id, chapter_number)
            )

    def _update_patreon(self, content_info: Dict[str, Any]) -> bool:
        """
        Update Patreon page with new content information.

        Args:
            content_info: Content information dictionary

        Returns:
            True if updated successfully, False otherwise
        """
        self.log_info(f"Updating Patreon for {content_info['title']}")

        try:
            # Get Patreon credentials
            credentials = self.config.get_website_credentials("PATREON")
            if not credentials:
                self.log_error("No credentials found for Patreon")
                return False

            # Initialize browser
            browser = self.browser_manager.get_browser()

            try:
                # Log in to Patreon
                browser.get("https://www.patreon.com/login")
                self.random_delay(2, 4)

                # Enter username/email
                username_field = browser.find_element(By.ID,  "email")
                username_field.send_keys(credentials["username"])
                self.random_delay(1, 2)

                # Enter password
                password_field = browser.find_element(By.ID,  "password")
                password_field.send_keys(credentials["password"])
                self.random_delay(1, 2)

                # Click login button
                login_button = browser.find_element(By.XPATH, "//button[@type='submit']")
                login_button.click()
                self.random_delay(3, 5)

                # Navigate to creator page
                browser.get("https://www.patreon.com/creator-home")
                self.random_delay(2, 3)

                # Create a new post
                post_title = f"New chapter of {content_info['title']} is now available!"
                post_content = self._generate_patreon_update(content_info)

                # Find and click the "Create" or "New Post" button
                create_button = browser.find_element(By.XPATH, 
                    "//a[contains(@href, '/posts/new') or contains(text(), 'Create') or contains(text(), 'New Post')]")
                create_button.click()
                self.random_delay(2, 3)

                # Fill in post details
                title_field = browser.find_element(By.XPATH, "//input[@placeholder='Title']")
                title_field.send_keys(post_title)
                self.random_delay(1, 2)

                # Fill in post content (might be in an iframe or rich text editor)
                content_field = browser.find_element(By.XPATH, "//div[contains(@class, 'editor') or @role='textbox']")
                content_field.send_keys(post_content)
                self.random_delay(2, 3)

                # Submit post
                publish_button = browser.find_element(By.XPATH, 
                    "//button[contains(text(), 'Publish') or contains(text(), 'Post')]")
                publish_button.click()
                self.random_delay(3, 5)

                # Verify post was published
                browser.get("https://www.patreon.com/posts")
                self.random_delay(2, 3)

                # Check for the post title to verify it was published
                posts = browser.find_elements(By.XPATH, f"//h1[contains(text(), '{post_title}')]")
                if posts:
                    self.log_info("Successfully published Patreon update")
                    return True
                else:
                    self.log_warning("Patreon post might not have been published")
                    return False

            except Exception as e:
                self.log_error(f"Error updating Patreon: {str(e)}")
                return False

        finally:
            # Always close the browser
            self.browser_manager.close_browser(browser)

    def _generate_patreon_update(self, content_info: Dict[str, Any]) -> str:
        """
        Generate content for a Patreon update.

        Args:
            content_info: Content information dictionary

        Returns:
            Generated update content
        """
        # Get latest chapter info
        result = self.db_manager.query(
            """
            SELECT chapter_number, title, platforms
            FROM content_chapters
            WHERE content_id = %s
            ORDER BY chapter_number DESC
            LIMIT 1
            """,
            (content_info['id'],)
        )

        if not result:
            return f"I've been working on new content for {content_info['title']}. Stay tuned for updates!"

        chapter_info = result[0]

        # Create links to platforms
        platform_links = ""
        try:
            platforms = json.loads(chapter_info['platforms'])
            for platform in platforms:
                platform_links += f"- {platform}\n"
        except (json.JSONDecodeError, KeyError):
            platform_links = "Available on multiple platforms!"

        # Create a prompt for the LLM
        prompt = f"""
        Write an engaging Patreon update announcing a new chapter of "{content_info['title']}".

        Details:
        - Chapter {chapter_info['chapter_number']}: "{chapter_info['title']}"
        - This is a {content_info['genre']} {content_info['type']}
        - Available on: {platform_links}

        The update should:
        1. Thank patrons for their support
        2. Highlight what's exciting about this new chapter
        3. Tease what's coming next
        4. Remind patrons about exclusive benefits

        Keep it friendly, personal, and engaging. About 200-300 words.
        """

        # Get response from LLM
        update_content = self.api_manager.generate_text(prompt)

        return update_content

    def _check_patreon_earnings(self) -> Dict[str, Any]:
        """
        Check current earnings on Patreon.

        Returns:
            Dictionary with earnings information
        """
        self.log_info("Checking Patreon earnings")

        try:
            # Get Patreon credentials
            credentials = self.config.get_website_credentials("PATREON")
            if not credentials:
                self.log_error("No credentials found for Patreon")
                return {"success": False, "earnings": 0}

            # Initialize browser
            browser = self.browser_manager.get_browser()

            try:
                # Log in to Patreon
                browser.get("https://www.patreon.com/login")
                self.random_delay(2, 4)

                # Enter username/email
                username_field = browser.find_element(By.ID,  "email")
                username_field.send_keys(credentials["username"])
                self.random_delay(1, 2)

                # Enter password
                password_field = browser.find_element(By.ID,  "password")
                password_field.send_keys(credentials["password"])
                self.random_delay(1, 2)

                # Click login button
                login_button = browser.find_element(By.XPATH, "//button[@type='submit']")
                login_button.click()
                self.random_delay(3, 5)

                # Navigate to income page
                browser.get("https://www.patreon.com/dashboard/earnings")
                self.random_delay(3, 5)

                # Extract earnings information
                # Note: This is a placeholder and needs to be adapted to the actual Patreon dashboard structure
                earnings_element = browser.find_element(By.XPATH, 
                    "//div[contains(@class, 'earnings') or contains(@class, 'amount')]")
                earnings_text = earnings_element.text.strip()

                # Parse earnings amount
                import re
                earnings_match = re.search(r'\$(\d+(\.\d+)?)', earnings_text)
                if earnings_match:
                    earnings = float(earnings_match.group(1))
                else:
                    earnings = 0

                # Extract patron count
                patrons_element = browser.find_element(By.XPATH, 
                    "//div[contains(@class, 'patrons') or contains(text(), 'patrons')]")
                patrons_text = patrons_element.text.strip()

                patrons_match = re.search(r'(\d+)', patrons_text)
                if patrons_match:
                    patrons = int(patrons_match.group(1))
                else:
                    patrons = 0

                # Update content subscribers in database
                content_info = self._get_active_content()
                if content_info:
                    self.db_manager.execute(
                        "UPDATE content_creation SET subscribers = %s WHERE id = %s",
                        (patrons, content_info['id'])
                    )

                self.log_info(f"Patreon earnings: ${earnings} from {patrons} patrons")

                return {
                    "success": True,
                    "earnings": earnings,
                    "patrons": patrons
                }

            except Exception as e:
                self.log_error(f"Error checking Patreon earnings: {str(e)}")
                return {"success": False, "earnings": 0}

        finally:
            # Always close the browser
            self.browser_manager.close_browser(browser)

    def _get_active_content(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the active content.

        Returns:
            Dictionary with content information or None if no active content
        """
        result = self.db_manager.query(
            "SELECT * FROM content_creation WHERE state='active' LIMIT 1"
        )

        if not result:
            return None

        content_info = dict(result[0])

        # Get synopsis from state if available
        if 'state' in content_info and content_info['state']:
            try:
                state_data = json.loads(content_info['state'])
                if 'synopsis' in state_data:
                    content_info['synopsis'] = state_data['synopsis']
            except json.JSONDecodeError:
                pass

        if 'synopsis' not in content_info:
            content_info['synopsis'] = f"A {content_info['genre']} {content_info['type']} series."

        return content_info

    def run(self) -> Dict[str, Any]:
        """
        Execute the content creation strategy.

        Returns:
            Dictionary with the result of the execution
        """
        self.log_info("Running content creation strategy")

        try:
            # Get active content or create new if none exists
            content_info = self._get_active_content()
            if not content_info:
                content_info = self._create_new_content()

            # Determine if it's time to publish a new chapter
            publish_new_chapter = False

            if content_info['chapters'] == 0:
                # No chapters yet, create the first one
                publish_new_chapter = True
            else:
                # Check if it's time for a new chapter based on publish_interval
                last_published = content_info['last_published']
                if isinstance(last_published, str):
                    last_published = datetime.datetime.strptime(last_published, "%Y-%m-%d %H:%M:%S")

                days_since_last = (datetime.datetime.now() - last_published).days
                if days_since_last >= self.publish_interval:
                    publish_new_chapter = True

            # Publish a new chapter if needed
            if publish_new_chapter:
                # Create a new chapter
                chapter_info = self._create_new_chapter(content_info)

                # Generate chapter content
                chapter_content = self._generate_chapter_content(content_info, chapter_info)

                # Publish to the primary platform
                primary_platform = content_info['platform']
                primary_success = self._publish_to_platform(
                    content_info,
                    chapter_info,
                    primary_platform,
                    chapter_content
                )

                # If successful, try publishing to other platforms
                if primary_success:
                    for platform in self.PLATFORMS:
                        if platform != primary_platform:
                            self._publish_to_platform(
                                content_info,
                                chapter_info,
                                platform,
                                chapter_content
                            )

                    # Update Patreon
                    self._update_patreon(content_info)

                    # Update last published date
                    self.db_manager.execute(
                        "UPDATE content_creation SET last_published = %s WHERE id = %s",
                        (datetime.datetime.now(), content_info['id'])
                    )

                    self.log_info(f"Published new chapter for {content_info['title']}")

            # Check Patreon earnings
            earnings_info = self._check_patreon_earnings()

            # Determine the result
            success = publish_new_chapter and primary_success if publish_new_chapter else earnings_info["success"]
            income = earnings_info.get("earnings", 0)

            return {
                'success': success,
                'income': income,
                'currency': 'USD',
                'description': f"Patreon earnings from {content_info['title']}",
                'details': {
                    'content_title': content_info['title'],
                    'chapters': content_info['chapters'],
                    'subscribers': earnings_info.get("patrons", 0),
                    'published_new': publish_new_chapter
                }
            }

        except Exception as e:
            self.log_error(f"Error executing content creation strategy: {str(e)}")
            return {
                'success': False,
                'income': 0,
                'currency': 'USD',
                'description': 'Content creation failed',
                'details': {'error': str(e)}
            }