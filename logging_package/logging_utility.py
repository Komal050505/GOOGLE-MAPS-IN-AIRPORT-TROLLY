# Standard Library Imports
from datetime import datetime
import logging


# Configure logging
logging.basicConfig(filename='app.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def get_formatted_time():
    """
    Returns the current time in 12-hour format with AM/PM.
    """
    return datetime.now().strftime("%I:%M %p")


def log_info(message):
    formatted_time = get_formatted_time()
    logging.info(f"{formatted_time} - {message}")


def log_error(message):
    formatted_time = get_formatted_time()
    logging.error(f"{formatted_time} - {message}")


def log_warning(message):
    formatted_time = get_formatted_time()
    logging.warning(f"{formatted_time} - {message}")


def log_debug(message):
    formatted_time = get_formatted_time()
    logging.debug(f"{formatted_time} - {message}")
