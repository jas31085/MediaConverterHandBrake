#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import os
import sys
import magic
import iso9660
import logging
import argparse
import tempfile
import subprocess
import transmissionrpc as trpc

from unicodedata import normalize
from shutil import copyfile
from shutil import move
from distutils.spawn import find_executable

# HANDBRAKE_PATH = os.path.dirname(__file__) + "/HandBrakeCLI"
HANDBRAKE_PATH = find_executable('HandBrakeCLI')
# HANDBRAKE_PATH = "/bin/echo"  # Just for testing..

NICE_PATH = find_executable('nice')

PID = os.path.join(tempfile.gettempdir(), os.path.splitext(os.path.basename(__file__))[0] + '.pid')

RESOLUTIONS = {
    "480":   { 'X': 720,  'Y': 480  },
    "576":   { 'X': 720,  'Y': 576  },
    "720":   { 'X': 1280, 'Y': 720  },
    "1080":  { 'X': 1920, 'Y': 1080 },
    "2K":    { 'X': 2048, 'Y': 1080 },
    "WQXGA": { 'X': 2560, 'Y': 1600 },
    "SHD":   { 'X': 3840, 'Y': 2160 },
    "4K":    { 'X': 4096, 'Y': 2160 }
}
EXCLUDED_EXT = [ '.part' ]
EXTRA_OPTS = [ "audio_naming" ]

log       = None
LOG_FILE  = None
SRC_DIR   = None
TMP_DIR   = None
DST_DIR   = None
MASK_DIR  = None
TXT_PATH  = None
FILE_PATH = None
OUT_EXT   = None
T_HOST    = None
T_PORT    = 9091
T_USER    = None
T_PSW     = None
MAX_SIZE  = 1200.0
MAX_RES   = '720'
LANG      = None
DEL_SRC   = False
DEBUG     = False
EXTRA     = None

PARSER = argparse.ArgumentParser(version     = '%(prog)s 1.0',
                                 add_help    = True, conflict_handler = 'resolve',
                                 description = 'Just another HandBrakeCLI batch executor.')

def log_setup(logLevel):
    logger = logging.getLogger(__name__)
    logger.setLevel(logLevel)

    # create a file handler
    if LOG_FILE:
        handler = logging.FileHandler(LOG_FILE)
    else:
        handler = logging.StreamHandler()
    handler.setLevel(logLevel)

    # create a logging format
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(funcName)s - %(message)s')
    handler.setFormatter(formatter)

    # add the handlers to the logger
    logger.addHandler(handler)

    return logger


