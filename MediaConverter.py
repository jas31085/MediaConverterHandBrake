#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import argparse
import tempfile
import configparser

from os import walk
from os.path import basename, exists, isfile, join, splitext

from libs.TorrentsCli import TorrentsCli
from libs.Video import Video
from libs.commons import TelegramCli, pidFile, removePID, printHelp

from libs.mediaLogger import MediaLogger
logger = MediaLogger(__name__, level=MediaLogger.DEBUG)

PID = join(tempfile.gettempdir(), splitext(basename(__file__))[0] + '.pid')

EXTRA_OPTS = [ 'audio_naming' ]

SRC_DIR         = None
TMP_DIR         = None
DST_DIR         = None
MASK_DIR        = None
TXT_PATH        = None
FILE_PATH       = None
OUT_EXT         = None
T_HOST          = None
T_PORT          = 9091
T_USER          = None
T_PSW           = None
MAX_SIZE        = 1200.0
MAX_RES         = '720'
LANG            = None
DEL_SRC         = False
EXTRA           = None
CONFIG_FILE     = None
TOKEN           = None
CHAT_ID         = None
FORCE_EXT       = None

PARSER = argparse.ArgumentParser(version     = '%(prog)s 1.0',
                                 add_help    = True, conflict_handler = 'resolve',
                                 description = 'Just another HandBrakeCLI batch executor.')


def config_file_read():
    global CONFIG_FILE
    global DEL_SRC
    global DST_DIR
    global EXTRA
    global FILE_PATH
    global FORCE_EXT
    global LANG
    global MASK_DIR
    global MAX_RES
    global MAX_SIZE
    global OUT_EXT
    global SRC_DIR
    global TMP_DIR
    global TXT_PATH
    global T_HOST
    global T_PORT
    global T_PSW
    global T_USER
    
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    
    paths = dict(config['path'])
    extras = dict(config['extra'])
    defaults = dict(config['default'])
    torrents = dict(config['torrent'])
    telegrams = dict(config['telegram'])

    for key, value in defaults.items():
        globals()[key.upper()] = value
    
    for key, value in paths.items():
        globals()[key.upper()] = value
        
    for key, value in torrents.items():
        globals()[key.upper()] = value
        
    for key, value in telegrams.items():
        globals()[key.upper()] = value
        
    for key, value in extras.items():
        globals()[key.upper()] = value


