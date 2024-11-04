import logging


def get_logger(logger_name: str, log_level: str = 'DEBUG') -> logging.Logger:
    """Default logger to set up in code logging

    Args:
        logger_name (str): Name for logger
        log_level (str, optional): Log level for printing to terminal. Defaults to 'DEBUG'.

    Returns:
        logging.Logger: Returns logging object to initialize logger with
    """
    logger = logging.getLogger(logger_name)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        # '%(asctime)s [%(levelname)s] [%(name)s] %(message)s')
        '%(asctime)s [%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(log_level)
    return logger
