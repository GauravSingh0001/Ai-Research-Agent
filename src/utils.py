
import logging
import sys
import re

def setup_logger(name: str):
    """Set up a standard logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)
    return logger


def safe_filename(text: str) -> str:
    """
    Convert text to a safe filename by replacing special characters.
    Compatible with the reference project's main.py helper function.
    
    Args:
        text: the text to make safe
        
    Returns:
        A filesystem-safe string
    """
    return re.sub(r'[\\/*?:"<>| ]+', "_", text)
