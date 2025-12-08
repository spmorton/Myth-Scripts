# Myth-Scripts
Collection of personal scripts and information for MythTV

I changed over to Debian some time ago, the below is kept for posterity.

## Mythbackend.service on OpenSuse Leap
The following allows for the use of the native mythbackend.service file with systemd
```
  Rename /etc/init.d/mythbackend to something else ie mythbackend.bak
  Then issue the command 'touch /etc/init.d/mythbackend'
  Restart the backend service.
```
Myth-Rec-2-Vid 2.0.2 is not ready for primtime
