#!/usr/bin/env python
# -*- coding: UTF-8 -*-

"""
    Myth-Rec-to-Vid.py
    Copyright (C) 2020  Scott P. Morton 

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
#   Name: Myth-Rec-to-Vid.py
#   Python Script
#   Author: Scott Morton
# 
#   For use with Myth 30+


#   Migrates MythTV Recordings to MythVideo.
#---------------------------


__title__  = "Myth-Rec-to-Vid"
__author__ = "Scott P. Morton"
__version__= "v2.0.2"

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

# In Python, everything is an object, so it is a bit redundant to
# to write yet another class to make yet another object. With that,
# I abandon the 'class' method of previous approaches by myself and others
# so this should be easier to follow and adjust as desired

# an exit path
def error_out(vid, thisJob):
    vid.delete()
    if thisJob:
        thisJob.setStatus(Job.ERRORED)
    sys.exit(1)

def getType(rec):
    if rec.seriesid != None and rec.programid[:2] != 'MV':
        return 'TV'
    else:
        return 'MOVIE'

def dup_check(vid, rec, thisJob, bend, log):
    log(MythLog.GENERAL, MythLog.INFO, 'Processing new file name ',
                '%s' % (vid['filename']))
    log(MythLog.GENERAL, MythLog.INFO, 'Checking for duplication of ',
                '%s - %s' % (rec['title'].encode('utf-8'), 
                             rec['subtitle'].encode('utf-8')))
    if bend.fileExists(vid['filename'], 'Videos'):
        log(MythLog.GENERAL, MythLog.INFO, 'Recording already exists in Myth Videos')
        if thisJob:
            thisJob.setComment("Action would result in duplicate entry" )
        return True
      
    else:
        log(MythLog.GENERAL, MythLog.INFO, 'No duplication found for ',
                '%s - %s' % (rec['title'].encode('utf-8'), 
                             rec['subtitle'].encode('utf-8')))
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
            thisJob.setComment("%02d%% complete - %d seconds remaining" %\
                                  (dstfp.tell()*100/srcsize, remt))
    srcfp.close()
    dstfp.close()
    
    vid.hash = vid.getHash()
    
    log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "Transfer Complete",
    			      "%d seconds elapsed" % int(time.time()-stime))

    if thisJob:
        thisJob.setComment("Complete - %d seconds elapsed" % \
    	      (int(time.time()-stime)))

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
    thisModule = 'Myth-Rec-to-Vid-v2.py'
    db = MythDB()
    host = db.dbconfig.hostname
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
        log._setfile('{0}/{1}.{2}.{3}.log'.format(opts.logpath,
                     thisModule,
                     datetime.now().strftime('%Y%m%d%H%M%S'),
                     os.getpid()))
    except Exception, e:
        MythLog(module=thisModule).logTB(MythLog.GENERAL,MythLog.INFO, "ERROR Processing fileName",
    			      "Message was: {0}".format(e.message))

    if opts.verbose:
        if opts.verbose == 'help':
            print MythLog.helptext
            sys.exit(0)
        MythLog._setlevel(opts.verbose)

    if opts.delete:
        opts.safe = True

    # if a manual channel and time entry then setup the export with opts
    if opts.chanid and opts.startdate and opts.starttime and opts.offset:
        try:
            chanID = opts.chanid
            startTime = opts.startdate + " " + opts.starttime + opts.offset

        except Exception, e:
            MythLog(module=thisModule).logTB(MythLog.GENERALMythLog.INFO, "ERROR Processing fileName",
    			      "Message was: {0}".format(e.message))
            sys.exit(1)

    # If an auto or manual job entry then setup the export with the jobID
    elif len(args) >= 1:
        try:
            print 'got to here\n'
            jobid = int(args[0])
            thisJob = Job(jobid)
            chanID = thisJob['chanid']
            startTime = thisJob['starttime']
            thisJob.update(status=Job.STARTING)

        except Exception, e:
            Job(jobid).update({'status':Job.ERRORED,
                                      'comment':'ERROR: ' + e})
            MythLog(module=thisModule).logTB(MythLog.GENERALMythLog.INFO, "ERROR Processing fileName",
    			      "Message was: {0}".format(e.message))
            sys.exit(0)

    # else bomb the job and return an error code
    else:
        parser.print_help()
        sys.exit(0)

    log(MythLog.GENERAL, MythLog.INFO, 'Recorording info', 
                    'JobID -  %d, ChanID - %d, StartTime - %s' % (jobid,
                                 chanID, 
                                 startTime))

    # get the desired recording from Myth as an 'Object' and log it
    rec = Recorded((chanID,startTime), db=db)
    log(MythLog.GENERAL, MythLog.INFO, 'Using recording',
                    '%s - %s' % (rec['title'].encode('utf-8'), 
                                 rec['subtitle'].encode('utf-8')))

    # get a blank video object from myth
    vid = Video(db=db).create({'title':u'', 'filename':u'',
                                         'host':host})

    # determien the time of recording
    thisType = getType(rec)
    log(log.GENERAL, log.INFO,
        'Attempting %s type migration.' % (thisType))

    try:
        # create a file name without a lot of BS
        ext = rec.basename.rsplit('.',1)[1]
        if(thisType == 'TV'):
            # as in 'Television/%TITLE%/Season %SEASON%/'+\
            #            '%TITLE% - S%SEASON%E%EPISODEPAD% - %SUBTITLE%'
            fileName = 'Television/{0}/Season {1}/{2} - S{3}E{4} - {5}.{6}'.format(
                    rec['title'].encode('utf-8'),
                    rec['season'],
                    rec['title'].encode('utf-8'),
                    rec['season'],
                    rec['episode'],
                    rec['subtitle'].encode('utf-8'),
                    ext)
        else:
            # as in 'Movies/%TITLE%'
            fileName = 'Movies/{0}'.format(rec['title'])
        # set the file name in the video object    
        vid['filename'] = fileName
    
    except Exception, e:
        log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "ERROR Processing fileName",
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
            log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "Copying myth://%s@%s/%s"\
                % (rec['storagegroup'], rec['hostname'], rec['basename'])\
                                                +" to myth://Videos@%s/%s"\
                                      % (host, vid['filename']))

            # I certainly hope the grabber is working and I do not need to
            # grab it again. If you have issues or missing data
            # see fix_metadata.py
            copy(vid, rec, thisJob, log)
            mdata = rec.exportMetadata()
            vid.importMetadata(mdata)
            vid.update()

        except Exception, e:
            log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "ERROR during copy",
        			      "Message was: %s" % e)
            error_out(vid, thisJob)

        log(log.GENERAL, log.INFO,'Performing copy validation.')
        if not check_hash(vid, rec, bend):
            log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "ERROR in Hash Check")
            error_out(vid, thisJob)

    # this stuff still makes sense keep
    if opts.seekdata:
        try:
            for seek in rec.seek:
                vid.markup.add(seek.mark, seek.offset, seek.type)

        except Exception, e:
            log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "ERROR in Seek Data", \
        			      "Message was: %s" % e.message)
            error_out(vid, thisJob)

    if opts.skiplist:
        try:
            copy_markup(vid, rec,
                        static.MARKUP.MARK_COMM_START,
                        static.MARKUP.MARK_COMM_END)

        except Exception, e:
            log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "ERROR in Skip List", \
        			      "Message was: %s" % e.message)
            error_out(vid, thisJob)

    if opts.cutlist:
        try:
            copy_markup(vid, rec,
                        static.MARKUP.MARK_CUT_START,
                        static.MARKUP.MARK_CUT_END)
        except Exception, e:
            log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "ERROR in Cut List",
        			      "Message was: %s" % e.message)
            error_out(vid, thisJob)

    # delete old file if that option is set
    if opts.delete:
        try:
            rec.delete()

        except Exception, e:
            log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "ERROR in Delete Orig",
        			      "Message was: %s" % e.message)
            error_out(vid, thisJob)
    # duh
    thisJob.setStatus(Job.FINISHED)

if __name__ == "__main__":
    main()
