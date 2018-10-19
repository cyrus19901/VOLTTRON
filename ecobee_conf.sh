#!/bin/bash

volttron_log='/home/pi/volttron/volttron.log'
HA_log='/home/pi/Homeassistant-updated/config/home-assistant.log'
HA_db='/home/pi/Homeassistant-updated/config/home-assistant_v2.db'
syslog='/var/log/syslog'

#\cp /home/pi/Homeassistant-updated/config/ecobee.conf /home/pi/volttron/


if [ -e "$volttron_log" ]; then
   rm /home/pi/volttron/volttron.log
fi

if [ -e "$syslog" ]; then
   rm /var/log/syslog
fi

if [ -e "$HA_log" ]; then
   rm /home/pi/Homeassistant-updated/config/home-assistant.log
fi


if [ -e "$volttron_log" ]; then
   rm /home/pi/volttron/volttron.log
fi
