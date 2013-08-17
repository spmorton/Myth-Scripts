#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#---------------------------
#   Name: Myth-Rec-to-Vid.py
#   Python Script
#   Author: Scott Morton
# 
#   This is a rewrite of a script by Raymond Wagner
#   The objective is to clean it up and streamline the code for use with Myth 26


#   Converts MythTV Recordings to MythVideo in Version .26.
#---------------------------


__title__  = "Myth-Rec-to-Vid"
__author__ = "Scott Morton"
__version__= "v0.1"

from MythTV import MythDB, Job, Recorded, Video, VideoGrabber,\
                   MythLog, MythError, static, MythBE
from optparse import OptionParser, OptionGroup
from socket import gethostname

#import os
#import re
import sys, time, hashlib
#import time
#import hashlib

# Global Constants

# Modify these setting to your prefered defaults
TVFMT = 'Television/%TITLE%/Season %SEASON%/'+\
                    '%TITLE% - S%SEASON%E%EPISODEPAD% - %SUBTITLE%'

MVFMT = 'Movies/%TITLE%'

# Available strings:
#    %TITLE%:         series title
#    %SUBTITLE%:      episode title
#    %SEASON%:        season number
#    %SEASONPAD%:     season number, padded to 2 digits
#    %EPISODE%:       episode number
#    %EPISODEPAD%:    episode number, padded to 2 digits
#    %YEAR%:          year
#    %DIRECTOR%:      director
#    %HOSTNAME%:      backend used to record show
#    %STORAGEGROUP%:  storage group containing recorded show
#    %GENRE%:         first genre listed for recording

def hashfile(fd):
    hasher = hashlib.sha1()
    while True:
        buff = fd.read(2**16)
        if len(buff) == 0:
            break
        hasher.update(buff)
    return hasher.hexdigest()

