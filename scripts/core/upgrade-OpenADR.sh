#!/usr/bin/env bash
export SOURCE=/home/yingying/freshcopy/volttron/services/core/OpenADRVenAgent
export CONFIG=/home/yingying/freshcopy/volttron/services/core/OpenADRVenAgent/openadrven.config

export TAG=opeADR

# Uncomment to make this agent the platform historian.
#export AGENT_VIP_IDENTITY=platform.historian
export AGENT_VIP_IDENTITY='OpenADRVen'
./scripts/core/make-agent.sh

# To set the agent to autostart with the platform, pass "enable"
# to make-agent.sh: ./scripts/core/make-agent.sh enable