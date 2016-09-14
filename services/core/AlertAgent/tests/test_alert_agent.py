# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
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
# }}}

import pytest
import gevent
import json

from volttron.platform.agent.known_identities import PLATFORM_ALERTER

ALERT_CONFIG = {
    "fakedevice": 5,
    "fakedevice2": {
        "seconds": 5,
        "points": ["point"]
    }
}

alert_messages = {}

@pytest.fixture(scope='module')
def agent(request, volttron_instance1):

    alert_uuid = volttron_instance1.install_agent(
        agent_dir="services/core/AlertAgent",
        config_file=ALERT_CONFIG)
    gevent.sleep(2)

    agent = volttron_instance1.build_agent()

    def onmessage(peer, sender, bus, topic, headers, message):
        global alert_messages

        alert = json.loads(message)["context"]

        try:
            alert_messages[alert] += 1
        except KeyError:
            alert_messages[alert] = 1

    agent.vip.pubsub.subscribe(peer='pubsub',
                               prefix='alert',
                               callback=onmessage)

    def stop():
        volttron_instance1.stop_agent(alert_uuid)
        agent.core.stop()

    request.addfinalizer(stop)
    return agent


def test_alert_agent(agent):
    global alert_messages
    for _ in range(10):
        agent.vip.pubsub.publish(peer='pubsub',
                                 topic='fakedevice')
        agent.vip.pubsub.publish(peer='pubsub',
                                 topic='fakedevice2',
                                 message=[{'point': 'value'}])
        gevent.sleep(1)

    assert not alert_messages
    gevent.sleep(6)

    assert len(alert_messages) == 3


def test_ignore_topic(agent):
    global alert_messages

    agent.vip.rpc.call(PLATFORM_ALERTER, 'ignore_topic', 'fakedevice2').get()
    alert_messages.clear()
    gevent.sleep(6)

    assert len(alert_messages) == 1
    assert u'fakedevice not published within time limit' in alert_messages


def test_watch_topic(agent):
    global alert_messages

    agent.vip.rpc.call(PLATFORM_ALERTER, 'watch_topic', 'newtopic', 5).get()
    gevent.sleep(6)

    assert u'newtopic not published within time limit' in alert_messages


def test_watch_device(agent):
    global alert_messages

    agent.vip.rpc.call(PLATFORM_ALERTER, 'watch_device', 'newdevice', 5, ['point']).get()
    gevent.sleep(6)

    assert u'newdevice not published within time limit' in alert_messages
    assert u'newdevice(point) not published within time limit' in alert_messages
