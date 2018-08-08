"""
Agent documentation goes here.
"""

__docformat__ = 'reStructuredText'

import logging
import sys
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
from datetime import datetime
import time
import simplejson as json
import base64
import os
import gevent

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"

pub_period = 80


class Voltron_Agent(Agent):
    """
    Document agent constructor here.
    """

    def __init__(self, config_path,
                 **kwargs):
        super(Voltron_Agent, self).__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)

        try:
            config = utils.load_config(config_path)
        except StandardError:
            config = {}

        if not config:
            _log.info("Using Agent defaults for starting configuration.")

        self.pub_signing = config.get('pub_signing', "devices/fake-campus/fake-building/fake-device/all")
        self.pub_archive_data = config.get('pub_archive_data', "/historian/archive_data")

        self.subscriptions = {"/ksi_sign/signed_data": self.handle_signed_data}

        self.agentid = config.get('agentid', "voltron_agent")
        global pub_period
        pub_period = config.get('pub_period', "80")

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        """
        This is method is called once the Agent has successfully connected to the platform.
        This is a good place to setup subscriptions if they are not dynamic or
        do any other startup activities that require a connection to the message bus.
        Called after any configurations methods that are called at startup.

        Usually not needed if using the configuration store.
        """

        self._create_subscription()
        # Example publish to pubsub
        # self.vip.pubsub.publish('pubsub', "some/random/topic", message="HI!")

        # Example RPC call
        # self.vip.rpc.call("some_agent", "some_method", arg1, arg2)

#    @Core.periodic(pub_period)
#    def publish_signing(self):
#        msg = {}
#        msg_time = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
#        msg = {'msg_data': 'sample testing data', 'msg_create_time': msg_time}
#        hdrs = {'AgentId': self.agentid,
#                'KISSAware': 'yes'}
#        self.vip.pubsub.publish('pubsub', self.pub_signing, hdrs, msg)

    def _create_subscription(self):
        self.vip.pubsub.unsubscribe('pubsub', None, None)
        for topic in self.subscriptions:
            self.vip.pubsub.subscribe('pubsub', topic, callback=self.subscriptions[topic])

    def handle_signed_data(self, peer, sender, bus, topic, headers, message):

        _log.debug("Peer %r, Sender: %r, Topic: %r, Headers: %r, Message: %r\n\n", peer, sender, topic, headers,
                   message)
        #gevent.sleep(5)
        _log.debug("Archive message\n\n")
        self.archive_message(message)

    def archive_message(self, msg):

        hdrs = {'AgentId': self.agentid,
                'KISSAware': 'yes'
                }
        self.vip.pubsub.publish('pubsub', self.pub_archive_data, hdrs, msg)


    @Core.receiver("onstop")
    def onstop(self, sender, **kwargs):
        """
        This method is called when the Agent is about to shutdown, but before it disconnects from
        the message bus.
        """
        pass

    @RPC.export
    def rpc_method(self, arg1, arg2, kwarg1=None, kwarg2=None):
        """
        RPC method

        May be called from another agent via self.core.rpc.call """
        # return self.setting1 + arg1 - arg2
        pass


def main():
    """Main method called to start the agent."""
    utils.vip_main(Voltron_Agent,
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
