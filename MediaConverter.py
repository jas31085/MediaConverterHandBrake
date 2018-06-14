#!/bin/env python

import os
import sys
import magic
import iso9660
import argparse
import subprocess
import logging as log
import transmissionrpc as trpc

from shutil import copyfile
from distutils.spawn import find_executable

LOG_LEVEL = log.DEBUG
# HANDBRAKE_PATH = "/usr/bin/HandBrakeCLI"
HANDBRAKE_PATH = "/bin/echo"

RESOLUTIONS = {
    "480": {'X': 720, 'Y': 480},
    "576": {'X': 720, 'Y': 576},
    "720": {'X': 1280, 'Y': 720},
    "1080": {'X': 1920, 'Y': 1080},
    "2K": {'X': 2048, 'Y': 1080},
    "WQXGA": {'X': 2560, 'Y': 1600},
    "SHD": {'X': 3840, 'Y': 2160},
    "4K": {'X': 4096, 'Y': 2160}
}
EXCLUDED_EXT = [".part"]

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

PARSER = argparse.ArgumentParser(version     = '%(prog)s 1.0',
                                 add_help    = True,
                                 description = 'Just another HandBrakeCLI batch executor.')


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
                # sub[subCategory] = ''
            else:
                sub = {}
                subCategory = None
            mainKey[category] = ''
        elif line == '':
            if subCategory:
                # sub[subCategory] = subsub
                # sub.append({subCategory: subsub})
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
        return False

    if os.path.splitext(filePath)[1].lower() in ['.iso']:
        return is_iso_video(filePath)

    if os.path.splitext(filePath)[1].lower() in EXCLUDED_EXT:
        return False

    if 'video' in magic.from_file(filePath, mime=True).lower():
        return True

    return False


def is_iso_video(filePath):
    try:
        cd = iso9660.ISO9660(filePath)
        cdTree = cd.tree()

        if '/VIDEO_TS' in cdTree or '/AUDIO_TS' in cdTree:
            return True

    except:
        pass

    return False


def video_transcoder(inPath, outPath, res, ext):
    # Preset HandBrake
    PRESET = """
        -e x264
        -q 20.0
        -r 30
        --pfr
        --audio 1,2,3,4,5,6,7,8,9,10
        --subtitle scan,1,2,3,4,5,6,7,8,9,10
        -E ffaac,copy:ac3
        -B 160,160
        -6 dpl2,none
        -R Auto,Auto
        -D 0.0,0.0
        --audio-copy-mask aac,ac3,dtshd,dts,mp3
        --audio-fallback ffac3
        -4
        -X %d
        -Y %d
        --decomb=fast
        --loose-anamorphic
        --modulus 2
        -m
        -O
        --x264-preset medium
        --h264-profile high
        --h264-level 4.0
        %s
        """ % (RESOLUTIONS[res]["X"], RESOLUTIONS[res]["Y"], '-f %s' % ext if ext else '')

    cmd = '"%s" -v -i "%s" %s -o "%s" ' % (HANDBRAKE_PATH, inPath, PRESET.replace('\n', ''), outPath)
    process = subprocess.Popen(cmd,
                               shell=True,
                               stderr=subprocess.PIPE,
                               stdout=subprocess.PIPE)
    (output, error) = process.communicate()

    return process.returncode


def copy_transcode(src_file, dst_dir):
    fileName, ext = os.path.splitext(os.path.basename(src_file))
    ext = ext.lstrip('.').lower()

    if OUT_EXT:
        ext = OUT_EXT

    if TMP_DIR:
        copyfile(src_file, TMP_DIR)
        video_transcoder(os.path.join(TMP_DIR, os.path.basename(src_file)),
                         os.path.join(TMP_DIR, '%s_transcoded.%s' % (fileName, ext)),
                         MAX_RES,
                         OUT_EXT)
        os.rename(os.path.join(TMP_DIR, '%s_transcoded.%s' % (fileName, ext)), dst_dir)

    else:
        video_transcoder(src_file,
                         os.path.join(dst_dir, '%s_transcoded.%s' % (fileName, ext)),
                         MAX_RES,
                         OUT_EXT)


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
        if type(LANG) == list:
            for f_lang in fileLang:
                if f_lang in LANG:
                    return True
        else:
            if LANG in fileLang:
                return True

    elif type(fileLang) == str:
        if fileLang in LANG:
            return True

    return False