def args_extraction(argv):
    global log
    global LOG_FILE
    global SRC_DIR
    global TMP_DIR
    global DST_DIR
    global MASK_DIR
    global TXT_PATH
    global FILE_PATH
    global OUT_EXT
    global T_HOST
    global T_PORT
    global T_USER
    global T_PSW
    global MAX_SIZE
    global MAX_RES
    global LANG
    global DEL_SRC
    global DEBUG
    global EXTRA

    g_group = PARSER.add_argument_group('Input Scan')
    t_group = PARSER.add_argument_group('Transmission')
    v_group = PARSER.add_argument_group('Video')

    PARSER.add_argument(       '--extra',       action = "store",      default = None,   dest = "EXTRA",     type = str,   required = False, metavar='Extra Opt',  nargs='+', help = 'Set extra parameter (use one of: %s)' % ', '.join(EXTRA_OPTS))
    PARSER.add_argument(       '--debug',       action = "store_true", default = False,  dest = "DEBUG",                   required = False,                       help = 'Set log level to Debug')
    PARSER.add_argument(       '--log-file',    action = "store",      default = None,   dest = "LOG_FILE",  type = str,   required = False, metavar='logPath',    help = 'Logs output on file')
    g_group.add_argument('-D', '--delete',      action = "store_true", default = False,  dest = "DEL_SRC",                 required = False,                       help = 'Delete Source file')
    g_group.add_argument('-s', '--source',      action = "store",      default = None,   dest = "SRC_DIR",   type = str,   required = False, metavar='SourcePath', help = 'Source path used for scan')
    g_group.add_argument('-t', '--tmp',         action = "store",      default = None,   dest = "TMP_DIR",   type = str,   required = False, metavar='TempPath',   help = 'Temporary folder')
    g_group.add_argument('-d', '--destination', action = "store",      default = None,   dest = "DST_DIR",   type = str,   required = False, metavar='DestPath',   help = '''
                                                                                                                                                                          Destination folder for converted items.
                                                                                                                                                                          If not specified source and destination are the same
                                                                                                                                                                          ''')
    t_group.add_argument('-m', '--mask',        action = "store",      default = None,   dest = "MASK_DIR",  type = str,   required = False, metavar='MaskPath',   help = '''
                                                                                                                                                                          Used if you are running this script outside of Transmission
                                                                                                                                                                          This is the local raggiungible path for Transmission downloads
                                                                                                                                                                          ''')
    g_group.add_argument('-T', '--txt',         action = "store",      default = None,   dest = "TXT_PATH",  type = str,   required = False, metavar='TextFile',   help = 'List of files in a *.txt list')
    g_group.add_argument('-f', '--file',        action = "store",      default = None,   dest = "FILE_PATH", type = str,   required = False, metavar='SingleFile', help = 'One shot execution for a single file')
    v_group.add_argument('-e', '--extension',   action = "store",      default = None,   dest = "OUT_EXT",   type = str,   required = False, metavar='Extension',  help = 'Extension for output transcoded file')
    t_group.add_argument(      '--host',        action = "store",      default = None,   dest = "T_HOST",    type = str,   required = False, metavar='Host',       help = 'Transmission host address')
    t_group.add_argument(      '--port',        action = "store",      default = 9091,   dest = "T_PORT",    type = int,   required = False, metavar='Port',       help = 'Transmission host port (default=9091)')
    t_group.add_argument(      '--user',        action = "store",      default = None,   dest = "T_USER",    type = str,   required = False, metavar='User',       help = 'Transmission username')
    t_group.add_argument(      '--psw',         action = "store",      default = None,   dest = "T_PSW",     type = str,   required = False, metavar='Password',   help = 'Transmission password')
    v_group.add_argument('-S', '--size',        action = "store",      default = 1200.0, dest = "MAX_SIZE",  type = float, required = False, metavar='Size',       help = 'The minimum file size limit for conversion')
    v_group.add_argument('-r', '--resolution',  action = "store",      default = '720',  dest = "MAX_RES",   type = str,   required = False, metavar='VideoRes',   help = '''
                                                                                                                                                                          Resolution for output transcoded file.
                                                                                                                                                                          The value is one of:
                                                                                                                                                                          480, 576, 720, 1080, 2K, WQXGA, SHD, 4K
                                                                                                                                                                          ''')
    v_group.add_argument('-l', '--language',    action = "store",      default = None,   dest = "LANG",      type = str,   required = False, metavar='Language', nargs='+', help = '''
                                                                                                                                                                          List of language needed in the file for start the conversion
                                                                                                                                                                          ''')

    if not argv:
        printHelp('No arguments provided')

    args = vars(PARSER.parse_args(argv))

    if args['DEBUG']:
       logLevel = logging.DEBUG
    else:
        logLevel = logging.INFO

    if args['LOG_FILE']:
        LOG_FILE = args['LOG_FILE']

    log = log_setup(logLevel)
    
    pid_file()

    for key, value in dict(args).iteritems():
        globals()[key] = value
        log.debug('%s: %s' % (key, value))

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
        if not os.path.exists(SRC_DIR):
            printHelp('Source path don\'t exist!')

    if TMP_DIR:
        if not os.path.exists(TMP_DIR):
            printHelp('Temporary Dir path don\'t exist!')

    if DST_DIR:
        if not os.path.exists(DST_DIR):
            printHelp('TorrentMask path don\'t exist!')

    if MASK_DIR:
        if not os.path.exists(MASK_DIR):
            printHelp('Destination path don\'t exist!')

    if TXT_PATH:
        if not os.path.isfile(TXT_PATH):
            printHelp('Input file don\'t exist!')

    if FILE_PATH:
        if not os.path.isfile(FILE_PATH):
            printHelp('Input file don\'t exist!')

    if EXTRA:
        newList = []
        for extra_opt in EXTRA:
            if extra_opt.lower() in EXTRA_OPTS:
                newList.append(extra_opt.lower())
        EXTRA = newList


