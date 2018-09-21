#!/usr/bin/env bash
export SOURCE=services/ops/AlertAgent
export CONFIG=services/ops/AlertAgent/config

export TAG=AlertAgent

# Uncomment to make this agent the platform historian.
#export AGENT_VIP_IDENTITY=mqtt

./scripts/core/make-agent.sh

# To set the agent to autostart with the platform, pass "enable"
# to make-agent.sh: ./scripts/core/make-agent.sh enable
