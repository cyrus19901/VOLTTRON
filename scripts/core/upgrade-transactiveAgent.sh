#!/usr/bin/env bash

# Build a temp file string for use with the configuration
export CONFIG=$(mktemp /tmp/abc-script.XXXXXX)

# Put contents of the config file in between the EOL markers.
# NOTE: Be mindful of the commas this is JSON (except for the comments)
#       not python.  Trailing ',' are an error.
cat > $CONFIG <<EOL
{

    "agentId": "TransactiveAgent",
    "hassConfigPath":"/home/yingying/Desktop/home-assistant/config/configuration.yaml",
    "device_list":["AC1","AC2","WH1","wh-9845"],
    "url":"http://localhost:8123/api/",
    "urlPass":"NULL",
    "entityID":"transactive_home.transactive_home",
    "friendly_name":"Transactive Home",
    "state" : "connected_homes",
    "password": "admin",
    "request":"post",
    "message": "hello"
 
}
EOL

export SOURCE=examples/TransactiveAgent/
export TAG=transactiveAgent

# Uncomment this to set the identity of the agent. Overrides the platform default identity and the agent's
# preferred identity.
export AGENT_VIP_IDENTITY='my_transactive'

# Add NO_START parameter if the agent shouldn't start
# export NO_START=1

./scripts/core/make-agent.sh 

# To set the agent to autostart with the platform, pass "enable" 
# to make-agent.sh: ./scripts/core/make-agent.sh enable

# Finally remove the temporary config file
rm $CONFIG
