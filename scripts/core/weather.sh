#!/usr/bin/env bash
export SOURCE=services/core/WeatherAgent
export CONFIG=services/core/WeatherAgent/weatheragent.config

export TAG=weather

# Uncomment to make this agent the platform historian.
export AGENT_VIP_IDENTITY=weather

./scripts/core/make-agent.sh

# To set the agent to autostart with the platform, pass "enable"
# to make-agent.sh: ./scripts/core/make-agent.sh enable
