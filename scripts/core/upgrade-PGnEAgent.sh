#!/usr/bin/env bash
export SOURCE=/home/yingying/freshcopy/volttron-applications/pnnl/PGnE
export CONFIG=/home/yingying/freshcopy/volttron-applications/pnnl/PGnE/config

export TAG=PGnE

# Uncomment to make this agent the platform historian.
#export AGENT_VIP_IDENTITY=platform.historian
export AGENT_VIP_IDENTITY='PGnEAgent'
./scripts/core/make-agent.sh

# To set the agent to autostart with the platform, pass "enable"
# to make-agent.sh: ./scripts/core/make-agent.sh enable
