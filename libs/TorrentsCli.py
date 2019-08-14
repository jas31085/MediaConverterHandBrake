#!/usr/bin/env python
# -*- coding: utf-8 -*-

import transmissionrpc as trpc

from os import walk
from os.path import join

from .Video import Video
from .commons import convertBytes
from .mediaLogger import MediaLogger

logger = MediaLogger(__name__, level=MediaLogger.DEBUG)


class TorrentsCli(object):

    def __init__(self, user, password, host, port, maskDir=None, maxSize=0):
        self.user = user
        self.password = password
        self.host = host
        self.port = port

        self.maskDir = maskDir
        self.maxSize = maxSize

        self.trClient = trpc.Client(self.host, self.port, self.user, self.password)

    def get_completed_downloads(self):
        retList = []
        maskFileList = []
        trasmissionFiles = []

        logger.info('Connecting to Transmission server.')
        torrents = self.trClient.get_torrents()
        logger.debug('%d Torrents found.' % len(torrents))

        for torrent in torrents:
            if torrent.status == 'stopped' and torrent.progress == 100:
                for key, value in dict(torrent.files()).items():
                    if convertBytes(value['size']) >= self.maxSize:
                        logger.debug('Evaluating completed Download: %s' % value['name'])
                        if self.maskDir:
                            trasmissionFiles.append( Video( join(torrent._fields['downloadDir'].value, value['name']), torrentID=torrent._fields['id'].value ))
                        else:
                            videoFile = Video( join(torrent._fields['downloadDir'].value, value['name']) )
                            if videoFile.isVideo: retList.append( videoFile )

        # TODO: Riduci il ciclo
        if self.maskDir:
            for path, subdirs, files in walk(self.maskDir):
                for name in files:
                    videoFile = Video( join(path, name) )
                    if videoFile.isVideo:
                        maskFileList.append( videoFile )

            for transmissionFile in trasmissionFiles:
                for maskFile in maskFileList:
                    if transmissionFile.fileName == maskFile.fileName:
                        retList.append( transmissionFile )
                        break

        return retList

    def remove_torrent(self, torrentID):
        logger.info('Removing download from Transmission.')
        self.trClient.remove_torrent(torrentID, True)

    def scan_torrents(self, fileList, srcDir):
        completeDownloads = self.get_completed_downloads()

        if srcDir:
            for download in completeDownloads:
                if download.filePath != srcDir:
                    fileList.append(download)
        else:
            fileList += completeDownloads

        logger.info('Found %d completed files on Transmission' % len(fileList))

        return fileList
