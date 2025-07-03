import logging
import sys


def _init_logger(name: str):
    """Make our custom logger available

    Args:
        name (str): Name of the logger

    Returns:
        Logger: A logger object
    """
    logger = logging.getLogger(name)
    # Set logger level to INFO to capture logs at all levels from INFO to lower
    # Remember DEBUG -> INFO -> WARNING -> ERROR -> CRITICAL
    logger.setLevel(logging.INFO)
    # Explicitly set the output of the logger to stdout,
    # this is the default stream for normal program output.
    # By default, it is redirected to terminal
    handler = logging.StreamHandler(sys.stdout)
    # Format the log message
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(module)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    # Add the handler to the logger
    logger.addHandler(handler)
    return logger


# Initialize the logger
logger = _init_logger(name="tsc-logger")
