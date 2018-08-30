from datetime import datetime
import gevent
import logging
import random
import sys
import numpy as np
import pandas as pd
import scipy.io
import scipy.io as sio
import pyexcel as pe
import math

# from examples.HEMS.AC_flexibility_prediction import AC_flexibility_prediction
# from examples.HEMS.AC_compute_temp import AC_compute_temp
# from examples.HEMS.market_clear_ideal_accurate_1AC import market_clear_ideal_accurate_1AC
# from examples.HEMS.AC_Temp_control import AC_Temp_control
# from examples.HEMS.AC_Tset_control_ideal import AC_Tset_control_ideal
# from examples.HEMS.AC_Status_update import AC_Status_update
from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, Core, RPC
from scipy.linalg import expm
from scipy.interpolate import interp1d
from scipy.interpolate import interp1d



utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'


def hems_dr(config_path, **kwargs):
    try:
        config = utils.load_config(config_path)
        print(config)
    except StandardError:
        config = {}

    if not config:
        _log.info("Using Agent defaults for starting configuration.")

    if not config.get("topic_mapping"):
        raise ValueError("Configuration must have a topic_mapping entry.")


    class HemsDR(Agent):


        def __init__(self, **kwargs):
            super(HemsDR, self).__init__(**kwargs)

        @Core.receiver('onsetup')
        def setup(self, sender, **kwargs):
            # Demonstrate accessing a value from the config file
            self._agent_id = config['agentid']

        # def __init__(self, topic_mapping, federate_name=None, broker_location="tcp://localhost:5570",
        #              time_delta="1s", subscription_topic=None, simulation_start_time=None, sim_length="10s",
        #              stop_agent_when_sim_complete=False, **kwargs):
        #     super(HemsDR, self).__init__(enable_fncs=True, enable_store=False, **kwargs)
        #     _log.debug("vip_identity: " + self.core.identity)

        #     self._federate_name = federate_name
        #     if self._federate_name is None:
        #         self._federate_name = self.core.identity
        #
        #     if not broker_location:
        #         raise ValueError("Invalid broker location specified.")
        #     self._broker_location = broker_location
        #     self._time_delta = time_delta
        #     self._topic_mapping = topic_mapping
        #     self._sim_start_time = simulation_start_time
        #     if self._sim_start_time is None:
        #         self._sim_start_time = datetime.now()
        #
        #     self._sim_length = sim_length
        #     self._stop_agent_when_complete = stop_agent_when_sim_complete
        #     self.subscription_topic = subscription_topic
        #     self.fncsmessage = None
        #     self.received_volttron = False
        #
        # @Core.receiver("onstart")
        # def onstart(self, sender, **kwargs):
        #     """
        #
        #     """
        #     # subscript to the volttron topic if given.
        #     if self.subscription_topic is not None:
        #         _log.info('Subscribing to ' + self.subscription_topic)
        #         self.vip.pubsub.subscribe(peer='pubsub',
        #                                   prefix=self.subscription_topic,
        #                                   callback=self.on_receive_publisher_message)
        #
        #     # Exit if fncs isn't installed in the current environment.
        #     if not self.vip.fncs.fncs_installed:
        #         _log.error("fncs module is unavailable please add it to the python environment.")
        #         self.core.stop()
        #         return
        #
        #     try:
        #
        #         self.vip.fncs.initialize(topic_maping=self._topic_mapping, federate_name=self._federate_name,
        #                                  time_delta=self._time_delta, sim_start_time=self._sim_start_time,
        #                                  sim_length=self._sim_length, work_callback=self.do_work,
        #                                  stop_agent_when_sim_complete=self._stop_agent_when_complete)
        #         self.vip.fncs.start_simulation()
        #
        #     except ValueError as ex:
        #         _log.error(ex.message)
        #         self.core.stop()
        #         return
        #
        # def do_work(self):
        #     current_values = self.vip.fncs.current_values
        #     _log.debug("Doing work: {}".format(self.core.identity))
        #     _log.debug("Current value: {}".format(current_values))
        #     # Check if the VOLTTRON agents update the information
        #     if self.subscription_topic is not None:
        #         while (self.received_volttron == False):
        #             gevent.sleep(0.2)
        #         value = self.fncsmessage
        #         self.received_volttron = False
        #     else:
        #         # If no topic is subscribed, then just use the dummy function
        #         value = str(random.randint(0, 10))
        #     _log.debug("New value is: {}".format(value))
        #     # Must publish to the fncs_topic here.
        #     self.vip.fncs.publish("devices/abcd", str(value))
        #     _log.debug('Volttron->FNCS:\nTopic:%s\nMessage:%s\n' % ("devices/abcd", str(value)))
        #     self.vip.fncs.next_timestep()
        #
        # def on_receive_publisher_message(self, peer, sender, bus, topic, headers, message):
        #     """
        #     Subscribe to publisher publications and change the data accordingly
        #     """
        #     # Update controller data
        #     val = message[0]
        #     # Currently only one topic is considered. In the future a dictionary should be used to check if all the topics are updated
        #     self.fncsmessage = float(val['test'])
        #     self.received_volttron = True
        #
        # @Core.receiver("onstop")
        # def onstop(self, sender, **kwargs):
        #     """
        #     This method is called when the Agent is about to shutdown, but before it disconnects from
        #     the message bus.
        #     """
        #     pass

    return HemsDR(**kwargs)

def main(argv=sys.argv):
    """Main method called to start the agent."""
    try:
        utils.vip_main(hems_dr, version=__version__)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())


