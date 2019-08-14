#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import telepot as telegram

from os import getpid, rename, remove
from os.path import basename, dirname, isfile, join

from unicodedata import normalize

from .mediaLogger import MediaLogger
logger = MediaLogger(__name__, level=MediaLogger.DEBUG)


def convertBytes(num):
    """
    this function will convert bytes to MB
    """
    for x in ['bytes', 'KB']:
        num /= 1024.0

    return float("%3.1f" % num)


def pidFile(PID):
    if isfile(PID):
        logger.error('Process already exists, exiting')
        sys.exit(2)

    try:
        open(PID, 'w').write(str(getpid()))
        logger.info('Writing PID in: %s' % PID)

    except Exception:
        logger.error('Another instance is running...')
        sys.exit(9)


def printHelp(message=None):
    if message:
        logger.error(message)
    sys.exit(1)


def removeAccents(old_path):
    unclean_file = basename(old_path)
    logger.debug('Normalize file name')
    if type(unclean_file) is not unicode:
        path = unicode(unclean_file, encoding='utf-8')
        path = normalize('NFD', path).encode('ascii', 'ignore')
        clean_file = re.sub(u"[!#$%&'*+,:;<=>?@^`{|}~]", ' ', path)
        clean_path = join(dirname(old_path), clean_file)
        if not old_path == clean_path:
            logger.debug('Rename file from %s to %s' % (unclean_file, clean_file))
            rename(old_path, clean_path)
    else:
        clean_path = old_path

    return clean_path


def removePID(PID):
    pidnumber = open(PID, 'r').read()
    if pidnumber == str(getpid()):
        remove(PID)


class TelegramCli(object):
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id

    def send_telegram_notification(self, msg):
        if self.token and self.chat_id:
            logger.debug('Send Telegram Notification: %s' % msg)
            if msg:
                bot = telegram.Bot(token=self.token)
                bot.sendMessage(chat_id=self.chat_id, text=msg)