def printHelp(message=None):
    PARSER.print_help()
    if message:
        print(message)
    sys.exit(1)


def pid_file():
    if os.path.isfile(PID):
        log.error('Process already exists, exiting')
        sys.exit(2)

    try:
        open(PID, 'w').write(str(os.getpid()))
        log.info('Writing PID in: %s' % PID)
    
    except Exception:
        log.error('Another instance is running...')
        sys.exit(9)


def get_media_info(filePath):
    """ Note this is media info cli """
    mediainfoPath = find_executable('mediainfo')
    cmd = '%s "%s"' % (mediainfoPath, filePath)

    process = subprocess.Popen(cmd,
                               shell=True,
                               stderr=subprocess.PIPE,
                               stdout=subprocess.PIPE)
    (output, error) = process.communicate()

    mainKey = {}
    category = None
    # make a dict of it
    for line in output.splitlines()[:-1]:
        if ':' not in line and line != '':
            oldCategory = category
            subsub = {}

            category = line.strip('\r')
            if "#" in category:
                subCategory = category.split('#')[1]
                category = category.split('#')[0].strip()
                if oldCategory != category:
                    sub = []
            else:
                sub = {}
                subCategory = None
            mainKey[category] = ''
        elif line == '':
            if subCategory:
                sub.append(subsub)
            mainKey[category] = sub
        elif ':' in line:
            if category != "Menu":
                z = line.split(':', 1)
                k = z[0].strip('\r').strip()
                v = z[1].strip('\r').strip()
            else:
                z = line.split(' : ', 1)
                k = z[0].strip('\r').strip()
                v = z[1].strip('\r').strip()
            if subCategory:
                subsub[k] = v
            else:
                sub[k] = v

    return mainKey


def is_video_file(filePath):
    if type(filePath) == list:
        filePath = os.path.join(filePath[0], filePath[1])

    if not os.path.isfile(filePath):
        log.debug("'%s' Skipped. File is not accessible." % filePath)
        return False

    if os.path.splitext(filePath)[1].lower() in EXCLUDED_EXT:
        log.debug("'%s' Skipped. Extension found in the excluded list." % filePath)
        return False

    if os.path.splitext(filePath)[1].lower() in ['.iso']:
        log.info('%s ISO File found.' % filePath)
        return is_iso_video(filePath)

    magicInfo = magic.from_file(filePath, mime=True)

    if 'video' in magicInfo.lower():
        log.info("'%s' OK: %s" % (os.path.basename(filePath), magicInfo))
        # Todo: verifica risoluzione, dimensione, lingue audio,
        return True

    if 'Video' in get_media_info(filePath):
        log.info("'%s' OK: The file is a video." % os.path.basename(filePath))
        # Todo: verifica risoluzione, dimensione, lingue audio,
        return True

    return False


def is_iso_video(filePath):
    try:
        cd = iso9660.ISO9660(filePath)
        cdTree = cd.tree()

        if '/VIDEO_TS' in cdTree or '/AUDIO_TS' in cdTree:
            return True

        log.debug("'%s' Skipped. The ISO file is not a Video file." % filePath)
    except Exception as e:
        log.error('Failed while opening ISO file.', exc_info=True)
        log.error("'%s'")
        pass

    return False


