#!/usr/bin/env bash
export SOURCE=examples/HEMS-Agent-noLockout/
export CONFIG=examples/HEMS-Agent-noLockout/HEMS.config

export TAG=HEMS-dr-nolockout

# Uncomment to make this agent the platform historian.
export AGENT_VIP_IDENTITY=HEMS-nolockout

./scripts/core/make-agent.sh

# To set the agent to autostart with the platform, pass "enable"
# to make-agent.sh: ./scripts/core/make-agent.sh enable
