"""Centralized logging helpers."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from files.config import AppPaths, build_paths, ensure_app_directories
from files.utils.file_utils import ensure_directory


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_file_logger(log_file: Path, logger_name: str = "autodub") -> logging.Logger:
    ensure_directory(log_file.parent)
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    file_handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(file_handler)
    return logger


def configure_startup_logging(paths: AppPaths | None = None) -> logging.Logger:
    resolved = ensure_app_directories(paths or build_paths())
    logger = setup_file_logger(resolved.startup_log, "autodub.startup")
    logger.info("Startup logger initialized.")
    return logger


def configure_main_logging(paths: AppPaths | None = None) -> logging.Logger:
    resolved = ensure_app_directories(paths or build_paths())
    logger = setup_file_logger(resolved.app_log, "autodub.app")
    stream_handler = logging.StreamHandler(stream=sys.stderr)
    stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(stream_handler)
    logger.info("Main application logger initialized.")
    return logger


def create_job_logger(log_file: Path, job_id: str) -> logging.Logger:
    return setup_file_logger(log_file, f"autodub.job.{job_id}")


def shutdown_logging_handlers() -> None:
    logger_names = {""}
    logger_names.update(str(name) for name in logging.root.manager.loggerDict)
    for logger_name in logger_names:
        logger = logging.getLogger(logger_name)
        for handler in list(logger.handlers):
            try:
                handler.flush()
                handler.close()
            finally:
                logger.removeHandler(handler)
    logging.shutdown()
