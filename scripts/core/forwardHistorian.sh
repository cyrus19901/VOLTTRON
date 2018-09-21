#!/usr/bin/env bash
export SOURCE=services/core/ForwardHistorian
export CONFIG=services/core/ForwardHistorian/config

export TAG=Forwarder

# Uncomment to make this agent the platform historian.
#export AGENT_VIP_IDENTITY=platform.historian
export AGENT_VIP_IDENTITY='ForwardHistorian'
./scripts/core/make-agent.sh

# To set the agent to autostart with the platform, pass "enable"
# to make-agent.sh: ./scripts/core/make-agent.sh enable
