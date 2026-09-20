from __future__ import annotations

import logging
from collections.abc import Callable

from PyQt5.QtCore import QObject, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QTextEdit


DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DEFAULT_DATE_FORMAT = "%H:%M:%S"


class QtLogEmitter(QObject):
    message_ready = pyqtSignal(str)

    def __init__(self, text_edit: QTextEdit):
        super().__init__()
        self.text_edit = text_edit
        self.message_ready.connect(self.append_message, Qt.QueuedConnection)

    @pyqtSlot(str)
    def append_message(self, message: str):
        self.text_edit.moveCursor(QTextCursor.End)
        self.text_edit.append(message)
        self.text_edit.moveCursor(QTextCursor.End)


class QTextEditLogHandler(logging.Handler):
    """Thread-safe logging handler that forwards records to a QTextEdit."""

    def __init__(self, text_edit: QTextEdit):
        super().__init__()
        self.text_edit = text_edit
        self.emitter = QtLogEmitter(text_edit)

    def emit(self, record: logging.LogRecord):
        try:
            self.emitter.message_ready.emit(self.format(record))
        except Exception:
            self.handleError(record)


def setup_text_edit_logging(
    text_edit: QTextEdit,
    *,
    logger_name: str | None = None,
    level: int = logging.INFO,
    formatter: logging.Formatter | None = None,
) -> tuple[logging.Logger, QTextEditLogHandler]:
    """Attach a QTextEdit logging handler and return the logger and handler."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    handler = QTextEditLogHandler(text_edit)
    handler.setLevel(level)
    handler.setFormatter(
        formatter or logging.Formatter(DEFAULT_LOG_FORMAT, DEFAULT_DATE_FORMAT)
    )
    logger.addHandler(handler)
    return logger, handler


def remove_logging_handler(logger: logging.Logger, handler: logging.Handler):
    logger.removeHandler(handler)
    handler.close()


def install_exception_logger(logger: logging.Logger | None = None) -> Callable:
    """Route uncaught Python exceptions through logging."""
    import sys

    if logger is None:
        logger = logging.getLogger("unhandled_exceptions")

    previous_hook = sys.excepthook

    def log_exception(exc_type, exc_value, traceback):
        logger.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, traceback),
        )
        previous_hook(exc_type, exc_value, traceback)

    sys.excepthook = log_exception
    return previous_hook
