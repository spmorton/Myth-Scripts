#!/usr/bin/env python3
#---------------------------
#   Name: Myth-Rec-to-Vid.py
#   Python Script
#   Author: Scott Morton
# 

#   Migrates MythTV Recordings to MythVideo in Version .26.
#---------------------------


__title__  = "Myth-Rec-to-Vid"
__author__ = "Scott Morton"
__version__= "v2.2.2"

from MythTV import MythDB, Job, Recorded, Video, VideoGrabber,\
                   MythLog, static, MythBE    
from optparse import OptionParser, OptionGroup

import sys, time

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
            self.thisJob = jobid
            self.chanID = opts.chanid
            self.startTime = opts.startdate + " " + opts.starttime + opts.offset
        self.opts = opts
        self.type = "none"
        self.db = MythDB()
        self.log = MythLog(module='Myth-Rec-to-Vid.py', db=self.db)
        self.log(MythLog.GENERAL, MythLog.INFO, 'Recorording info', 
                        'JobID -  %d, ChanID - %d, StartTime - %s' % (jobid,
                                     self.chanID, 
                                     self.startTime))


        # Capture the backend host name
        self.host = self.db.gethostname()

        # prep objects
        self.rec = Recorded((self.chanID,self.startTime), db=self.db)
        self.log(MythLog.GENERAL, MythLog.INFO, 'Using recording',
                        '%s - %s' % (self.rec.title.encode('utf-8'), 
                                     self.rec.subtitle.encode('utf-8')))

        self.vid = Video(db=self.db).create({'title':u'', 'filename':u'',
                                             'host':self.host})

        self.bend = MythBE(db=self.db)
        
        
    def check_hash(self):
        self.log(self.log.GENERAL, self.log.INFO,
                 'Performing copy validation.')
        srchash = self.bend.getHash(self.rec.basename, self.rec.storagegroup)
        dsthash = self.bend.getHash(self.vid.filename, 'Videos')
        if srchash != dsthash:
            return False
        else:
            return True
               
    def copy(self):
        stime = time.time()
        srcsize = self.rec.filesize
        htime = [stime,stime,stime,stime]

        self.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "Copying myth://%s@%s/%s"\
               % (self.rec.storagegroup, self.rec.hostname, self.rec.basename)\
                                                    +" to myth://Videos@%s/%s"\
                                          % (self.host, self.vid.filename))
        
 
        srcfp = self.rec.open('r')
        dstfp = self.vid.open('w')

        if self.thisJob:
            self.set_job_status(Job.RUNNING)
        tsize = 2**24
        while tsize == 2**24:
            tsize = min(tsize, srcsize - dstfp.tell())
            dstfp.write(srcfp.read(tsize))
            htime.append(time.time())
            rate = float(tsize*4)/(time.time()-htime.pop(0))
            remt = (srcsize-dstfp.tell())/rate
            if self.thisJob:
                self.thisJob.setComment("%02d%% complete - %d seconds remaining" %\
                                      (dstfp.tell()*100/srcsize, remt))
        srcfp.close()
        dstfp.close()
        
        self.vid.hash = self.vid.getHash()
        
        self.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "Transfer Complete",
        			      "%d seconds elapsed" % int(time.time()-stime))

        if self.thisJob:
            self.thisJob.setComment("Complete - %d seconds elapsed" % \
        	      (int(time.time()-stime)))

    def copy_markup(self, start, stop):
        for mark in self.rec.markup:
            if mark.type in (start, stop):
                self.vid.markup.add(mark.mark, 0, mark.type)

    def copy_seek(self):
        for seek in self.rec.seek:
            self.vid.markup.add(seek.mark, seek.offset, seek.type)
                
    def delete_vid(self):
        self.vid.delete()
        
    def delete_rec(self):
        self.rec.delete()
        
    def dup_check(self):
        self.log(MythLog.GENERAL, MythLog.INFO, 'Processing new file name ',
                    '%s' % (self.vid.filename))
        self.log(MythLog.GENERAL, MythLog.INFO, 'Checking for duplication of ',
                    '%s - %s' % (self.rec.title.encode('utf-8'), 
                                 self.rec.subtitle.encode('utf-8')))
        if self.bend.fileExists(self.vid.filename, 'Videos'):
            self.log(MythLog.GENERAL, MythLog.INFO, 'Recording already exists in Myth Videos')
            if self.thisJob:
                self.thisJob.setComment("Action would result in duplicate entry" )
            return True
          
        else:
            self.log(MythLog.GENERAL, MythLog.INFO, 'No duplication found for ',
                    '%s - %s' % (self.rec.title.encode('utf-8'), 
                                 self.rec.subtitle.encode('utf-8')))
            return False 

    def get_dest(self):
        if self.type == 'TV':
            self.vid.filename = self.process_fmt(TVFMT)
        elif self.type == 'MOVIE':
            self.vid.filename = self.process_fmt(MVFMT)
        
        self.vid.markup._refdat = (self.vid.filename,)

    def get_meta(self):
        import_info = 'Listing only MetaData import complete'
        #metadata = self.rec.exportMetadata()
        #yrInfo = self.rec.getProgram()
        #metadata['year'] = yrInfo.get('year')
        
     #   try:
        self.vid.importMetadata(self.rec.exportMetadata())
        self.vid.year = self.rec.getProgram().year
        
    #    except Exception, e:
   #         print e
  #          self.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "ERROR in grab", \
 #   			      "Message was: %s" % e.message % "\n")
