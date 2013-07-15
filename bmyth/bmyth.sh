 
#!/bin/sh
# written by scott Morton 7/14/2013
# bmyth.sh is Bounce MYTH FE for those nasty occasions when it locks up.
# Set LIRC to execute this with the power buttom or button of your choice.

declare -i DTIME=$(date '+%s')			# get current time
declare -i BMYTHTIME=$(cat ~/.bmythtime)	# get previous time form file

#echo $DTIME, $BMYTHTIME

DIF=$(($DTIME - $BMYTHTIME))			# calculate difference

#echo $DIF

if [ $DIF -gt 10 ] || [ $DIF -eq 0 ]; then	# if eq 0 then this is first use

  echo $DTIME >~/.bmythtime			# write current time stamp to file
  #echo in loop
  PIDS='100'

  while [ "$PIDS" != "" ]			# had an issue with multiple copies of the FE running
    do
	  PIDS=$(pidof mythfrontend)		# check to see if MFE is running
	  pkill mythfrontend			# Kill it
	  sleep 5				# wait 5 seconds
	  #echo $PIDS
    done


else
  #echo exit loop
  exit 0					# else force exit with status 0

fi


