#!/usr/bin/env bash
export SOURCE=services/core/OpenADRVenAgent/
export CONFIG=services/core/OpenADRVenAgent/openadrven.config

export TAG=OpenADR

# Uncomment to make this agent the platform historian.
#export AGENT_VIP_IDENTITY=platform.historian
export AGENT_VIP_IDENTITY='OpenADR'
./scripts/core/make-agent.sh

# To set the agent to autostart with the platform, pass "enable"
# to make-agent.sh: ./scripts/core/make-agent.sh enable
