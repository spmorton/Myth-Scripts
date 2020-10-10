#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 02:48:03 2020

@author: scott
"""


from MythTV import MythDB, Job, Recorded, Video, VideoGrabber,\
                   MythLog, static, MythBE    
from optparse import OptionParser, OptionGroup

import sys, time

db = MythDB()
    
xxx = Recorded.getAllEntries()
for i in xxx:
    if i.title == 'The Three Stooges' and i.season == 0:
        thisrec = i
        Job.fromRecorded(thisrec,4,args='/dev/null')
