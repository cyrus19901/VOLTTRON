#!/usr/bin/env bash
export SOURCE=examples/EcobeeCurrentTemp/
export CONFIG=examples/EcobeeCurrentTemp/config

export TAG=ecobeeCurrentTemp

# Uncomment to make this agent the platform historian.
export AGENT_VIP_IDENTITY=ecobeeCurrent

./scripts/core/make-agent.sh

# To set the agent to autostart with the platform, pass "enable"
# to make-agent.sh: ./scripts/core/make-agent.sh enable
