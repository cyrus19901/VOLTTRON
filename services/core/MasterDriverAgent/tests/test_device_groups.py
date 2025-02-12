# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
#}}}

"""
py.test cases for global master driver settings.
"""

import pytest

from volttron.platform import get_services_core
from volttrontesting.utils.platformwrapper import start_wrapper_platform
from volttron.platform.agent.known_identities import CONFIGURATION_STORE, PLATFORM_DRIVER
import gevent
from volttron.platform.vip.agent import Agent, PubSub
from volttron.platform.messaging import topics
from volttron.platform.agent.utils import parse_timestamp_string

def get_normalized_time_offset(time_string):
    """Parses time_string and returns timeslot of the the value assuming 1 second publish interval
    and 0.1 second driver_scrape_interval."""
    ts = parse_timestamp_string(time_string)
    return ts.microsecond // 100000

class _subscriber_agent(Agent):
    def __init__(self, **kwargs):
        super(_subscriber_agent, self).__init__(**kwargs)
        self.publish_results = {}

    def reset_results(self):
        print "Resetting results"
        self.publish_results.clear()

    def get_results(self):
        return self.publish_results.copy()

    def add_result(self, peer, sender, bus, topic, headers, message):
        print "message published to", topic
        self.publish_results[topic] = get_normalized_time_offset(headers['TimeStamp'])


@pytest.fixture(scope="module")
def subscriber_agent(request, volttron_instance1):

    agent = volttron_instance1.build_agent(identity='subscriber_agent',
                                          agent_class=_subscriber_agent)

    agent.vip.pubsub.subscribe(peer='pubsub',
                                prefix=topics.DRIVER_TOPIC_BASE,
                                callback=agent.add_result).get()

    yield agent

    agent.core.stop()

fake_device_config = """
{{
    "driver_config": {{}},
    "registry_config":"config://fake.csv",
    "interval": 1,
    "timezone": "US/Pacific",
    "heart_beat_point": "Heartbeat",
    "driver_type": "fakedriver",
    "group": {group}

}}
"""

master_driver_config = """
{{
    "driver_scrape_interval": 0.1,
    "group_offset_interval": {interval},
    "publish_breadth_first_all": false,
    "publish_depth_first_all": true,
    "publish_depth_first": false,
    "publish_breadth_first": false
}}
"""


registry_config_string = """Point Name,Volttron Point Name,Units,Units Details,Writable,Starting Value,Type,Notes
Float,Float,F,-100 to 300,TRUE,50,float,CO2 Reading 0.00-2000.0 ppm
FloatNoDefault,FloatNoDefault,F,-100 to 300,TRUE,,float,CO2 Reading 0.00-2000.0 ppm
"""




@pytest.fixture(scope="module")
def config_store_connection(request, volttron_instance1):

    connection = volttron_instance1.build_connection(peer=CONFIGURATION_STORE)
    # Reset master driver config store
    connection.call("manage_delete_store", PLATFORM_DRIVER)

    # Start the master driver agent which would in turn start the fake driver
    #  using the configs created above
    master_uuid = volttron_instance1.install_agent(
        agent_dir=get_services_core("MasterDriverAgent"),
        config_file={},
        start=True)
    print("agent id: ", master_uuid)
    gevent.sleep(2)  # wait for the agent to start and start the devices

    yield connection

    volttron_instance1.stop_agent(master_uuid)
    volttron_instance1.remove_agent(master_uuid)
    connection.kill()


@pytest.fixture(scope="function")
def config_store(request, config_store_connection):
    #Always have fake.csv ready to go.
    print "Adding fake.csv into store"
    config_store_connection.call("manage_store", PLATFORM_DRIVER, "fake.csv", registry_config_string, config_type="csv")

    yield config_store_connection
    # Reset master driver config store
    print "Wiping out store."
    config_store_connection.call("manage_delete_store", PLATFORM_DRIVER)
    gevent.sleep(0.1)


def setup_config(config_store, config_name, config_string, **kwargs):
    config = config_string.format(**kwargs)
    print "Adding", config_name, "to store"
    config_store.call("manage_store", PLATFORM_DRIVER, config_name, config, config_type="json")