def video_transcoder(inPath, outPath, res, ext):
    # Preset HandBrake
    text = ''
    perc = re.compile('\d{1,3}\.\d{1,3} %')

    PRESET = """
        --pfr
        --h264-level 4.0
        --modulus 2 -m -O
        --loose-anamorphic
        --h264-profile high
        --x264-preset medium
        -e x264 -q 20.0 -r 30
        --audio 1,2,3,4,5,6,7,8,9,10
        --subtitle scan,1,2,3,4,5,6,7,8,9,10
        --audio-fallback ffac3 -X %d -Y %d
        --audio-copy-mask aac,ac3,dtshd,dts,mp3 %s
        -E ffaac,copy:ac3 -B 160,160 -6 dpl2,none -R Auto,Auto -D 0.0,0.0
        """ % (RESOLUTIONS[res]["X"], RESOLUTIONS[res]["Y"], '-f %s' % ext if ext else '')

    cmd = '"%s" -n 19 "%s" -v -i "%s" %s -o "%s" ' % (NICE_PATH, HANDBRAKE_PATH, inPath, PRESET.replace('\n', ''), outPath)

    log.info('Starting video conversion')
    log.debug('%s' % cmd)
    process = subprocess.Popen(cmd,
                               shell=True,
                               stderr=subprocess.PIPE,
                               stdout=subprocess.PIPE)

    # (output, error) = process.communicate()

    logCtl = False
    while True:
        out = process.stdout.read(1)
        if out == '' and process.poll() is not None:
            break
        if out != '':
            if '\r' != out:
                text += out
            else:
                if text.strip() != '':
                    percVal = int(round(float(perc.search(text).group()[:-2])))

                    if percVal % 25 == 0 and not logCtl:
                        logCtl = True
                        log.info(text)
                    elif percVal % 25 != 0 and logCtl:
                        logCtl = False


                    # print(perc.search(text).group(), end=out)

                text = ''

    return process.returncode


def copy_transcode(src_file, utils=None):
    this_inpDir = ''
    this_trnDir = ''
    this_outDir = ''
    this_lang   = None
    torrentID   = None
    resolution = MAX_RES

    if utils:
        if 'Transmission_ID' in utils:
            torrentID = utils['Transmission_ID']
        if 'audio_naming' in EXTRA and 'audio_naming' in utils:
            if type(utils['audio_naming']) == list:
                this_lang = '_'.join(utils['audio_naming'])
            else: this_lang = '_' + utils['audio_naming']

    in_fileName, in_extension = os.path.splitext(os.path.basename(src_file))
    in_extension = in_extension.lstrip('.').lower()

    out_fileName = '%s.%s'
    out_extension = OUT_EXT if OUT_EXT else in_extension

    if TMP_DIR and DST_DIR:            # Case A
        this_inpDir = this_trnDir = TMP_DIR
        this_outDir = DST_DIR

    elif TMP_DIR and not DST_DIR:      # Case B
        this_inpDir = this_trnDir = TMP_DIR
        this_outDir = os.path.dirname(src_file)

    elif not TMP_DIR and DST_DIR:      # Case C
        this_inpDir = os.path.dirname(src_file)
        this_trnDir = this_outDir = DST_DIR

    elif not TMP_DIR and not DST_DIR:  # Case D
        this_inpDir = this_trnDir = this_outDir = os.path.dirname(src_file)

    inputFile  = os.path.join(this_inpDir, '%s.%s' % (in_fileName,  in_extension))
    transFile  = os.path.join(this_trnDir, '%s.%s' % (in_fileName + '_transcoded', out_extension))

    # TODO: Output FileName personalization
    if this_lang:
        outputFile = os.path.join(this_outDir, out_fileName % (in_fileName + '_' + this_lang, out_extension))
    else:
        outputFile = os.path.join(this_outDir, out_fileName % (in_fileName + '_transcoded' if not DST_DIR else in_fileName, out_extension))

    # The magic begins..
    if TMP_DIR:
        log.info('Start copying file to temporary directory.')
        log.debug('cp %s %s' % (src_file, inputFile))
        copyfile(src_file, inputFile)
        log.debug('Finish copy file to temporary directory.')

    retCode = video_transcoder(inputFile, transFile, resolution, out_extension)

    if retCode == 0:
        log.info('Conversion finished without error.')
        if TMP_DIR:
            log.info('Moving file from temporary to appropriate directory.')
            log.debug('mv "%s" "%s"' % (transFile, outputFile))
            move(transFile, outputFile)
            log.debug('rm "%s"' % inputFile)
            os.remove(inputFile)
        elif DST_DIR:
            log.info('Moving file to appropriate directory.')
            log.debug('mv "%s" "%s"' % (transFile, outputFile))
            move(transFile, outputFile)
        elif this_lang:
            log.info('Renaming output file with extra informations.')
            log.debug('mv "%s" "%s"' % (transFile, outputFile))
            move(transFile, outputFile)
            this_inpDir = None

        if DEL_SRC:
            log.info('Removing original file.')
            log.debug('rm "%s"' % src_file)
            os.remove(src_file)
            if torrentID: remove_torrent(torrentID)
            if this_inpDir == this_outDir and not TMP_DIR: move(transFile, outputFile)
    else:
        log.error('Something goes wrong during conversion..')