def get_completed_downloads(host, port, usr, psw):
    retList = []
    maskFileList = []
    trasmissionFiles = []

    torrents = trpc.Client(host, port, usr, psw).get_torrents()
    for torrent in torrents:
        if torrent.status == 'stopped' and torrent.progress == 100:
            for key, value in dict(torrent.files()).iteritems():
                if convert_bytes(value['size']) >= MAX_SIZE:
                    if MASK_DIR:
                        trasmissionFiles.append([torrent._fields['downloadDir'].value, value['name']])
                    elif is_video_file([torrent._fields['downloadDir'].value, value['name']]):
                        retList.append([torrent._fields['downloadDir'].value, value['name']])

    if MASK_DIR:
        for path, subdirs, files in os.walk(MASK_DIR):
            for name in files:
                if is_video_file([path, name]):
                    maskFileList.append([path, name])

        for transmissionFile in trasmissionFiles:
            for maskFile in maskFileList:
                if transmissionFile[1] in maskFile:
                    retList.append(maskFile)
                    break

    return retList


def scan_torrents(fileList):
    if SRC_DIR:
        for download in get_completed_downloads(T_HOST, T_PORT, T_USER, T_PSW):
            if download[0] != SRC_DIR:
                fileList.append(download)
    else:
        fileList = get_completed_downloads(T_HOST, T_PORT, T_USER, T_PSW)

    log.info('Found %d completed files on Transmission' % len(fileList))

    return fileList


def scan_path(fileList):
    for path, subdirs, files in os.walk(SRC_DIR):
        for file in files:
            try:
                if is_video_file([path, file]):
                    file_path = os.path.join(path, file)
                    file_info = os.stat(file_path)
                    file_size = convert_bytes(file_info.st_size)
                    if file_size >= MAX_SIZE:
                        fileList.append([path, file])
            except:
                pass

    return fileList


def scan_file():
    if is_video_file(FILE_PATH):
        file = os.path.basename(FILE_PATH)
        path = os.path.dirname(FILE_PATH)
        return [[path, file]]

    return []


def scan_txt():
    retList = []

    with open(TXT_PATH) as f:
        lines = f.readlines()
        for line in lines:
            line_cleaned = line.strip('\r').strip()
            if line_cleaned != '':
                if is_video_file(line_cleaned):
                    file = os.path.basename(line_cleaned)
                    path = os.path.dirname(line_cleaned)
                    retList.append([path, file])

    return retList


def printHelp(message=None):
    PARSER.print_help()
    if message:
        log.error(message)
    sys.exit(1)


def convert_bytes(num):
    """
    this function will convert bytes to MB
    """
    for x in ['bytes', 'KB']:
        num /= 1024.0

    return float("%3.1f" % num)


