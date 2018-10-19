#!/usr/bin/env bash
export SOURCE=examples/Ecobee/
export CONFIG=examples/Ecobee/config

export TAG=ecobeeGetSetpoint

# Uncomment to make this agent the platform historian.
export AGENT_VIP_IDENTITY=getSetpoint

./scripts/core/make-agent.sh

# To set the agent to autostart with the platform, pass "enable"
# to make-agent.sh: ./scripts/core/make-agent.sh enable
