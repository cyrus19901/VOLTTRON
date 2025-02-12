# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2017, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

import logging
import sys

from volttron.platform.vip.agent import *
from volttron.platform.agent.base_historian import BaseHistorian, add_timing_data_to_header
from volttron.platform.agent import utils
from volttron.platform.agent import math_utils

utils.setup_logging()
_log = logging.getLogger(__name__)


def historian(config_path, **kwargs):

    config = utils.load_config(config_path)
    utils.update_kwargs_with_config(kwargs, config)

    class NullHistorian(BaseHistorian):
        '''This historian forwards data to another platform.
        '''

        def __init__(self, **kwargs):
            super(NullHistorian, self).__init__(**kwargs)

            if self._gather_timing_data:
                self._turnaround_times = []

        @Core.receiver("onstart")
        def starting(self, sender, **kwargs):
            
            _log.debug('Null historian started.')

        def publish_to_historian(self, to_publish_list):

            for item in to_publish_list:
                if self._gather_timing_data:
                    turnaround_time = add_timing_data_to_header(item["headers"],
                                                                self.core.agent_uuid or self.core.identity,
                                                                "published")
                    self._turnaround_times.append(turnaround_time)
                    if len(self._turnaround_times) > 10000:
                        # Test is now over. Button it up and shutdown.
                        mean = math_utils.mean(self._turnaround_times)
                        stdev = math_utils.stdev(self._turnaround_times)
                        _log.info("Mean time from collection to publish: " + str(mean))
                        _log.info("Std dev time from collection to publish: " + str(stdev))
                        self._turnaround_times = []
                #_log.debug("publishing {}".format(item))

            _log.debug("recieved {} items to publish"
                       .format(len(to_publish_list)))

            self.report_all_handled()

        def query_historian(self, topic, start=None, end=None, agg_type=None,
              agg_period=None, skip=0, count=None, order="FIRST_TO_LAST"):
            """Not implemented
            """
            raise NotImplemented("query_historian not implimented for null historian")

    return NullHistorian(**kwargs)


def main(argv=sys.argv):
    """Main method called by the aip."""
    try:
        utils.vip_main(historian, identity="nullhistorian")
    except Exception as e:
        print(e)
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass