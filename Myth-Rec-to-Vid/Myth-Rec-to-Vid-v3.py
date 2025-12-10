#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Myth-Rec-to-Vid-v3.py
    Copyright (C) 2025  Scott P. Morton PhD

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

#---------------------------
#   Name: Myth-Rec-to-Vidv3.py
#   Python Script
#   Author: Scott Morton PhD
# 
#   For use with Myth 34+


#   Migrates MythTV Recordings to MythVideo.
#---------------------------

# In Python, everything is an object, so it is a bit redundant to
# to write yet another class to make yet another object. With that,
# I abandon the 'class' method of previous approaches by myself and others
# so this should be easier to follow and adjust as desired


__title__  = "Myth-Rec-to-Vid-v3"
__author__ = "Scott P. Morton PhD"
__version__= "v3.1.3"

from MythTV import MythDB, Job, Recorded, Video, VideoGrabber,\
                   MythLog, static, MythBE    
from optparse import OptionParser, OptionGroup

import sys, os, time
from datetime import datetime

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

# an exit path

def error_out(vid, thisJob):
    vid.delete()
    if thisJob:
        thisJob.setStatus(Job.ERRORED)
    sys.exit(1)

def getType(rec):
    if rec.programid[:2] == 'MV':
        return 'MOVIE'
    else:
        return 'TV'

def dup_check(vid, rec, thisJob, bend, log):
    log(log.GENERAL, log.INFO, 'Processing new file name ',
                '{0}'.format(vid['filename']))
    log(log.GENERAL, log.INFO, 'Checking for duplication of ',
                '{0} - {1}'.format(rec['title'], 
                             rec['subtitle']))
    if bend.fileExists(vid['filename'], 'Videos'):
        log(log.GENERAL, log.INFO, 'Recording already exists in Myth Videos')
        if thisJob:
            thisJob.setComment("Action would result in duplicate entry" )
        return True
      
    else:
        log(log.GENERAL, log.INFO, 'No duplication found for ',
                '{0} - {1}'.format(rec['title'], 
                             rec['subtitle']))
        return False 

def copy(vid, rec, thisJob, log):
    stime = time.time()
    srcsize = rec.filesize
    htime = [stime,stime,stime,stime]

    srcfp = rec.open('r')
    dstfp = vid.open('w')

    if thisJob:
        thisJob.setStatus(Job.RUNNING)
    tsize = 2**24
    while tsize == 2**24:
        tsize = min(tsize, srcsize - dstfp.tell())
        dstfp.write(srcfp.read(tsize))
        htime.append(time.time())
        rate = float(tsize*4)/(time.time()-htime.pop(0))
        remt = (srcsize-dstfp.tell())/rate
        if thisJob:
            thisJob.setComment("%{:.2%}% complete - {} seconds remaining".format\
                                  (dstfp.tell()*100/srcsize, remt))
    srcfp.close()
    dstfp.close()
    
    vid.hash = vid.getHash()
    
    log(log.GENERAL|log.FILE, log.INFO, "Transfer Complete",
    			      "{} seconds elapsed".format(int(time.time()-stime)))

    if thisJob:
        thisJob.setComment("Complete - {} seconds elapsed".
                           format(int(time.time()-stime)))

def copy_markup(vid, rec, start, stop):
    for mark in rec.markup:
        if mark.type in (start, stop):
            vid.markup.add(mark.mark, 0, mark.type)

def check_hash(vid, rec, bend):
    srchash = bend.getHash(rec.basename, rec.storagegroup)
    dsthash = bend.getHash(vid.filename, 'Videos')
    if srchash != dsthash:
        return False
    else:
        return True

def main():
    jobid = 'MANUAL'
    chanID = ''
    startTime = ''
    db = MythDB()
    # host = db.dbconfig.hostname
    thisModule = 'Myth-Rec-to-Vid-v3.py'
    host = db.gethostname()
    bend = MythBE(db=db)

    # Capture the command line args
    parser = OptionParser(usage="usage: %prog [jobid] [options]")

    sourcegroup = OptionGroup(parser, "Source Definition",
                    "These options can be used to manually specify a recording to operate on "+\
                    "in place of the job id.")
    sourcegroup.add_option("--chanid", action="store", type="int", dest="chanid",
            help="Use chanid for manual operation, format interger")
    sourcegroup.add_option("--startdate", action="store", type="string", dest="startdate",
            help="Use startdate for manual operation, format is year-mm-dd")
    sourcegroup.add_option("--starttime", action="store", type="string", dest="starttime",
            help="Use starttime for manual operation, format is hh:mm:ss in UTC")
    sourcegroup.add_option("--offset", action="store", type="string", dest="offset",
            help="Use offset(timezone) for manual operation, format is [+/-]hh:mm. Do not adjust for DST")
    parser.add_option_group(sourcegroup)

    actiongroup = OptionGroup(parser, "Additional Actions",
                    "These options perform additional actions after the recording has been migrated. "+\
                    "A safe copy is always performed in that the file is checked to match the "+\
                    "MythBE hash. The safe copy option will abort the entire process if selected "+\
                    "along with Other Data and an exception occurs in the process")
    actiongroup.add_option('--safe', action='store_true', default=False, dest='safe',
            help='If other data is copied and a failure occurs this will abort the whole process.')
    actiongroup.add_option("--delete", action="store_true", default=False,
            help="Delete source recording after successful export. Enforces use of --safe.")
    parser.add_option_group(actiongroup)

    othergroup = OptionGroup(parser, "Other Data",
                    "These options copy additional information from the source recording.")
    othergroup.add_option("--seekdata", action="store_true", default=False, dest="seekdata",
            help="Copy seekdata from source recording.")
    othergroup.add_option("--skiplist", action="store_true", default=False, dest="skiplist",
            help="Copy commercial detection from source recording.")
    othergroup.add_option("--cutlist", action="store_true", default=False, dest="cutlist",
            help="Copy manual commercial cuts from source recording.")
    parser.add_option_group(othergroup)

    MythLog.loadOptParse(parser)
    opts, args = parser.parse_args()

    try:
        log = MythLog(module=thisModule, db=db)
        if opts.logpath:
            log._setfile('{0}/{1}.{2}.{3}.log'.format(opts.logpath,
                                    thisModule,
                                    datetime.now().strftime('%Y%m%d%H%M%S'),
                                    os.getpid()))
    except Exception as e:
        log.logTB(log.GENERAL)

    if opts.verbose:
        if opts.verbose == 'help':
            print (log.helptext)
            sys.exit(0)
        log._setlevel(opts.verbose)

    if opts.delete:
        opts.safe = True

    # if a manual channel and time entry then setup the export with opts
    if opts.chanid and opts.startdate and opts.starttime and opts.offset:
        try:
            chanID = opts.chanid
            startTime = opts.startdate + " " + opts.starttime + opts.offset

        except Exception as e:
            log.logTB("ERROR Processing fileName",
    			      "Message was: {0}".format(e.message))
            sys.exit(1)

    # If an auto or manual job entry then setup the export with the jobID
    elif len(args) >= 1:
        try:
            jobid = int(args[0])
            thisJob = Job(jobid)
            chanID = thisJob['chanid']
            startTime = thisJob['starttime']
            thisJob.update(status=Job.STARTING)

        except Exception as e:
            Job(jobid).update({'status':Job.ERRORED,
                                      'comment':'ERROR: ' + e})
            log.logTB(log.GENERAL, log.INFO, "ERROR Processing fileName",
    			      "Message was: {0}".format(e.message))
            sys.exit(0)

    # else bomb the job and return an error code
    else:
        parser.print_help()
        sys.exit(0)

    log(log.GENERAL, log.INFO, 'Recorording info', 
                    'JobID -  {}, ChanID - {}, StartTime - {}'.format(jobid,
                                 chanID, 
                                 startTime))

    # get the desired recording from Myth as an 'Object' and log it
    rec = Recorded((chanID,startTime), db=db)
    log(log.GENERAL, log.INFO, 'Using recording',
                    '{} - {}'.format(rec['title'], 
                                 rec['subtitle']))

    # get a blank video object from myth
    vid = Video(db=db).create({'title':u'', 'filename':u'',
                                         'host':host})

    # determien the time of recording
    thisType = getType(rec)
    log(log.GENERAL, log.INFO,
        'Attempting {} type migration.'.format(thisType))

    try:
        # create a file name without a lot of BS
        ext = rec.basename.rsplit('.',1)[1]
        if(thisType == 'TV'):
            # as in 'Television/%TITLE%/Season %SEASON%/'+\
            #            '%TITLE% - S%SEASON%E%EPISODEPAD% - %SUBTITLE%'
            fileName = 'Television/{0}/Season {1}/{2} - S{3}E{4} - {5}.{6}'.format(
                    rec['title'],
                    rec['season'],
                    rec['title'],
                    rec['season'],
                    rec['episode'],
                    rec['subtitle'],
                    ext)
            vid['contenttype'] = 'TELEVISION'
        else:
            # as in 'Movies/%TITLE%'
            fileName = 'Movies/{0}.{1}'.format(rec['title'],
                                               ext)
            vid['contenttype'] = 'MOVIE'
        # set the file name in the video object    
        vid['filename'] = fileName
    
    except Exception as e:
        log(log.GENERAL|log.FILE, log.INFO, "ERROR Processing fileName",
    			      "Message was: {0}".format(e.message))
        error_out(vid, thisJob)

    # make sure you are not creating a duplicate
    if (dup_check(vid, rec, thisJob, bend, log)):
        vid.delete()
        if thisJob:
            thisJob.setStatus(Job.FINISHED)
        sys.exit(0)

    else:
        try:
            log(log.GENERAL|log.FILE, MythLog.INFO, "Copying myth://{}@{}/{}"
                .format(rec['storagegroup'], rec['hostname'], rec['basename'])
                                                +" to myth://Videos@{}/{}"
                                                .format(host, vid['filename']))

            # I certainly hope the grabber is working and I do not need to
            # grab it again. If you have issues or missing data
            # see fix_metadata.py
            copy(vid, rec, thisJob, log)
            mdata = rec.exportMetadata()
            vid.importMetadata(mdata)
            vid.update()

        except Exception as e:
            log(log.GENERAL|log.FILE, log.INFO, "ERROR during copy",
        			      "Message was: {}".format(e))
            error_out(vid, thisJob)

        log(log.GENERAL, log.INFO,'Performing copy validation.')
        if not check_hash(vid, rec, bend):
            log(log.GENERAL|log.FILE, log.INFO, "ERROR in Hash Check")
            error_out(vid, thisJob)

    # this stuff still makes sense keep
    if opts.seekdata:
        try:
            for seek in rec.seek:
                vid.markup.add(seek.mark, seek.offset, seek.type)

        except Exception as e:
            log(log.GENERAL|log.FILE, log.INFO, "ERROR in Seek Data", \
        			      "Message was: {}".format(e.message))
            error_out(vid, thisJob)

    if opts.skiplist:
        try:
            copy_markup(vid, rec,
                        static.MARKUP.MARK_COMM_START,
                        static.MARKUP.MARK_COMM_END)

        except Exception as e:
            log(log.GENERAL|log.FILE, log.INFO, "ERROR in Skip List", \
        			      "Message was: {}".format(e.message))
            error_out(vid, thisJob)

    if opts.cutlist:
        try:
            copy_markup(vid, rec,
                        static.MARKUP.MARK_CUT_START,
                        static.MARKUP.MARK_CUT_END)
        except Exception as e:
            log(log.GENERAL|log.FILE, log.INFO, "ERROR in Cut List",
        			      "Message was: {}".format(e.message))
            error_out(vid, thisJob)

    # delete old file if that option is set
    if opts.delete:
        try:
            rec.delete()

        except Exception as e:
            log(log.GENERAL|log.FILE, log.INFO, "ERROR in Delete Orig",
        			      "Message was: {}".format(e.message))
            error_out(vid, thisJob)
    # duh
    thisJob.setStatus(Job.FINISHED)

if __name__ == "__main__":
    main()