def remove_config(config_store, config_name):
    print "Removing", config_name, "from store"
    config_store.call("manage_delete_config", PLATFORM_DRIVER, config_name)


@pytest.mark.driver
def test_no_groups(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config, interval=0)
    setup_config(config_store, "devices/fake0", fake_device_config, group=0)
    setup_config(config_store, "devices/fake1", fake_device_config, group=0)
    setup_config(config_store, "devices/fake2", fake_device_config, group=0)

    subscriber_agent.reset_results()

    #Give it enough time to publish at least once.
    gevent.sleep(2)

    results = subscriber_agent.get_results()

    assert results["devices/fake0/all"] == 0
    assert results["devices/fake1/all"] == 1
    assert results["devices/fake2/all"] == 2


@pytest.mark.driver
def test_groups_no_interval(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config, interval=0)
    setup_config(config_store, "devices/fake0", fake_device_config, group=0)
    setup_config(config_store, "devices/fake1", fake_device_config, group=1)
    setup_config(config_store, "devices/fake2", fake_device_config, group=2)

    subscriber_agent.reset_results()

    #Give it enough time to publish at least once.
    gevent.sleep(2)

    results = subscriber_agent.get_results()

    assert results["devices/fake0/all"] == 0
    assert results["devices/fake1/all"] == 0
    assert results["devices/fake2/all"] == 0

@pytest.mark.driver
def test_groups_interval(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config, interval=0.5)
    setup_config(config_store, "devices/fake0", fake_device_config, group=0)
    setup_config(config_store, "devices/fake1", fake_device_config, group=1)
    setup_config(config_store, "devices/fake2", fake_device_config, group=1)

    subscriber_agent.reset_results()

    #Give it enough time to publish at least once.
    gevent.sleep(2)

    results = subscriber_agent.get_results()

    assert results["devices/fake0/all"] == 0
    assert results["devices/fake1/all"] == 5
    assert results["devices/fake2/all"] == 6


@pytest.mark.driver
def test_add_remove_drivers(config_store, subscriber_agent):
    setup_config(config_store, "config", master_driver_config, interval=0.5)
    setup_config(config_store, "devices/fake0_0", fake_device_config, group=0)
    setup_config(config_store, "devices/fake0_1", fake_device_config, group=0)
    setup_config(config_store, "devices/fake0_2", fake_device_config, group=0)
    setup_config(config_store, "devices/fake1_0", fake_device_config, group=1)
    setup_config(config_store, "devices/fake1_1", fake_device_config, group=1)
    setup_config(config_store, "devices/fake1_2", fake_device_config, group=1)

    subscriber_agent.reset_results()

    #Give it enough time to publish at least once.
    gevent.sleep(2)

    results = subscriber_agent.get_results()

    assert results["devices/fake0_0/all"] == 0
    assert results["devices/fake0_1/all"] == 1
    assert results["devices/fake0_2/all"] == 2
    assert results["devices/fake1_0/all"] == 5
    assert results["devices/fake1_1/all"] == 6
    assert results["devices/fake1_2/all"] == 7

    remove_config(config_store, "devices/fake0_1")
    remove_config(config_store, "devices/fake1_1")

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(2)

    results = subscriber_agent.get_results()

    assert results["devices/fake0_0/all"] == 0
    assert results["devices/fake0_2/all"] == 2
    assert results["devices/fake1_0/all"] == 5
    assert results["devices/fake1_2/all"] == 7

    assert "devices/fake0_1/all" not in results
    assert "devices/fake1_1/all" not in results

    setup_config(config_store, "devices/fake0_1", fake_device_config, group=0)
    setup_config(config_store, "devices/fake1_1", fake_device_config, group=1)

    subscriber_agent.reset_results()

    # Give it enough time to publish at least once.
    gevent.sleep(2)

    results = subscriber_agent.get_results()

    assert results["devices/fake0_0/all"] == 0
    assert results["devices/fake0_1/all"] == 1
    assert results["devices/fake0_2/all"] == 2
    assert results["devices/fake1_0/all"] == 5
    assert results["devices/fake1_1/all"] == 6
    assert results["devices/fake1_2/all"] == 7

