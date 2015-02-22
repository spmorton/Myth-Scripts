#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#---------------------------
#   Name: Myth-Vid-Tool.py
#   Python Script
#   Author: Scott Morton
# 
#   This is a rewrite of a script by Raymond Wagner
#   The objective is to clean it up and streamline 
#   the code for use with Myth 26


#   Migrates MythTV Recordings to MythVideo in Version .26.
#---------------------------


__title__  = "Myth-Vid-Tool"
__author__ = "Scott Morton"
__version__= "v1.0"

from MythTV import MythDB, Video, VideoGrabber, MythBE 
from optparse import OptionParser, OptionGroup

import sys

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
#    %YEAR%:          yearMythDB()
#    %DIRECTOR%:      director
#    %HOSTNAME%:      backend used to record show
#    %STORAGEGROUP%:  storage group containing recorded show
#    %GENRE%:         first genre listed for recording


def main():
    parser = OptionParser(usage="usage: option [option] [option]")

    maintenancegroup = OptionGroup(parser, "Maintenance",
                    "These options can be used to perform DB cleanup.")
    maintenancegroup.add_option("--dedup", action="store_true", default=False, dest="dedup",
            help="checks for duplicate entries in the Video database")
    maintenancegroup.add_option("--check_orphans", action="store_true", default=False, dest="check_orphans",
            help="checks for orphaned DB entries in Video")
    parser.add_option_group(maintenancegroup)
   
    actiongroup = OptionGroup(parser, "Meta Updates",
                    "This option updates Video Meta Data")
    actiongroup.add_option('--update', action='store_true', default=False, dest='update',
            help='Updates the video meta data on each entry')
    parser.add_option_group(actiongroup)
    
    othergroup = OptionGroup(parser, 'Other Options',
                             "These options allow for additional controls")
    othergroup.add_option('--folder', action='store', type='string', dest='folder',
                          help='Limits actions to Videos in a specified folder,\
                                  example "Movies" would limit to any filename \
                                  starting with Movies/some_video_file.mpg' )
    othergroup.add_option('--step', action="store_true", default=False, dest='step',
                          help='Steps through each action to allow evaluation of \
                                  process')
    parser.add_option_group(othergroup)
    

    
    opts, args = parser.parse_args()


 
    # if a manual channel and time entry then setup the export with opts

    # sys.exit(1)

    # setup the connection to the DB
    db = MythDB()
    be = MythBE()
    
    #Setup a scanner for all videos in the DB
    videos = db.searchVideos()
    # setup a Video object to work with    
    
    def get_Meta(item):
        
        metadata = item.exportMetadata()

        if not item.filename.startswith('Television'):
            grab = VideoGrabber('Movie')
            if item.get('inetref') != '00000000':
                try:
                    match = grab.grabInetref(item.inetref)
                    item.importMetadata(match)
                    item.plot = match.get('description')
                    item.title = match.get('title')
                    copy_Art(match, item)
                    item.update()
                    return

                except Exception:
                    print 'grabber failed for: ' + str(item.get('inetref'))
                    print 'trying by name instead'

            try:            
                results = grab.sortedSearch(item.title)
            except Exception, e:
                print 'grabber failed for: ' + str(item.get('inetref'))
                print e
                return
                    
            if len(results) > 0:
                if len(results) > 1:
                    menu = {}
                    list = 1
                    for each in results:
                        menu[list]= each.title + ', year: ' + str(each.get('year')) \
                                                + ', inetref: ' + str(each.get('inetref'))
                        list = list + 1
                    menu[list]='Skip to next video\n\n'
                    print '\n'
                    while True: 
                        options=menu.keys()
                        options.sort()
                        for entry in options: 
                            print entry, menu[entry]
                        try:
                            selection=input("Please Select: ") 
                            if selection in range (1,len(results)+1): 
                                listing = results[selection -1]
                                break
                            elif selection == len(results)+1:
                                return
                            else: 
                              print "Invalid Selection, try again!\n\n" 
                        except Exception:
                              print "Invalid Selection, try again!\n\n" 
                else:
                    listing = results[0]
                
                try:
                    match = grab.grabInetref(listing.get('inetref'))
                    item.importMetadata(match)
                    item.plot = match.get('description')
                    item.title = match.get('title')
                    copy_Art(match, item)
                    item.update()
                    print 'Full MetaData Import complete for: ' + item.title + '\n'

                except Exception, e:
                    print 'grabber failed for: ' + str(item.get('inetref'))
                    print e
                
 
            elif len(results) == 0:
                print 'No MetaData to import for: ' + item.title + '\n'
        else:
            grab = VideoGrabber('TV')
            results = grab.sortedSearch(item.title, item.subtitle)
            if len(results) > 0:
                if len(results) > 1:
                    menu = {}
                    list = 1
                    for each in results:
                        menu[list]= each.title + ' - ' + each.subtitle, \
                                        + ' year: ' + str(each.get('year')) \
                                        + ', inetref: ' + str(each.get('inetref'))
                        list = list + 1
                    menu[list]='Skip to next video\n\n'
                    while True: 
                        options=menu.keys()
                        options.sort()
                        for entry in options: 
                            print entry, menu[entry]
                        try:
                            selection=input("Please Select:") 
                            if selection in range (1,len(results)+1): 
                                listing = results[selection -1]
                                break
                            elif selection == len(results)+1:
                                return
                            else: 
                              print "Invalid Selection, try again!\n\n" 
                        except Exception:
                              print "Invalid Selection, try again!\n\n" 
                              
                else:
                    listing = results[0]
                    
                try:
                    match = grab.grabInetref(listing.get('inetref'))
                    item.importMetadata(match)
                    item.plot = match.get('description')
                    item.title = match.get('title')
                    copy_Art(match, item)
                    item.update()
                    print 'Full MetaData Import complete for: ' + item.title
                    
                except Exception, e:
                    print 'grabber failed for: ' + str(item.get('inetref'))
                    print e
                

            elif len(results) == 0:
                print 'No MetaData to import for: ' + item.title

        try:
            item.category = metadata.get('category')
            item.update()
        except Exception, e:
            print 'grabber failed for: ' + str(item.get('inetref'))
            print e
            
    def copy_Art(meta, item):
        select = {}
        for images in meta.images:
            if images.type not in select:
                select[images.type] = images

        for key in select:
            be.downloadTo(select[key]['url'], select[key]['type'], select[key]['filename'])
            if images.type == 'coverart':
                item.coverfile = images.filename
            elif images.type == 'screenshot':
                item.screenshot = images.filename
            elif images.type == 'banner':
                item.banner = images.filename
            elif images.type == 'fanart':
                item.fanart = images.filename
            elif images.type == 'trailer':
                item.trailer = images.filename
            
    #define a function to dedup the DB upon detection
    def del_dup(dup_item):
        vid = dup_item
        print 'Deleting duplicate entry for: ' + vid.title
        vid.delete()
    def deduplicate_DB(item,x):
        # try to determine if one of the items has more metadata
        # to retain than the other
        # otherwise delete the last entry in the DB
        if x.inetref > 0 and item.inetref == 0:
            del_dup(item)
        elif x.inetref == 0 and item.inetref > 0 :
            del_dup(x)
        else:
            del_dup(item)

    def Step(title):
        menu = {}
        menu[1]= 'Continue to process this video: ' + title
        menu[2]= 'Skip to next video'
        menu[3]= 'exit processing'
        
        while True: 
            options=menu.keys()
            options.sort()
            for entry in options: 
                print entry, menu[entry]
        
            selection=input("Please Select:") 
            if selection == 1:
                return False
            elif selection == 2:
                return True
            elif selection == 3:
                sys.exit(0)
            else: 
              print "Invalid Selection, try again!\n\n" 
        
    if opts.dedup and not opts.update and not opts.check_orphans:
        # Build a dictionary to store all searched videos
        check = {}

        # loop through the videos
        for item in videos:
            if opts.step:
                if Step(item.title):
                    continue
                
            if opts.folder:
                if item.title in check and item.filename.startswith(opts.folder):
                    x = check.get(item.title)
                    if item.filename == x.filename:
                        deduplicate_DB(item,x)
                        continue
                    else:                            
                        print 'Unable to determine desired operation for:'
                        print item.title
                        print 'The duplicate entries have different file names'
                        print item.filename
                        print x.filename
                        continue
                    
                else:
                    check[item.title] = item
            else:
                if item.title in check:
                    x = check.get(item.title)
                    if item.filename == x.filename:
                        deduplicate_DB(item,x)
                        continue
                    else:                            
                        print 'Unable to determine desired operation for:'
                        print item.title
                        print 'The duplicate entries have different file names'
                        print item.filename
                        print x.filename
                        continue
                    
                else:
                    check[item.title] = item
        sys.exit(0)

    elif not opts.dedup and opts.update and not opts.check_orphans:
        for item in db.searchVideos():
            if opts.step:
                if opts.folder:
                    if opts.folder == item.filename[:len(opts.folder)]:
                        if Step(item.title):
                            continue
                            
                elif Step(item.title):
                    continue
            if opts.folder:
                if opts.folder == item.filename[:len(opts.folder)]:
                    print item.title
                    get_Meta(item)
            else:
                print item.title
                get_Meta(item)
        sys.exit(0)
        
    elif not opts.dedup and not opts.update and opts.check_orphans:
        #if opts.step:
        #    if Step(item.title):
        #        continue
        sys.exit(0)

    elif len(args) == 0:
        parser.print_help()
        
    else:
        print 'You cannot perform meta updates/replace while deuping'
        print 'Suggest you dedup first and then update/replace meta'
        sys.exit(0)

      
if __name__ == "__main__":
    main()
