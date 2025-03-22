# setup.py
"""
Setup script for the Autonomous Income Generator.
"""
from setuptools import setup, find_packages

setup(
    name="autonomous-income-generator",
    version="0.1.0",
    description="A self-sustaining, income-generating Python application",
    author="Your Name",
    author_email="your.email@example.com",
    packages=find_packages(),
    install_requires=[
        # Core dependencies
        "python-dotenv>=0.19.0",
        "schedule>=1.1.0",
        "Flask>=2.0.1",

        # Database
        "mysql-connector-python>=8.0.26",

        # Web automation
        "selenium>=4.1.0",
        "undetected-chromedriver>=3.1.5",
        "selenium-stealth>=1.0.6",
        "webdriver-manager>=3.5.2",
        "zenrows>=1.3.1",

        # API clients
        "requests>=2.26.0",
        "httpx>=0.23.0",

        # Utilities
        "tqdm>=4.62.3",
        "pydantic>=1.9.0",
    ],
    entry_points={
        "console_scripts": [
            "income-generator=app.__main__:main",
        ],
    },
    python_requires=">=3.8",
)