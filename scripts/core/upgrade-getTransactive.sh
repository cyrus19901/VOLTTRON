#!/usr/bin/env bash

# Build a temp file string for use with the configuration
export CONFIG=$(mktemp /tmp/abc-script.XXXXXX)

# Put contents of the config file in between the EOL markers.
# NOTE: Be mindful of the commas this is JSON (except for the comments)
#       not python.  Trailing ',' are an error.
cat > $CONFIG <<EOL
{

    "agentId": "TransactiveAgent",
    "hassConfigPath":"/home/pi/Homeassistant-updated/config/configuration.yaml",
    "device_list":["HVAC1","HVAC2","wh-9845"],
    "url":"http://localhost:8123/api/",
    "urlPass":"NULL",
    "password": "admin",
    "friendly_name":"Transactive Home",
    "state" : "on",
    "request":"post",
    "message": "hello"
 
}
EOL

export SOURCE=examples/GetTransactiveValues/
export TAG=getTransactive

# Uncomment this to set the identity of the agent. Overrides the platform default identity and the agent's
# preferred identity.
export AGENT_VIP_IDENTITY='my_getTransacitive'

# Add NO_START parameter if the agent shouldn't start
# export NO_START=1

./scripts/core/make-agent.sh 

# To set the agent to autostart with the platform, pass "enable" 
# to make-agent.sh: ./scripts/core/make-agent.sh enable

# Finally remove the temporary config file
rm $CONFIG
