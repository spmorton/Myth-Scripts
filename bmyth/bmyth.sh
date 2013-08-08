 
#!/bin/sh
# written by scott Morton 7/14/2013
# bmyth.sh is Bounce MYTH FE for those nasty occasions when it locks up.
# Set LIRC to execute this with the power buttom or button of your choice.

# 8/7/2013 Added an '&' to allow the script to terminate after launch of MFE
# 8/7/2013 Added logic to run MFE from kstart if in a KDE env


__title__  = "bmyth.sh"
__author__ = "Scott Morton"
__version__= "1.2"

declare -i DTIME=$(date '+%s')			# get current time
declare -i BMYTHTIME=$(cat ~/.bmythtime)	# get previous time from file


DIF=$(($DTIME - $BMYTHTIME))			# calculate difference


if [ $DIF -gt 10 ] || [ $DIF -eq 0 ]; then	# if eq 0 then this is first use

  echo $DTIME >~/.bmythtime			# write current time stamp to file
  PIDS=$(pidof mythfrontend)			# prime the while loop

  while [ "$PIDS" != "" ]			# had an issue with multiple copies of the FE running
    do
	  pkill mythfrontend			# Kill it
	  sleep 5				# wait 5 seconds
	  PIDS=$(pidof mythfrontend)		# check to see if MFE is running
    done

  if [ $(echo $KDE_SESSION_VERSION) ]; then	# if kde is running then lets launch clean with the KDE env
    kstart /usr/bin/mythfrontend
    
  else
    mythfrontend &				# else just launch the dirty way
  
  fi

fi