def get_video_lang(video_lang):
    ret_lang = []

    if type(video_lang) == list:
        for audio in video_lang:
            if 'Language' in audio:
                ret_lang.append(audio['Language'].lower())
    else:
        if 'Language' in video_lang:
            ret_lang = video_lang['Language'].lower()

    return ret_lang


def lang_exists(fileLang):
    if fileLang == '' or fileLang == [] or not LANG: return True

    if type(fileLang) == list:
        for f_lang in fileLang:
            if f_lang in LANG:
                return True

    elif type(fileLang) == str:
        if fileLang in LANG:
            return True

    return False


def get_completed_downloads():
    retList = []
    maskFileList = []
    trasmissionFiles = []

    log.info('Connecting to Transmission server.')
    torrents = trpc.Client(T_HOST, T_PORT, T_USER, T_PSW).get_torrents()
    log.debug('%d Torrents found.' % len(torrents))

    for torrent in torrents:
        if torrent.status == 'stopped' and torrent.progress == 100:
            for key, value in dict(torrent.files()).iteritems():
                if convert_bytes(value['size']) >= MAX_SIZE:
                    log.debug('Evaluating completed Download: %s' % value['name'])
                    if MASK_DIR:
                        trasmissionFiles.append( [ torrent._fields['downloadDir'].value, value['name'], torrent._fields['id'].value] )
                    elif is_video_file( [torrent._fields['downloadDir'].value, value['name']] ):
                        retList.append( [ torrent._fields['downloadDir'].value, value['name'], torrent._fields['id'].value ] )

    # TODO: Riduci il ciclo
    if MASK_DIR:
        for path, subdirs, files in os.walk(MASK_DIR):
            for name in files:
                if is_video_file([path, name]):
                    maskFileList.append([path, name])

        for transmissionFile in trasmissionFiles:
            for maskFile in maskFileList:
                if transmissionFile[1] in maskFile:
                    retList.append( [ maskFile[0], maskFile[1], transmissionFile[2] ] )
                    break

    return retList


def remove_torrent(torrentID):
    log.info('Removing download from Transmission.')
    trpc.Client(T_HOST, T_PORT, T_USER, T_PSW).remove_torrent(torrentID, True)


def scan_file():
    log.info("Evaluating file: %s" % FILE_PATH)
    line_cleaned = remove_accents(FILE_PATH)
    if is_video_file(line_cleaned):
        return [ [ os.path.dirname(line_cleaned), os.path.basename(line_cleaned) ] ]

    return []


def scan_txt():
    retList = []

    log.info("Evaluating file list: %s" % TXT_PATH)
    with open(TXT_PATH) as f:
        lines = f.readlines()
        log.debug('The file has %d lines' % len(lines))
        for line in lines:
            line_cleaned = line.strip('\r').strip()
            if line_cleaned != '':
                if is_video_file(line_cleaned):
                    line_cleaned = remove_accents(line_cleaned)
                    retList.append( [ os.path.dirname(line_cleaned), os.path.basename(line_cleaned) ] )

    log.info('Found %d files in the text file' % len(retList))
    return retList


def scan_torrents(fileList):
    completeDownloads = get_completed_downloads()

    if SRC_DIR:
        for download in completeDownloads:
            if download[0] != SRC_DIR:
                fileList.append(download)
    else:
        fileList += completeDownloads

    log.info('Found %d completed files on Transmission' % len(fileList))

    return fileList


def scan_path(fileList):
    for path, subdirs, files in os.walk(SRC_DIR, topdown=True):
        for file in files:
            try:
                if is_video_file([path, file]):
                    file_path = os.path.join(path, file)
                    line_cleaned = remove_accents(file_path)
                    file_info = os.stat(line_cleaned)
                    file_size = convert_bytes(file_info.st_size)
                    file = os.path.basename(line_cleaned)
                    if file_size >= MAX_SIZE:
                        fileList.append([path, file])
            except Exception as e:
                log.error("Cannot open file '%s'" % file, exc_info=True)
                log.error("'%s'")
                pass

    return fileList


