#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import magic
import iso9660
import subprocess

from .commons import convertBytes

from os import remove, stat
from os.path import basename, dirname, isfile, join, splitext

from shutil import copyfile, move
from distutils.spawn import find_executable

from libs.mediaLogger import MediaLogger
logger = MediaLogger(__name__, level=MediaLogger.DEBUG)

# HANDBRAKE_PATH = dirname(__file__) + "/HandBrakeCLI"
# HANDBRAKE_PATH = find_executable('HandBrakeCLI')
HANDBRAKE_PATH = "/bin/echo"  # Just for testing..

NICE_PATH = find_executable('nice')


class Video(object):
    RESOLUTIONS = {
        "480":   { 'X': 720,  'Y': 480  },
        "576":   { 'X': 720,  'Y': 576  },
        "720":   { 'X': 1280, 'Y': 720  },
        "1080":  { 'X': 1920, 'Y': 1080 },
        "2K":    { 'X': 2048, 'Y': 1080 },
        "WQXGA": { 'X': 2560, 'Y': 1600 },
        "SHD":   { 'X': 3840, 'Y': 2160 },
        "4K":    { 'X': 4096, 'Y': 2160 },
    }
    EXCLUDED_EXT = ['.part']

    def __init__(self, filePath, **kwargs):
        if type(filePath) == list: self.filePath = join(filePath[0], filePath[1])
        else: self.filePath = filePath

        self.fileDir = dirname(self.filePath)
        self.fileExt = splitext(basename(self.filePath))[1].lstrip('.')
        self.fileName = splitext(basename(self.filePath))[0]

        self.media_info = self.get_media_info()
        self.isVideo = self.is_video_file()
        self.isISO = self.is_iso_video()

        self.height = int(self.media_info['Video']['Height'].replace(' ', '').replace('pixels', '')) if 'Video' in self.media_info else None
        self.width = int(self.media_info['Video']['Width'].replace(' ', '').replace('pixels', '')) if 'Video' in self.media_info else None

        self.fileInfo = stat(self.filePath)
        self.fileSize = convertBytes(self.fileInfo.st_size)

        self.torrentID = (kwargs['torrentID'] if 'torrentID' in kwargs else None) if kwargs else None
        self.requiredLang = (kwargs['requiredLang'] if 'requiredLang' in kwargs else None) if kwargs else None
        self.newResolution = (kwargs['newResolution'] if 'newResolution' in kwargs else None) if kwargs else None

    def copy_transcode(self, **kwargs):
        this_inpDir = ''
        this_trnDir = ''
        this_outDir = ''
        this_lang = None

        if 'utils' in kwargs and 'extra' in kwargs:
            if 'audio_naming' in kwargs['extra'] and 'audio_naming' in kwargs['utils']:
                if type(kwargs['utils']['audio_naming']) == list:
                    this_lang = '_'.join(kwargs['utils']['audio_naming'])
                else:
                    this_lang = '_' + kwargs['utils']['audio_naming']

        out_fileName = '%s.%s'
        out_extension = kwargs['newExtension'] if kwargs['newExtension'] else self.fileExt

        if kwargs['tmpDir'] and kwargs['dstDir']:  # Case A
            this_inpDir = this_trnDir = kwargs['tmpDir']
            this_outDir = kwargs['dstDir']

        elif kwargs['tmpDir'] and not kwargs['dstDir']:  # Case B
            this_inpDir = this_trnDir = kwargs['tmpDir']
            this_outDir = dirname(self.filePath)

        elif not kwargs['tmpDir'] and kwargs['dstDir']:  # Case C
            this_inpDir = dirname(self.filePath)
            this_trnDir = this_outDir = kwargs['dstDir']

        elif not kwargs['tmpDir'] and not kwargs['dstDir']:  # Case D
            this_inpDir = this_trnDir = this_outDir = self.fileDir

        inputFile = join(this_inpDir, '%s.%s' % (self.fileName, self.fileExt))
        transFile = join(this_trnDir, '%s.%s' % (self.fileName + '_transcoded', out_extension))

        # TODO: Output FileName personalization
        if this_lang:
            outputFile = join(this_outDir, out_fileName % (self.fileName + '_' + this_lang, out_extension))
        else:
            outputFile = join(this_outDir, out_fileName % (
            self.fileName + '_transcoded' if not kwargs['dstDir'] else self.fileName, out_extension))

        # The magic begins..
        if kwargs['tmpDir']:
            logger.info('Start copying file to temporary directory.')
            logger.debug('cp %s %s' % (self.filePath, inputFile))
            copyfile(self.filePath, inputFile)
            logger.debug('Finish copy file to temporary directory.')

        retCode = self.transcode(inputFile, transFile, self.newResolution, out_extension)

        if retCode == 0:
            logger.info('Conversion finished without error.')
            if kwargs['tmpDir']:
                logger.info('Moving file from temporary to appropriate directory.')
                logger.debug('mv "%s" "%s"' % (transFile, outputFile))
                move(transFile, outputFile)
                logger.debug('rm "%s"' % inputFile)
                remove(inputFile)
            elif kwargs['dstDir']:
                logger.info('Moving file to appropriate directory.')
                logger.debug('mv "%s" "%s"' % (transFile, outputFile))
                move(transFile, outputFile)
            elif this_lang:
                logger.info('Renaming output file with extra informations.')
                logger.debug('mv "%s" "%s"' % (transFile, outputFile))
                move(transFile, outputFile)
                this_inpDir = None

            if kwargs['delSrc']:
                logger.info('Removing original file.')
                logger.debug('rm "%s"' % self.filePath)
                remove(self.filePath)
                # if self.torrentID: remove_torrent(self.torrentID)
                if this_inpDir == this_outDir and not kwargs['tmpDir']: move(transFile, outputFile)
        else:
            logger.error('Something goes wrong during conversion..')

    def get_media_info(self):
        """ Note this is media info cli """
        mediainfoPath = find_executable('mediainfo')
        cmd = '%s "%s"' % (mediainfoPath, self.filePath)

        process = subprocess.Popen(cmd,
                                   shell=True,
                                   stderr=subprocess.PIPE,
                                   stdout=subprocess.PIPE)
        (output, error) = process.communicate()

        mainKey = {}
        category = subCategory = sub = subsub = None
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

    def is_iso_video(self):
        try:
            if splitext(self.fileName)[1].lower() != 'iso': return False
            cd = iso9660.ISO9660(self.filePath)
            cdTree = cd.tree()

            if '/VIDEO_TS' in cdTree or '/AUDIO_TS' in cdTree:
                return True

            logger.debug("'%s' Skipped. The ISO file is not a Video file." % self.filePath)
        except Exception:
            logger.error('Failed while opening ISO file.', exc_info=True)
            logger.error("'%s'")
            pass

        return False

    def is_video_file(self):
        if not isfile(self.filePath):
            logger.debug("'%s' Skipped. File is not accessible." % self.filePath)
            return False

        if splitext(self.filePath)[1].lower() in Video.EXCLUDED_EXT:
            logger.debug("'%s' Skipped. Extension found in the excluded list." % self.filePath)
            return False

        if splitext(self.filePath)[1].lower() in ['.iso']:
            logger.info('%s ISO File found.' % self.filePath)
            return self.is_iso_video()

        magicInfo = magic.from_file(self.filePath, mime=True)

        if 'video' in magicInfo.lower():
            logger.info("'%s' OK: %s" % (basename(self.filePath), magicInfo))
            # Todo: verifica risoluzione, dimensione, lingue audio,
            return True

        if 'Video' in self.media_info:
            logger.info("'%s' OK: The file is a video." % basename(self.filePath))
            # Todo: verifica risoluzione, dimensione, lingue audio,
            return True

        return False

    def lang_exists(self, fileLang):
        if fileLang == '' or fileLang == [] or not self.requiredLang: return True

        if type(fileLang) == list:
            for f_lang in fileLang:
                if f_lang in self.requiredLang:
                    return True

        elif type(fileLang) == str:
            if fileLang in self.requiredLang:
                return True

        return False

    def setNewResolution(self, newRes):
        self.newResolution = newRes

    @staticmethod
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

    @staticmethod
    def transcode(inPath, outPath, res, ext):

        if not HANDBRAKE_PATH:
            logger.error('HandBrakeCLI not found, exiting')
            sys.exit(9)

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
            """ % (Video.RESOLUTIONS[res]["X"], Video.RESOLUTIONS[res]["Y"], '-f %s' % ext if ext else '')

        cmd = '"%s" -n 19 "%s" -v -i "%s" %s -o "%s" ' % (NICE_PATH, HANDBRAKE_PATH, inPath, PRESET.replace('\n', ''), outPath)

        logger.info('Starting video conversion')
        logger.debug('%s' % cmd)
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
                            logger.info(text)
                        elif percVal % 25 != 0 and logCtl:
                            logCtl = False

                        # print(perc.search(text).group(), end=out)

                    text = ''

        return process.returncode