#            raise e
        
        if self.type == 'MOVIE':
            grab = VideoGrabber('Movie')
            try:
                results = grab.sortedSearch(self.rec.title)
                
            except Exception as e:
                print (e)
                self.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "ERROR in MOVIE grab", \
        			      "Message was: %s" % e.message)
                print ("error in grab") 

            if len(results) > 0:
                for i in results:
                    if i.year == self.rec.getProgram().year and i.title == self.rec.get('title'):
                        self.vid.importMetadata(i)
                        match = grab.grabInetref(i.get('inetref'))
                        length = len(match.people)
                        for p in range(length-2):
                            self.vid.cast.add(match.people[p].get('name'))
                        self.vid.director = match.people[length - 1].get('name')
                        import_info = 'Full MetaData Import complete'
        else:
            try:
                grab = VideoGrabber('TV')
                results = grab.sortedSearch(self.rec.title, self.rec.subtitle)
            except Exception as e:
                print (e)
                self.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "ERROR in TV grab", \
        			      "Message was: %s" % e)
                print ("error in grab") 

            if len(results) > 0:
                for i in results:
                    if  i.title == self.rec.get('title') and i.subtitle == self.rec.get('subtitle'):
                        self.vid.importMetadata(i)
                        match = grab.grabInetref(grab.grabInetref(i.get('inetref'), \
                                season=i.get('season'),episode=i.get('episode')))
                        length = len(match.people)
                        for p in range(length-2):
                            self.vid.cast.add(match.people[p].get('name'))
                        self.vid.director = match.people[length - 1].get('name')
                        import_info = 'Full MetaData Import complete'
            
        
        self.vid.category = self.rec.get('category')

        self.log(self.log.GENERAL, self.log.INFO, import_info)

    def get_type(self):
        if self.rec.programid[:2] == 'MV':
            self.type = 'MOVIE'
            self.log(self.log.GENERAL, self.log.INFO,
                    'Performing MOVIE type migration.')
        else:
            self.type = 'MOVIE'
            self.log(self.log.GENERAL, self.log.INFO,
                    'Performing TV type migration.')

    def process_fmt(self, fmt):
        # replace fields from viddata
        # print self.vid.items()        
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

    def set_job_status(self, status):
        self.thisJob.setStatus(status)
        
    def set_vid_hash(self):
        self.vid.hash = self.vid.getHash()
    
    def update_vid(self):
        self.vid.update()
        
#---END CLASS--------------------------------------------------

def main():
    parser = OptionParser(usage="usage: %prog [options] [jobid]")

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
    actiongroup.add_option("--deleteanyway", action="store_true", default=False,
            help="Delete source recording if duplicate destination exists.")
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

    def error_out():
        export.delete_vid()
        if export.thisJob:        
            export.set_job_status(Job.ERRORED)
        sys.exit(1)
        
    if opts.verbose:
        if opts.verbose == 'help':
            print (MythLog.helptext)
            sys.exit(0)
        MythLog._setlevel(opts.verbose)

    if opts.delete:
        opts.safe = True

    # if a manual channel and time entry then setup the export with opts
    if opts.chanid and opts.startdate and opts.starttime and opts.offset:
        try:
            export = VIDEO(opts)

        except Exception as e:
            sys.exit(1)

    # If an auto or manual job entry then setup the export with the jobID
    elif len(args) == 1:
        try:
            export = VIDEO(opts,int(args[0]))

        except Exception as e:
            print (e)
            Job(int(args[0])).update({'status':Job.ERRORED,
                                      'comment':'ERROR: ' + e})
            MythLog(module='Myth-Rec-to-Vid.py').logTB(MythLog.GENERAL)
            sys.exit(1)

    # else bomb the job and return an error code
    else:
        parser.print_help()
        sys.exit(2)

    # Export object created so process the job
    try:
        export.get_type()
        export.get_meta()
        export.get_dest()

    except Exception as e:
        export.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "ERROR in Processing 'gets'",
    			      "Message was: %s" % e.message)
        error_out()

    if (export.dup_check()):
        if(opts.deleteanyway):
            export.delete_rec()
        export.delete_vid()
        if export.thisJob:
            export.set_job_status(Job.FINISHED)
        sys.exit(0)

    else:
        try:
            export.copy()
            print ('copy finished')
            export.update_vid()
            print ('update finished')
            export.set_vid_hash()
            print ('hash finished')

        except Exception as e:
            print (e)
            export.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "ERROR in Processing 'exports'",
        			      "Message was: %s" % e)
            #error_out()

        try:
            if not export.check_hash():
                error_out()
                
        except Exception as e:
            export.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "ERROR in Hash Check",
        			      "Message was: %s" % e.message)
            error_out()

    if opts.seekdata:
        try:
            export.copy_seek()

        except Exception as e:
            export.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "ERROR in Seek Data", \
        			      "Message was: %s" % e.message)
            if opts.safe:
                error_out()

    if opts.skiplist:
        try:
            export.copy_markup(static.MARKUP.MARK_COMM_START,
                         static.MARKUP.MARK_COMM_END)

        except Exception as e:
            export.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "ERROR in Skip List", \
        			      "Message was: %s" % e.message)
            if opts.safe:
                error_out()

    if opts.cutlist:
        try:
            export.copy_markup(static.MARKUP.MARK_CUT_START,
                         static.MARKUP.MARK_CUT_END)
        except Exception as e:
            export.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "ERROR in Cut List",
        			      "Message was: %s" % e.message)
            if opts.safe:
                error_out()

    # delete old file
    if opts.delete:
        try:
            export.delete_rec()

        except Exception as e:
            export.log(MythLog.GENERAL|MythLog.FILE, MythLog.INFO, "ERROR in Delete Orig",
        			      "Message was: %s" % e.message)
            if opts.safe:
                error_out()
    
    export.set_job_status(Job.FINISHED)
    

if __name__ == "__main__":
    main()
