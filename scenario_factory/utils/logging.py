import logging


def configure_root_logger(level: int = logging.INFO) -> logging.Logger:
    """
    Configure the root logger to print messages to he console.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    root_logger.addHandler(handler)

    return root_logger