def args_extraction(argv):
    global CONFIG_FILE
    global DEL_SRC
    global DST_DIR
    global EXTRA
    global FILE_PATH
    global FORCE_EXT
    global LANG
    global MASK_DIR
    global MAX_RES
    global MAX_SIZE
    global OUT_EXT
    global SRC_DIR
    global TMP_DIR
    global TXT_PATH
    global T_HOST
    global T_PORT
    global T_PSW
    global T_USER

    e_group = PARSER.add_argument_group('Extra argument')
    g_group = PARSER.add_argument_group('Input Scan')
    t_group = PARSER.add_argument_group('Transmission')
    v_group = PARSER.add_argument_group('Video')

    # p = configargparse.ArgParser(default_config_files=['/etc/app/conf.d/*.conf', '~/.my_settings'])

    e_group.add_argument(       '--extra',       action='store',      default=None,   dest='EXTRA',     type=str,   required=False, metavar='Extra Opt',  nargs='+', help='Set extra parameter (use one of: %s)' % ', '.join(EXTRA_OPTS))
    e_group.add_argument(       '--debug',       action='store_true', default=False,  dest='DEBUG',                 required=False,                       help='Set log level to Debug')
    e_group.add_argument(       '--config',      action='store',      default=None,   dest='CONFIG_FILE',           required=False,                       help='Set Configuration File')
    e_group.add_argument('-F',  '--force',       action='store',      default=False,  dest='FORCE_EXT',             required=False,                       help='Force MKV extension')
    g_group.add_argument('-D',  '--delete',      action='store_true', default=False,  dest='DEL_SRC',               required=False,                       help='Delete Source file')
    g_group.add_argument('-s',  '--source',      action='store',      default=None,   dest='SRC_DIR',   type=str,   required=False, metavar='SourcePath', help='Source path used for scan')
    g_group.add_argument('-t',  '--tmp',         action='store',      default=None,   dest='TMP_DIR',   type=str,   required=False, metavar='TempPath',   help='Temporary folder')
    g_group.add_argument('-d',  '--destination', action='store',      default=None,   dest='DST_DIR',   type=str,   required=False, metavar='DestPath',   help='''
                                                                                                                                                               Destination folder for converted items.
                                                                                                                                                               If not specified source and destination are the same
                                                                                                                                                               ''')
    t_group.add_argument('-m', '--mask',         action='store',      default=None,   dest='MASK_DIR',  type=str,   required=False, metavar='MaskPath',   help='''
                                                                                                                                                               Used if you are running this script outside of Transmission
                                                                                                                                                               This is the local raggiungible path for Transmission downloads
                                                                                                                                                               ''')
    g_group.add_argument('-T', '--txt',          action='store',      default=None,   dest='TXT_PATH',  type=str,   required=False, metavar='TextFile',   help='List of files in a *.txt list')
    g_group.add_argument('-f', '--file',         action='store',      default=None,   dest='FILE_PATH', type=str,   required=False, metavar='SingleFile', help='One shot execution for a single file')
    v_group.add_argument('-e', '--extension',    action='store',      default=None,   dest='OUT_EXT',   type=str,   required=False, metavar='Extension',  help='Extension for output transcoded file')
    t_group.add_argument(      '--host',         action='store',      default=None,   dest='T_HOST',    type=str,   required=False, metavar='Host',       help='Transmission host address')
    t_group.add_argument(      '--port',         action='store',      default=9091,   dest='T_PORT',    type=int,   required=False, metavar='Port',       help='Transmission host port (default=9091)')
    t_group.add_argument(      '--user',         action='store',      default=None,   dest='T_USER',    type=str,   required=False, metavar='User',       help='Transmission username')
    t_group.add_argument(      '--psw',          action='store',      default=None,   dest='T_PSW',     type=str,   required=False, metavar='Password',   help='Transmission password')
    v_group.add_argument('-S', '--size',         action='store',      default=1200.0, dest='MAX_SIZE',  type=float, required=False, metavar='Size',       help='The minimum file size limit for conversion')
    v_group.add_argument('-r', '--resolution',   action='store',      default='720',  dest='MAX_RES',   type=str,   required=False, metavar='VideoRes',   help='''
                                                                                                                                                               Resolution for output transcoded file.
                                                                                                                                                               The value is one of:
                                                                                                                                                               480, 576, 720, 1080, 2K, WQXGA, SHD, 4K
                                                                                                                                                               ''')
    v_group.add_argument('-l', '--language',     action='store',      default=None,   dest='LANG',      type=str,   required=False, metavar='Language', nargs='+', help='''
                                                                                                                                                                        List of language needed in the file for start the conversion
                                                                                                                                                                        ''')
    if not argv:
        printHelp('No arguments provided')

    args = vars(PARSER.parse_args(argv))

    if args['CONFIG_FILE']:
        CONFIG_FILE = dict(args).get('CONFIG_FILE')
        if isfile(CONFIG_FILE):
            config_file_read()
        else:
            printHelp('Configuration File not valid')
    else:
        for key, value in dict(args).items():
            globals()[key] = value
    
    for key, value in globals().items():
        if key.isupper():
            logger.debug('%s: %s' % (key, value))

    # pidFile(PID)

    check_parameters()


def check_parameters():
    global EXTRA

    if not T_HOST and MASK_DIR:
        printHelp('Cannot set Mask directory if Torrent Host is not defined')

    if TXT_PATH and (T_HOST or SRC_DIR):
        printHelp('Cannot read list if Torrent Host and/or source dir are defined')

    if FILE_PATH and (T_HOST or SRC_DIR):
        printHelp('Cannot convert single file if Torrent Host and/or source dir are defined')

    if FILE_PATH and TXT_PATH:
        printHelp('Cannot read list if single file is defined')

    if SRC_DIR:
        if not exists(SRC_DIR):
            printHelp('Source path don\'t exist!')

    if TMP_DIR:
        if not exists(TMP_DIR):
            printHelp('Temporary Dir path don\'t exist!')

    if DST_DIR:
        if not exists(DST_DIR):
            printHelp('TorrentMask path don\'t exist!')

    if MASK_DIR:
        if not exists(MASK_DIR):
            printHelp('Destination path don\'t exist!')

    if TXT_PATH:
        if not isfile(TXT_PATH):
            printHelp('Input file don\'t exist!')

    if FILE_PATH:
        if not isfile(FILE_PATH):
            printHelp('Input file don\'t exist!')

    if EXTRA:
        newList = []
        for extra_opt in EXTRA:
            if extra_opt.lower() in EXTRA_OPTS:
                newList.append(extra_opt.lower())
        EXTRA = newList


