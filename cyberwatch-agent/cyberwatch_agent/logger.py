#!/usr/bin/env python3
# coding: utf-8

import logging
from logging.handlers import TimedRotatingFileHandler
import time
import sys

FILE_FORMATTER = '%(asctime)s [%(levelname).1s] %(message)s'
FILE_DATE_FORMATTER = '%Y-%m-%d--%H-%M-%S-UTC'

STREAM_FORMATTER = '%(levelname).1s> %(message)s'


class Logger(object):
    def __init__(self, env, debug=False, quiet=False):
        self.env = env

        # Set verbosity level
        verbosity_level = logging.INFO
        if debug:
            verbosity_level = logging.DEBUG
        if quiet and not debug:
            verbosity_level = logging.ERROR

        # Create root logger
        self.root_logger = logging.getLogger()
        self.root_logger.setLevel(logging.NOTSET)

        # Create file handler
        try:
            # Rotation on Sundays
            file_handler = TimedRotatingFileHandler(self.env.logs_file, when="W6", backupCount=1)
            file_handler.setLevel(logging.INFO)

            file_handler_formatter = logging.Formatter(FILE_FORMATTER, FILE_DATE_FORMATTER)
            file_handler_formatter.converter = time.gmtime

            file_handler.setFormatter(file_handler_formatter)
            self.root_logger.addHandler(file_handler)

        except IOError as e:
            self.root_logger = FallBackLogger()
            print('Logger: {0}'.format(e))
            return

        # Create stream handler
        try:
            self.stream_handler = logging.StreamHandler(stream=sys.stdout)
        except TypeError:
            self.stream_handler = logging.StreamHandler(strm=sys.stdout)

        self.stream_handler.setLevel(verbosity_level)
        self.stream_handler.setFormatter(logging.Formatter(STREAM_FORMATTER))

        self.root_logger.addHandler(self.stream_handler)

        # Disable network module loggers
        logging.getLogger('urllib3').propagate = False
        logging.getLogger('cyberwatch_agent.urllib3').propagate = False
        logging.getLogger('requests').propagate = False
        logging.getLogger('cyberwatch_agent.requests').propagate = False


class FallBackLogger(object):
    @staticmethod
    def debug(msg):
        print('D: {0}'.format(msg))

    @staticmethod
    def info(msg):
        print('I: {0}'.format(msg))

    @staticmethod
    def warning(msg):
        print('W: {0}'.format(msg))

    @staticmethod
    def error(msg):
        print('E: {0}'.format(msg))

    @staticmethod
    def critical(msg):
        print('C: {0}'.format(msg))

    def setLevel(self, arg):
        pass

    def addHandler(self, arg):
        pass
