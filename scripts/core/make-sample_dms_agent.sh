#!/usr/bin/env bash
export SOURCE=examples/sample_dms_agent
export CONFIG=examples/sample_dms_agent/config

export TAG=sampleDMS

# Uncomment to make this agent the platform historian.
#export AGENT_VIP_IDENTITY=platform.historian

./scripts/core/make-agent.sh

# To set the agent to autostart with the platform, pass "enable"
# to make-agent.sh: ./scripts/core/make-agent.sh enable
