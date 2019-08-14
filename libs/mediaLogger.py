#!/usr/bin/env python
# coding=utf-8
# Author: Danilo Daloiso

import sys
import errno
import logging
import logging.handlers

from os import makedirs
from os.path import exists, isdir, join, realpath, dirname


def mkdir_p(path):
    try:
        makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and isdir(path):
            pass
        else:
            raise


class MediaLogger(object):
    loggers = set()

    # log levels
    INFO = logging.INFO
    DEBUG = logging.DEBUG
    ERROR = logging.ERROR
    WARNING = logging.WARNING

    LOGGING_LEVELS = {
        'INFO': INFO,
        'DEBUG': DEBUG,
        'ERROR': ERROR,
        'WARNING': WARNING,
    }

    def __init__(self, name, console_logging=True, file_logging=True, format='%(asctime)s - [%(levelname)s]\t(%(name)20s) - %(message)s', level=DEBUG):
        # Initial construct.
        self.name = name
        self.level = level
        self.format = format

        # Logger configuration.
        self.file_logging = file_logging
        self.console_logging = console_logging
        self.logPath = join(dirname(realpath(sys.argv[0])), 'logs')
        self.logFile = join(self.logPath, 'MediaConverter.log')

        self.formatter = logging.Formatter(self.format)

        # Console logging
        if self.console_logging:
            self.console_logger = logging.StreamHandler(sys.stdout)
            self.console_logger.setFormatter(self.formatter)

        # File logging
        if self.file_logging:
            if not exists(self.logPath): mkdir_p(self.logPath)
            self.file_logger = logging.handlers.RotatingFileHandler(
                self.logFile, maxBytes=int(10 * 1048576), backupCount=30, encoding='utf-8'
            )
            self.file_logger.setFormatter(self.formatter)

        # Complete logging config.
        self.logger = logging.getLogger(name)
        if name not in self.loggers:
            self.loggers.add(name)
            self.logger.setLevel(self.level)
            if self.file_logging:    self.logger.addHandler(self.file_logger)
            if self.console_logging: self.logger.addHandler(self.console_logger)

    def getHandlers(self):
        return self.console_logger, self.file_logger

    def getLogger(self):
        return self.logger

    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        self.logger.warn(msg, *args, **kwargs)
