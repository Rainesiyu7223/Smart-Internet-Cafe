This document records the Raspberry command lines.
## Connecting and checking
- `ping 192.168.0.165` -- IP check
- `control + c` -- stop 
- `ssh admin@192.168.0.165` -- SSH connection

## Shut down and restart
- `sudo shutdown -h now` -- shut down
- `sudo reboot` -- restart

## Coding
- `nano docuName.py` -- open and coding in a document
- `control+o` -- saving the changes
- `enter` -- confirm
- `control+x` -- leaving from the document
- `control+k` -- deleting the line


## MQTT
- `brew services start mosquitto`  --start MQTT
- `mosquitto_sub -h 192.168.0.153` -t "#" -v -- receive data from raspberrypi
- `brew services list`
