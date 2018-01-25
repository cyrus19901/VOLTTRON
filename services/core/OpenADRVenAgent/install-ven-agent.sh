cd $VOLTTRON_ROOT
export VIP_SOCKET="ipc://$VOLTTRON_HOME/run/vip.socket"
python ~/Desktop/volttron/scripts/install-agent.py \
    -s ~/Desktop/volttron/services/core/OpenADRVenAgent \
    -i venagent \
    -c ~/Desktop/volttron/services/core/OpenADRVenAgent/openadrven.config \
    -t venagent \
    -f
