import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = "logs"
INFO_LOG_FILE = "info.log"
ERROR_LOG_FILE = "err.log"

class Logger:
    def __init__(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        self.logger = logging.getLogger("app")
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')


            # handle info log
            info_handler = RotatingFileHandler(
                os.path.join(LOG_DIR, INFO_LOG_FILE),
                maxBytes=5 * 1024 * 1024,
                backupCount=5
            )
            info_handler.setLevel(logging.INFO)
            info_handler.setFormatter(formatter)

            # handle error log
            error_handler = RotatingFileHandler(os.path.join(LOG_DIR, ERROR_LOG_FILE), maxBytes=5 * 1024 * 1024, backupCount=5)
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)

            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.DEBUG)
            stream_handler.setFormatter(formatter)

            self.logger.addHandler(info_handler)
            self.logger.addHandler(error_handler)
            self.logger.addHandler(stream_handler)

    def debug(self, msg):
        self.logger.debug(msg)
    def info(self, msg):
        self.logger.info(msg)
    def warning(self, msg):
        self.logger.warning(msg)
    def error(self, msg):
        self.logger.error(msg)
    def exception(self, msg, exc_info=True):
        self.logger.exception(msg, exc_info=exc_info)
