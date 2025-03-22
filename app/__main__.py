# app/__main__.py
"""
Main entry point for the Autonomous Income Generator.

This module initializes and starts the application.
"""
import os
import sys
import logging
import argparse
from app.core.app_controller import AppController


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Autonomous Income Generator")

    parser.add_argument(
        "--config",
        type=str,
        default=".env",
        help="Path to the configuration file (default: .env)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    return parser.parse_args()


def main():
    """
    Main entry point for the application.
    """
    # Parse command-line arguments
    args = parse_arguments()

    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting Autonomous Income Generator")

    try:
        # Initialize the application controller
        app = AppController(config_path=args.config)

        # Start the application
        app.start()

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")

    except Exception as e:
        logger.error(f"Error starting application: {str(e)}", exc_info=True)
        sys.exit(1)

    logger.info("Application exited")


if __name__ == "__main__":
    main()