def convert_bytes(num):
    """
    this function will convert bytes to MB
    """
    for x in ['bytes', 'KB']:
        num /= 1024.0

    return float("%3.1f" % num)


def remove_accents(old_path):
    unclean_file = os.path.basename(old_path)
    log.debug('Normalize file name')
    if type(unclean_file) is not unicode:
        path = unicode(unclean_file, encoding='utf-8')
        path = normalize('NFD', path).encode('ascii', 'ignore')
        clean_file = re.sub(u"[!#$%&'*+,:;<=>?@^`{|}~]", ' ', path)
        clean_path = os.path.join(os.path.dirname(old_path) , clean_file)
        if not old_path == clean_path:
            log.debug('Rename file from %s to %s' % (unclean_file,clean_file))
            os.rename(old_path, clean_path)
    
    return clean_path


def main(argv):
    
    global LANG

    try:
        cont = 0
        fileList = []
    
        args_extraction(argv)
        
        log.info("- - - - - - - - -   START MEDIA CONVERSION   - - - - - - - - -")
    
        if not HANDBRAKE_PATH:
            log.error('HandBrakeCLI path not found, exiting')
            sys.exit(9)
    
        if LANG:
            LANG = [x.lower().strip() for x in LANG]
    
        if FILE_PATH:
            fileList = scan_file()
    
        if TXT_PATH:
            fileList = scan_txt()
    
        if T_HOST:
            fileList = scan_torrents(fileList)
            cont = len(fileList)
    
        if SRC_DIR:
            fileList = scan_path(fileList)
            log.info('Found %d video files during scan' % (len(fileList) - cont))
    
        log.info('%d total files in list for evaluating' % len(fileList))
    
        for item in fileList:
            log.info('Validating %s' % item[1])
            this_FullPath = os.path.join(item[0], item[1])
            # this_FileName, this_ext = os.path.splitext(item[1])
            # this_ext = this_ext.lstrip('.').lower()
            utils = {}
            this_lang = []

            log.debug('The File came from Transmission? %s' % item[1])
            if len(item) == 3:
                log.debug('The File came from Transmission')
                utils['Transmission_ID'] = item[2]
            else:
                log.debug('NO')
                
            log.debug("Get Mediainfo from %s" % item[1])
            mediaInfo = get_media_info(this_FullPath)
            
            log.debug("Media is ISO File? %s" % item[1])
            if 'ISO' in mediaInfo['General']['Format']:
                log.debug("Start Processing ISO file")
                copy_transcode(this_FullPath)
                continue
            
            log.debug("Media have Video in File? %s" % item[1])
            if 'Video' not in mediaInfo:
                log.debug("Missing 'Video' tag in mediainfo for '%s'" % item[1])
                continue
    
            H = this_res = int(mediaInfo['Video']['Height'].replace(' ', '').replace('pixels', ''))
            W = int(mediaInfo['Video']['Width'].replace(' ', '').replace('pixels', ''))
    
            log.debug('Video original resolution: %dx%d' % (W, H))
            log.debug('Video target resolution: %dx%d' % (RESOLUTIONS[MAX_RES]['X'], RESOLUTIONS[MAX_RES]['Y']))
    
            log.debug("Media have the correct Resolution? %s" % item[1])
            if this_res > RESOLUTIONS[MAX_RES]['Y']:
            # if this_res > 0:
                if 'Audio' in mediaInfo:
                    this_lang = get_video_lang(mediaInfo['Audio'])
                    utils['audio_naming'] = this_lang
    
                if lang_exists(this_lang):
                    copy_transcode(this_FullPath, utils)
    
        log.info("- - - - - - - - -   END MEDIA CONVERSION   - - - - - - - - -")
    
    except Exception as e:
        log.error (e.message, exc_info=True)
        log.error("%s")
        
    finally:
        pidnumber = open(PID, 'r').read()
        if pidnumber == str(os.getpid()):
            os.remove(PID)
    


########################################
########################################
###############  MAIN  #################
########################################
########################################


if __name__ == "__main__":
    main(sys.argv[1:])
