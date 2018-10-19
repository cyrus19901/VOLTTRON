#!/bin/bash
. env/bin/activate
vctl status
vctl stop c3
now=$(date +"%m_%d_%Y")
sudo scp -r -i "HA-VOLTTRON.pem" ~/.volttron/data/platform.historian.sqlite ubuntu@ec2-54-226-32-240.compute-1.amazonaws.com:~/data/181/platform.historian_$now.sqlite
sudo rm ~/.volttron/data/*
vctl start c3