def scan_file(filePath):
    logger.info('Evaluating file: %s' % filePath)
    videoFile = Video(filePath)
    if videoFile.isVideo:
        return [ videoFile ]

    return []


def scan_txt(txtPath):
    retList = []

    logger.info('Evaluating file list: %s' % txtPath)
    with open(txtPath) as f:
        lines = f.readlines()
        logger.debug('The file has %d lines' % len(lines))
        for line in lines:
            line_cleaned = line.strip('\r').strip()
            if line_cleaned != '':
                videoFile = Video(line_cleaned)
                if videoFile.isVideo: retList.append( videoFile )

    logger.info('Found %d files in the text file' % len(retList))
    return retList


def scan_path(videoList, srcDir):
    for path, subdirs, files in walk(srcDir, topdown=True):
        for f in files:
            try:
                videoFile = Video( join(path, f) )
                if videoFile.isVideo:
                    if videoFile.fileSize >= MAX_SIZE:
                        videoList.append( videoFile )
            except Exception:
                logger.error('Cannot open file \'%s\'' % f, exc_info=True)
                pass

    return videoList


def main(argv):
    
    global LANG

    try:
        cont = 0
        videoList = []

        telegram = TelegramCli(TOKEN, CHAT_ID)

        args_extraction(argv)

        if LANG:
            LANG = LANG.lower().split()
            # LANG = [x.lower().strip() for x in LANG]

        if FILE_PATH:
            videoList = scan_file(FILE_PATH)

        if TXT_PATH:
            videoList = scan_txt(TXT_PATH)

        if T_HOST:
            transmissionClient = TorrentsCli(T_USER, T_PSW, T_HOST, T_PORT, maskDir=MASK_DIR, maxSize=MAX_SIZE)
            videoList = transmissionClient.scan_torrents(videoList, SRC_DIR)
            cont = len(videoList)

        if SRC_DIR:
            videoList = scan_path(videoList, SRC_DIR)
            logger.info('Found %d video files during scan' % (len(videoList) - cont))

        logger.info('%d total files in list for evaluating' % len(videoList))

        for videoFile in videoList:
            logger.info('Validating %s' % videoFile.fileName)
            utils = {}
            this_lang = []

            if 'ISO' in videoFile.media_info['General']['Format']:
                logger.debug('Start Processing ISO file')
                telegram.send_telegram_notification('Transcoding started for file \'%s\'' % videoFile.fileName)
                videoFile.setNewResolution(MAX_RES)
                videoFile.copy_transcode(utils=utils, tmpDir=TMP_DIR, dstDir=DST_DIR, delSrc=DEL_SRC,
                                         newExtension=OUT_EXT)
                telegram.send_telegram_notification('Transcoding finished for file \'%s\'' % videoFile.fileName)
                continue

            if 'Video' not in videoFile.media_info:
                logger.debug('Missing \'Video\' tag in mediainfo for \'%s\'' % videoFile.fileName)
                continue

            logger.debug('Video original resolution: %dx%d' % (videoFile.width, videoFile.height))
            logger.debug('Video target resolution: %dx%d' % (Video.RESOLUTIONS[MAX_RES]['X'], Video.RESOLUTIONS[MAX_RES]['Y']))

            if videoFile.height > Video.RESOLUTIONS[MAX_RES]['Y']:
                if 'Audio' in videoFile.media_info:
                    this_lang = videoFile.get_video_lang(videoFile.media_info['Audio'])
                    utils['audio_naming'] = this_lang

                if videoFile.lang_exists(this_lang):
                    telegram.send_telegram_notification('Transcoding started for file \'%s\'' % videoFile.fileName)
                    videoFile.setNewResolution(MAX_RES)
                    videoFile.copy_transcode(utils=utils, tmpDir=TMP_DIR, dstDir=DST_DIR, delSrc=DEL_SRC,
                                             newExtension=OUT_EXT)
                    telegram.send_telegram_notification('Transcoding finished for file \'%s\'' % videoFile.fileName)
            else: logger.info('Resolution is less than required. Skipping.')

    except Exception as e:
        logger.error(e.message, exc_info=True)
    finally:
        removePID(PID)

########################################
########################################
###############  MAIN  #################
########################################
########################################


if __name__ == '__main__':
    main(sys.argv[1:])
