
#!/usr/bin/env bash
export SOURCE=examples/PublisherSubscriber/
export CONFIG=examples/PublisherSubscriber/config

export TAG=publishersubscriber

# Uncomment to make this agent the platform historian.
export AGENT_VIP_IDENTITY=publisherSubscriber

./scripts/core/make-agent.sh

# To set the agent to autostart with the platform, pass "enable"
# to make-agent.sh: ./scripts/core/make-agent.sh enable


