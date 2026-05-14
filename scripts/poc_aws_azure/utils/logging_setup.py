import logging
import os


def setup_logging(results_dir: str) -> logging.Logger:
    """Configure logging for the POC runner.

    - Console: INFO level, concise format.
    - File: DEBUG level, verbose format with timestamps.
    """
    logger = logging.getLogger("poc")
    logger.setLevel(logging.DEBUG)

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%H:%M:%S"
    ))
    logger.addHandler(console)

    # File handler
    log_path = os.path.join(results_dir, "poc_run.log")
    os.makedirs(results_dir, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(file_handler)

    return logger
