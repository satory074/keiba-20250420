"""
Logging configuration for the Netkeiba scraper.
"""
import logging

# Configure basic logging settings
logging.basicConfig(
    level=logging.INFO,  # Set default logging level (INFO, DEBUG, WARNING, ERROR, CRITICAL)
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Get a logger instance for use in other modules
logger = logging.getLogger(__name__)

def get_logger(name):
    """Returns a logger instance with the specified name."""
    return logging.getLogger(name)