class VIDEO:
    def __init__(self, opts, jobid=None):
        
        # Setup for the job to run
        if jobid:
            self.thisJob = Job(jobid)
            self.chanID = self.thisJob.chanid
            self.startTime = self.thisJob.starttime
            self.thisJob.update(status=Job.STARTING)
            
        # If no job ID given, must be a command line run
        else:
            self.chanID = opts.chanid
            self.startTime = opts.starttime

        #self.opts = opts



        # Capture the backend host name
        self.host = self.db.gethostname()

        
        self.db = MythDB()
        self.log = MythLog(module='Myth-Rec-to-Vid.py', db=self.db)

 

        # prep objects
        self.rec = Recorded((self.chanid,self.starttime), db=self.db)
        self.log(MythLog.GENERAL, MythLog.INFO, 'Using recording',
                        '%s - %s' % (self.rec.title.encode('utf-8'), 
                                     self.rec.subtitle.encode('utf-8')))
        self.vid = Video(db=self.db).create({'title':'', 'filename':'',
                                             'host':self.host})


    def copy_markup(self, start, stop):
        for mark in self.rec.markup:
            if mark.type in (start, stop):
                self.vid.markup.add(mark.mark, 0, mark.type)

    def copy_seek(self):
        for seek in self.rec.seek:
            self.vid.markup.add(seek.mark, seek.offset, seek.type)
                
    def dup_check(self):
        bend = MythBE(db=self.vid._db)
        self.log(MythLog.GENERAL, MythLog.INFO, 'Checking for duplication of ',
                    '%s - %s' % (self.rec.title.encode('utf-8'), 
                                 self.rec.subtitle.encode('utf-8')))
        if bend.fileExists(self.vid.filename, 'Videos'):
          self.log(MythLog.GENERAL, MythLog.INFO, 'Recording already exists in Myth Videos')
          self.job.setComment("Action would result in duplicate entry, job ended" )
          self.job.setStatus(Job.FINISHED)
          self.vid.delete()
          self.log(MythLog.GENERAL, MythLog.INFO, 'Exiting program')
          sys.exit(0)
          
        else:
            self.log(MythLog.GENERAL, MythLog.INFO, 'No duplication found for ',
                    '%s - %s' % (self.rec.title.encode('utf-8'), 
                                 self.rec.subtitle.encode('utf-8')))
    
    def get_dest(self):
        if self.type == 'TV':
            self.vid.filename = self.process_fmt(TVFMT)
        elif self.type == 'MOVIE':
            self.vid.filename = self.process_fmt(MVFMT)

    def get_meta(self):
        metadata = self.rec.exportMetadata()
        self.vid.importMetadata(metadata)
        self.log(self.log.GENERAL, self.log.INFO, 'MetaData Import complete')

    def get_type(self):
            if self.rec.season is not 0 or self.rec.subtitle:
                self.type = 'TV'
                self.log(self.log.GENERAL, self.log.INFO,
                        'Performing TV export.')
            else:
                self.type = 'MOVIE'
                self.log(self.log.GENERAL, self.log.INFO,
                        'Performing Movie export.')

    def process_fmt(self, fmt):
        # replace fields from viddata

        ext = '.'+self.rec.basename.rsplit('.',1)[1]
        rep = ( ('%TITLE%','title','%s'),   ('%SUBTITLE%','subtitle','%s'),
            ('%SEASON%','season','%d'),     ('%SEASONPAD%','season','%02d'),
            ('%EPISODE%','episode','%d'),   ('%EPISODEPAD%','episode','%02d'),
            ('%YEAR%','year','%s'),         ('%DIRECTOR%','director','%s'))
        for tag, data, format in rep:
            if self.vid[data]:
                fmt = fmt.replace(tag,format % self.vid[data])
            else:
                fmt = fmt.replace(tag,'')

        # replace fields from program data
        rep = ( ('%HOSTNAME%',    'hostname',    '%s'),
                ('%STORAGEGROUP%','storagegroup','%s'))
        for tag, data, format in rep:
            data = getattr(self.rec, data)
            fmt = fmt.replace(tag,format % data)


        if len(self.vid.genre):
            fmt = fmt.replace('%GENRE%',self.vid.genre[0].genre)
        else:
            fmt = fmt.replace('%GENRE%','')
        return fmt+ext

    def copy(self):
        stime = time.time()
        srcsize = self.rec.filesize
        htime = [stime,stime,stime,stime]

        self.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "Copying myth://%s@%s/%s"\
               % (self.rec.storagegroup, self.rec.hostname, self.rec.basename)\
                                                    +" to myth://Videos@%s/%s"\
                                          % (self.vid.host, self.vid.filename))
        
 
        srcfp = self.rec.open('r')
        dstfp = self.vid.open('w')

        if self.job:
            self.job.setStatus(Job.RUNNING)
            tsize = 2**24
            while tsize == 2**24:
                tsize = min(tsize, srcsize - dstfp.tell())
                dstfp.write(srcfp.read(tsize))
                htime.append(time.time())
                rate = float(tsize*4)/(time.time()-htime.pop(0))
                remt = (srcsize-dstfp.tell())/rate
                if self.job:
                    self.job.setComment("%02d%% complete - %d seconds remaining" %\
                                          (dstfp.tell()*100/srcsize, remt))
            srcfp.close()
            dstfp.close()
            
            self.vid.hash = self.vid.getHash()
            
            self.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "Transfer Complete",
            			      "%d seconds elapsed" % int(time.time()-stime))
            
            if self.opts.reallysafe:
                if self.job:
                    self.job.setComment("Checking file hashes")
                self.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "Checking file hashes.")
                srchash = hashfile(self.rec.open('r'))
                dsthash = hashfile(self.rec.open('r'))
                if srchash != dsthash:
                    raise MythError('Source hash (%s) does not match destination hash (%s)' \
                	      % (srchash, dsthash))
            elif self.opts.safe:
                self.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "Checking file sizes.")
                be = MythBE(db=self.vid._db)
                try:
                    srcsize = be.getSGFile(self.rec.hostname, self.rec.storagegroup, \
                			self.rec.basename)[1]
                    dstsize = be.getSGFile(self.vid.host, 'Videos', self.vid.filename)[1]
                except:
                    raise MythError('Could not query file size from backend')
                if srcsize != dstsize:
                    raise MythError('Source size (%d) does not match destination size (%d)' \
                            	      % (srcsize, dstsize))
            
            if self.job:
                self.job.setComment("Complete - %d seconds elapsed" % \
            	      (int(time.time()-stime)))
                self.job.setStatus(Job.FINISHED)
