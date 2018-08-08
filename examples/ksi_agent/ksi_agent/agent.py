"""
KSI Agent to demonstrate signing and verification services.
"""
import base64
import hashlib

__docformat__ = 'reStructuredText'

import logging

import sys

print sys.path

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.messaging import headers as headers_mod, topics
import simplejson as json
from datetime import datetime
import time
import ksi

print sys.path

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.1"


class KsiAgent(Agent):
    """
    Document agent constructor here.
    """

    def __init__(self, config_path,
                 **kwargs):
        super(KsiAgent, self).__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)

        try:
            config = utils.load_config(config_path)
        except StandardError:
            config = {}

        if not config:
            _log.info("Using Agent defaults for starting configuration.")

        self.pub_signer = config.get('pub_sign', "/ksi_sign/signed_data")
        self.pub_verifier = config.get('pub_verify', "/ksi_verify/verified_data")
	self.subscriptions = {"devices/fake-campus/fake-building/fake-device/all": self.handle_signing,
			      "/ksi/verify": self.handle_verification}
#        self.subscriptions = {"/raj/ksi/sign": self.handle_signing,
#                              "/ksi/verify": self.handle_verification}

        self.agentid = config.get('agentid', "ksi_agent")
        self.rcvd_msg = None
        self.verify_msg = None
        self.KSI = ksi.KSI(**ksi.ksi_env())
        self.KSI.set_verification_policy(self.KSI.verification.POLICY_KEY_BASED)

    def __del__(self):
        try:
            _log.info('cleaning KSI object')
            del self.KSI
        except AttributeError:
            pass

    @Core.receiver("onstart")
    def onstart(self, sender, **kwargs):
        """
        This is method is called once the Agent has successfully connected to the platform.
        This is a good place to setup subscriptions if they are not dynamic or
        do any other startup activities that require a connection to the message bus.
        Called after any configurations methods that are called at startup.

        Usually not needed if using the configuration store.
        """
        # Example publish to pubsub
        # self.vip.pubsub.publish('pubsub', "some/random/topic", message="HI!")

        self._create_subscriptions()

        # Example RPC call
        # self.vip.rpc.call("some_agent", "some_method", arg1, arg2)

    def publish_signing(self):
        signature = None
        try:
            signature = self.KSI.sign_hash(hashlib.sha256(json.dumps(self.rcvd_msg)))
            encoded_sign = base64.b64encode(signature.serialize())
            self.rcvd_msg.append({'signature': encoded_sign})
        except Exception as e:
            _log.error(e)
            raise e
        finally:
            try:
                _log.debug("Cleaning signature")
                del signature
            except AttributeError:
                pass

        hdrs = {'AgentId': self.agentid,
                'KISSAware': 'yes'
                }
        self.vip.pubsub.publish('pubsub', self.pub_signer, hdrs, self.rcvd_msg)

    def publish_verification(self):
        verification_result = None
        ksi_obj = None
	#print(self.verify_msg[2]['signature'])
        rcvd_signature = self.verify_msg[2]['signature']
        signature = base64.b64decode(rcvd_signature)
        del self.verify_msg[2]
        try:
            ksi_obj = self.KSI.parse(signature)
            hasher = ksi_obj.get_hasher()
            json_msg = json.dumps(self.verify_msg)
            hasher.update(json_msg)
            verification_result = self.KSI.verify_hash(ksi_obj, hasher)
        except Exception as e:
            _log.error(e)
            raise e
        finally:
            try:
                del ksi_obj
            except AttributeError:
                pass

        hdrs = {'AgentId': self.agentid,
                'KISSAware': 'yes'
                }
        self.verify_msg.append({'signature': rcvd_signature})
        self.verify_msg.append({'verification_result': verification_result})
        self.vip.pubsub.publish('pubsub', self.pub_verifier, hdrs, self.verify_msg)

    def _create_subscriptions(self):
        self.vip.pubsub.unsubscribe('pubsub', None, None)
        for topic in self.subscriptions:
            self.vip.pubsub.subscribe('pubsub', topic, callback=self.subscriptions[topic])

    def handle_signing(self, peer, sender, bus, topic, headers, message):
        _log.debug("Peer %r, Sender: %r, Topic: %r, Headers: %r, Message: %r \n\n", peer, sender, topic, headers,
                   message)
        self.rcvd_msg = message
        self.publish_signing()

    def handle_verification(self, peer, sender, bus, topic, headers, message):
        # _log.debug("Peer %r, Sender: %r, Topic: %r, Headers: %r, Message: %r", peer, sender, topic, headers,message)
        self.verify_msg = message
	self.publish_verification()

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
    utils.vip_main(KsiAgent,
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