def args_extraction(argv):
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

    g_group = PARSER.add_argument_group('Input Scan')
    t_group = PARSER.add_argument_group('Transmission')
    v_group = PARSER.add_argument_group('Video')

    g_group.add_argument('-s', '--source',       action = "store",  default = None,   dest = "SRC_DIR",   type = str,   required = False, help = 'Source path used for scan')
    g_group.add_argument('-t', '--tmp',          action = "store",  default = None,   dest = "TMP_DIR",   type = str,   required = False, help = 'Temporary folder')
    g_group.add_argument('-d', '--destination',  action = "store",  default = None,   dest = "DST_DIR",   type = str,   required = False, help = '''
                                                                                                                                                 Destination folder for converted items.
                                                                                                                                                 If not specified source and destination are the same
                                                                                                                                                 ''')
    t_group.add_argument('-m', '--mask',         action = "store",  default = None,   dest = "MASK_DIR",  type = str,   required = False, help = '''
                                                                                                                                                 Used if you are running this script outside of Transmission
                                                                                                                                                 This is the local raggiungible path for Transmission downloads
                                                                                                                                                 ''')
    g_group.add_argument('-T', '--txt',          action = "store",  default = None,   dest = "TXT_PATH",  type = str,   required = False, help = 'List of files in a *.txt list')
    g_group.add_argument('-f', '--file',         action = "store",  default = None,   dest = "FILE_PATH", type = str,   required = False, help = 'One shot execution for a single file')
    v_group.add_argument('-e', '--extension',    action = "store",  default = None,   dest = "OUT_EXT",   type = str,   required = False, help = 'Extension for output transcoded file')
    t_group.add_argument(      '--host',         action = "store",  default = None,   dest = "T_HOST",    type = str,   required = False, help = 'Transmission host address')
    t_group.add_argument(      '--port',         action = "store",  default = 9091,   dest = "T_PORT",    type = int,   required = False, help = 'Transmission host port (default=9091)')
    t_group.add_argument(      '--user',         action = "store",  default = None,   dest = "T_USER",    type = str,   required = False, help = 'Transmission username')
    t_group.add_argument(      '--psw',          action = "store",  default = None,   dest = "T_PSW",     type = str,   required = False, help = 'Transmission password')
    v_group.add_argument('-S', '--size',         action = "store",  default = 1200.0, dest = "MAX_SIZE",  type = float, required = False, help = 'The minimum file size limit for conversion')
    v_group.add_argument('-r', '--resolution',   action = "store",  default = '720',  dest = "MAX_RES",   type = str,   required = False, help = '''
                                                                                                                                                 Resolution for output transcoded file.
                                                                                                                                                 The value is one of:
                                                                                                                                                 480, 576, 720, 1080, 2K, WQXGA, SHD, 4K
                                                                                                                                                 ''')
    v_group.add_argument('-l', '--language',     action = "append", default = None,   dest = "LANG",      type = str,   required = False, help = '''
                                                                                                                                                 List of language needed in the file for start the conversion
                                                                                                                                                 ''')

    if not argv:
        log.error("No arguments provided")
        print "No arguments provided"
        printHelp()

    # args = vars(PARSER.parse_args(['-h']))
    args = vars(PARSER.parse_args(argv))

    for key, value in dict(args).iteritems():
        globals()[key] = value

    check_parameters()


def check_parameters():
    if not T_HOST and MASK_DIR:
        printHelp('Cannot set Mask directory if Torrent Host is not defined')

    if TXT_PATH and (T_HOST or SRC_DIR):
        printHelp('Cannot read list if Torrent Host and/or source dir are defined')

    if FILE_PATH and (T_HOST or SRC_DIR):
        printHelp('Cannot convert single file if Torrent Host and/or source dir are defined')

    if FILE_PATH and TXT_PATH:
        printHelp('Cannot read list if single file is defined')

    if not os.path.exists(SRC_DIR):
        printHelp('Source path don\'t exist!')

    if not os.path.exists(TMP_DIR):
        printHelp('Temporary Dir path don\'t exist!')

    if not os.path.exists(DST_DIR):
        printHelp('TorrentMask path don\'t exist!')

    if not os.path.exists(MASK_DIR):
        printHelp('Destination path don\'t exist!')


def main(argv):
    cont = 0
    fileList = []

    log.basicConfig(level=LOG_LEVEL)

    args_extraction(argv)
    # sys.exit(0)

    if FILE_PATH:
        fileList = scan_file()

    if TXT_PATH:
        fileList = scan_txt()

    if T_HOST:
        fileList = scan_torrents(fileList)
        cont = len(fileList)

    if SRC_DIR:
        fileList = scan_path(fileList)
        log.info('Found %d during scan' % (len(fileList) - cont))

    log.info('%d total files in list for evaluating' % len(fileList))

    for item in fileList:
        this_FullPath = os.path.join(item[0], item[1])
        this_FileName, this_ext = os.path.splitext(item[1])
        this_ext = this_ext.lstrip('.').lower()
        this_lang = []

        if not DST_DIR:
            this_destDir = item[0]
        else:
            this_destDir = DST_DIR

        mediaInfo = get_media_info(this_FullPath)

        if 'ISO' in mediaInfo['General']['Format']:
            copy_transcode(this_FullPath, this_destDir)
            continue

        if 'Video' not in mediaInfo:
            continue

        this_res = int(mediaInfo['Video']['Height'].replace(' ', '').replace('pixels', ''))

        if this_res > RESOLUTIONS[MAX_RES]['Y']:
            if 'Audio' in mediaInfo:
                this_lang = get_video_lang(mediaInfo['Audio'])

            if lang_exists(this_lang):
                copy_transcode(this_FullPath, this_destDir)


########################################
########################################
###############  MAIN  #################
########################################
########################################

if __name__ == "__main__":
    main(sys.argv[1:])
