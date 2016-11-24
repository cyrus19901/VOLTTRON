# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
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

"""
.. _volttroncentral-agent:

The VolttronCentral(VCA) agent is used to manage remote VOLTTRON instances.
The VCA exposes a JSON-RPC based web api and a web enabled visualization
framework.  The web enabled framework is known as VOLTTRON
Central Management Console (VCMC).

In order for an instance to be able to be managed by VCMC a
:class:`vcplatform.agent.VolttronCentralPlatform` must be executing on the
instance.  If there is a :class:`vcplatform.agent.VolttronCentralPlatform`
running on the same instance as VCA it will be automatically registered as a
managed instance.  Otherwise, there are two different paths to registering an
instance with VCA.

1. Through the web api a call to the JSON-RPC method register_instance.
2. From an external platform through pub/sub.  this secondary method is
   preferred when deploying instances in the field that need to "phone home"
   to VCA after being deployed.
   
"""
import errno
import hashlib
import logging
import os
import os.path as p
import sys
from collections import defaultdict, namedtuple
from copy import deepcopy
from urlparse import urlparse

import datetime
import gevent
from volttron.platform.auth import AuthFile, AuthEntry
from zmq.utils import jsonapi

from authenticate import Authenticate
from sessions import SessionHandler
from volttron.platform import jsonrpc
from volttron.platform.agent import utils
from volttron.platform.agent.exit_codes import INVALID_CONFIGURATION_CODE
from volttron.platform.agent.known_identities import (
    VOLTTRON_CENTRAL, VOLTTRON_CENTRAL_PLATFORM, PLATFORM_HISTORIAN)
from volttron.platform.agent.utils import (
    get_aware_utc_now, format_timestamp)
from volttron.platform.jsonrpc import (
    INVALID_REQUEST, METHOD_NOT_FOUND,
    UNHANDLED_EXCEPTION, UNAUTHORIZED,
    DISCOVERY_ERROR,
    UNABLE_TO_UNREGISTER_INSTANCE, UNAVAILABLE_PLATFORM, INVALID_PARAMS,
    UNAVAILABLE_AGENT)
from volttron.platform.messaging.health import Status, \
    BAD_STATUS, GOOD_STATUS, UNKNOWN_STATUS
from volttron.platform.vip.agent import Agent, RPC, PubSub, Core, Unreachable
from volttron.platform.vip.agent.connection import Connection
from volttron.platform.vip.agent.subsystems.query import Query
from volttron.platform.web import (DiscoveryInfo, DiscoveryError)

__version__ = "3.6.0"

utils.setup_logging()
_log = logging.getLogger(__name__)

# Web root is going to be relative to the volttron central agents
# current agent's installed path
DEFAULT_WEB_ROOT = p.abspath(p.join(p.dirname(__file__), 'webroot/'))

Platform = namedtuple('Platform', ['instance_name', 'serverkey', 'vip_address'])
RequiredArgs = namedtuple('RequiredArgs', ['id', 'session_user',
                                           'platform_uuid'])

class VolttronCentralAgent(Agent):
    """ Agent for managing many volttron instances from a central web ui.

    During the


    """
    __name__ = 'VolttronCentralAgent'

    def __init__(self, config_path, **kwargs):
        """ Creates a `VolttronCentralAgent` object to manage instances.

         Each instances that is registered must contain a running
         `VolttronCentralPlatform`.  Through this conduit the
         `VolttronCentralAgent` is able to communicate securly and
         efficiently.

        :param config_path:
        :param kwargs:
        :return:
        """
        _log.info("{} constructing...".format(self.__name__))

        super(VolttronCentralAgent, self).__init__(enable_web=True, **kwargs)
        # Load the configuration into a dictionary
        config = utils.load_config(config_path)

        # Required users
        users = config.get('users', None)

        # Expose the webroot property to be customized through the config
        # file.
        webroot = config.get('webroot', DEFAULT_WEB_ROOT)
        if webroot.endswith('/'):
            webroot = webroot[:-1]

        topic_replace_list = config.get('topic-replace-list', [])

        # Create default configuration to be used in case of problems in the
        # packaged agent configuration file.
        self.default_config = dict(
            webroot=os.path.abspath(webroot),
            users=users,
            topic_replace_list=topic_replace_list
        )

        # During the configuration update/new/delete action this will be
        # updated to the current configuration.
        self.runtime_config = None

        # Start using config store.
        self.vip.config.set_default("config", config)
        self.vip.config.subscribe(self.configure_main,
                                  actions=['NEW', 'UPDATE', 'DELETE'],
                                  pattern="config")

        # Use config store to update the settings of a platform's configuration.
        self.vip.config.subscribe(self.configure_platforms,
                                  actions=['NEW', 'UPDATE', 'DELETE'],
                                  pattern="platforms/*")

        # mapping from the real topic into the replacement.
        self.replaced_topic_map = {}

        # mapping from md5 hash of address to the actual connection to the
        # remote instance.
        self.vcp_connections = {}

        # Current sessions available to the
        self.web_sessions = None

        # Platform health based upon device driver publishes
        self.device_health = defaultdict(dict)

        # Used to hold scheduled reconnection event for vcp agents.
        self._vcp_reconnect_event = None

    def configure_main(self, config_name, action, contents):
        """
        The main configuration for volttron central.  This is where validation
        will occur.

        Note this method is called:

            1. When the agent first starts (with the params from packaged agent
               file)
            2. When 'store' is called through the volttron-ctl config command
               line with 'config' as the name.

        Required Configuration:

        The volttron central requires a user mapping.

        :param config_name:
        :param action:
        :param contents:
        """

        _log.debug('Main config updated')
        _log.debug('ACTION IS {}'.format(action))
        _log.debug('CONTENT IS {}'.format(contents))
        if action == 'DELETE':
            # Remove the registry and keep the service running.
            self.runtime_config = None
            # Now stop the exposition of service.
        else:
            self.runtime_config = self.default_config.copy()
            self.runtime_config.update(contents)

            problems = self._validate_config_params(self.runtime_config)

            if len(problems) > 0:
                _log.error(
                    "The following configuration problems were detected!")
                for p in problems:
                    _log.error(p)
                sys.exit(INVALID_CONFIGURATION_CODE)
            else:
                _log.info('volttron central webroot is: {}'.format(
                    self.runtime_config.get('webroot')
                ))

                users = self.runtime_config.get('users')
                self.web_sessions = SessionHandler(Authenticate(users))

            _log.debug('Querying router for addresses and serverkey.')
            q = Query(self.core)

            external_addresses = q.query('addresses').get(timeout=5)
            self.runtime_config['local_external_address'] = external_addresses[0]

        self.vip.web.register_websocket(r'/vc/ws', self.open_authenticate_ws_endpoint, self._ws_closed, self._ws_received)
        self.vip.web.register_endpoint(r'/jsonrpc', self.jsonrpc)
        self.vip.web.register_path(r'^/.*', self.runtime_config.get('webroot'))

        auth_file = AuthFile()
        entry = auth_file.find_by_credentials(self.core.publickey)[0]
        if 'manager' not in entry.capabilities:
            _log.debug('Adding manager capability for volttron.central to '
                       'local instance. Publickey is {}'.format(
                self.core.publickey))
            entry.add_capabilities(['manager'])
            auth_file.add(entry, True)
            gevent.sleep(0.1)

        # Keep connections in sync if necessary.
        self._periodic_reconnect_to_platforms()

    def configure_platforms(self, config_name, action, contents):
        _log.debug('Platform configuration updated.')
        _log.debug('ACTION IS {}'.format(action))
        _log.debug('CONTENT IS {}'.format(contents))

    def open_authenticate_ws_endpoint(self, fromip, endpoint):
        """
        Callback method from when websockets are opened.  The endpoine must
        be '/' delimited with the second to last section being the session
        of a logged in user to volttron central itself.

        :param fromip:
        :param endpoint:
            A string representing the endpoint of the websocket.
        :return:
        """
        _log.debug("OPENED ip: {} endpoint: {}".format(fromip, endpoint))
        try:
            session = endpoint.split('/')[-2]
        except IndexError:
            _log.error("Malformed endpoint. Must be delimited by '/'")
            _log.error(
                'Endpoint must have valid session in second to last position')
            return False

        if not self.web_sessions.check_session(session, fromip):
            _log.error("Authentication error for session!")
            return False

        _log.debug('Websocket allowed.')

        return True

    def _ws_closed(self, endpoint):
        _log.debug("CLOSED endpoint: {}".format(endpoint))

    def _ws_received(self, endpoint, message):
        _log.debug("RECEIVED endpoint: {} message: {}".format(endpoint,
                                                              message))

    @RPC.export
    def register_instance(self, address, display_name=None, vcpserverkey=None,
                          vcpagentkey=None):
        """
        RPC Method to register an instance with volttron central.

        This method is able to accommodates both a discovery address as well
        as well as a vip address.  In both cases the ports must be included in
        the uri passed to address.  A discovery address allows the lookup of
        serverkey from the address.  If instead address is an instance address
        then the serverkey and vcpagentkey is required.  If either the serverkey
        or the vcpagentkey are not specified then a ValueError is thrown.

        .. code-block:: python
            :linenos:

            # Function call using discovery address
            agent.vip.call('volttron.central', 'register_instance',
                           'http://127.0.0.1:8080', 'platform1')

            # Function call using instance address
            agent.vip.call('volttron.central', 'register_instance',
                           'tcp://127.0.0.1:22916',
                           serverkey='EOEI_TzkyzOhjHuDPWqevWAQFaGxxU_tV1qVNZqqbBI',
                           vcpagentkey='tV1qVNZqqbBIEOEI_TzkyzOhjHuDPWqevWAQFaGxxU_')

            # Function call using instance address
            agent.vip.call('volttron.central', 'register_instance',
                           'ipc://@/home/volttron/.volttron/run/vip.socket',
                           'platform1',
                           'tV1qVNZqqbBIEOEI_TzkyzOhjHuDPWqevWAQFaGxxU_')

        :param str address:
            The url of the address for the platform.
        :param str display_name:
            (Optional) How the instance is displayed on volttron central.  This
            will default to address if it is not specified.
        :param str vcpserverkey:
            (Optional) A server key for connecting from volttron central to the
            calling instance
        :param str vcpagentkey:
            (Optional) The public key associated with the vcp agent connecting
            to the volttron central instance.
        """
        _log.debug('register_instance called via RPC address: {}'.format(address))

        _log.debug('rpc context for register_instance is: {}'.format(
            self.vip.rpc.context.request)
        )
        _log.debug('rpc context for register_instance is: {}'.format(
            self.vip.rpc.context.vip_message)
        )

        parsed = urlparse(address)

        valid_schemes = ('http', 'https', 'tcp', 'ipc')
        if parsed.scheme not in valid_schemes:
            raise ValueError('Unknown scheme specified {} valid schemes are {}'
                             .format(parsed.scheme, valid_schemes))

        if parsed.scheme in ('http', 'https'):
            self._register_instance(address, parsed.scheme,
                                    display_name=display_name)
        elif parsed.scheme == 'tcp':
            if not vcpserverkey or len(vcpserverkey) != 43:  # valid publickey length
                raise ValueError(
                    "tcp addresses must have valid vcpserverkey provided")
            self.register_platform(address, parsed.scheme,  vcpserverkey,
                                   display_name)
        elif parsed.scheme == 'ipc':
            self.register_platform(address, parsed.scheme,
                                   display_name=display_name)

    def register_platform(self, address, address_type, serverkey=None,
                          display_name=None):
        """ Allows an volttron central platform (vcp) to register with vc

        @param address:
            An address or resolvable domain name with port.
        @param address_type:
            A string consisting of ipc or tcp.
        @param: serverkey: str:
            The router publickey for the vcp attempting to register.
        @param: display_name: str:
            The name to be shown in volttron central.
        """
        _log.info('Attempting registration of vcp at address: '
                  '{} display_name: {}, serverkey: {}'.format(address,
                                                              display_name,
                                                              serverkey))
        assert address_type in ('ipc', 'tcp') and address[:3] in ('ipc', 'tcp'), \
            "Invalid address_type and/or address specified."

        try:
            connection = self._build_connection(address, serverkey)
        except gevent.Timeout:
            _log.error("Initial building of connection not found")
            raise

        try:
            if address_type == 'tcp':
                self.core.publickey

                _log.debug(
                    'TCP calling manage. my publickey: {}'.format(
                        self.core.publickey))
                my_address = self.runtime_config['local_external_address']
                pk = connection.call('manage', my_address)
            else:
                pk = connection.call('manage', self.core.address)
        except gevent.Timeout:
            _log.error(
                'RPC call to manage did not return in a timely manner.')
            raise

        # If we were successful in calling manage then we can add it to
        # our list of managed platforms.
        if pk is not None and len(pk) == 43:

            md5 = hashlib.md5(address)
            address_hash = md5.hexdigest()
            config_name = "platforms/{}".format(address_hash)
            platform = None
            if config_name in self.vip.config.list():
                platform = self.vip.config.get(config_name)

            if platform:
                data = platform.copy()
                data['serverkey'] = serverkey
                data['display_name'] = display_name

            else:
                time_now = format_timestamp(get_aware_utc_now())
                data = dict(
                        address=address, serverkey=serverkey,
                        display_name=display_name,
                        registered_time_utc=time_now,
                        instance_uuid=address_hash
                    )

            data['health'] = connection.call('health.get_status')
            devices = connection.call('get_devices')
            data['devices'] = devices

            status = Status.build(UNKNOWN_STATUS,
                                  context="Not published since update")
            devices_health = {}
            for device, item in devices.items():
                device_no_prefix = device[len('devices/'):]
                devices_health[device_no_prefix] = dict(
                    last_publish_utc=None,
                    health=status.as_dict(),
                    points=item.get('points', [])
                )
            data['devices_health'] = devices_health

            self.vip.config.set(config_name, data)

            def ondevicemessage(peer, sender, bus, topic, headers, message):
                if not topic.endswith('/all'):
                    return

                # used in the devices structure.
                topic_no_all = topic[:-len('/all')]

                # Used in the devices_health structure.
                no_devices_prefix = topic_no_all[len('devices/'):]

                now_time_utc = get_aware_utc_now()
                last_publish_utc = format_timestamp(now_time_utc)

                status = Status.build(GOOD_STATUS,
                                      context="Last publish {}".format(
                                          last_publish_utc))
                try:
                    data = self.vip.config.get(config_name)
                except KeyError:
                    _log.error('Invalid configuration name: {}'.format(
                        config_name))
                    return

                cp = deepcopy(data)
                try:
                    device_health = cp['devices_health'][no_devices_prefix]
                except KeyError:
                    _log.warn('No device health for: {}'.format(no_devices_prefix))
                    device_health=dict(
                        points=cp['devices'][topic_no_all]['points'])

                # Build a dictionary to easily update the status of our device
                # health.
                update = dict(last_publish_utc=last_publish_utc,
                              health=status.as_dict())
                device_health.update(update)
                # Might need to provide protection around these three lines
                data = self.vip.config.get(config_name)
                data.update(cp)
                self.vip.config.set(config_name, cp)

            # Subscribe to the vcp instance for device publishes.
            connection.server.vip.pubsub.subscribe('pubsub', 'devices',
                                                   ondevicemessage)

    def _periodic_reconnect_to_platforms(self):
        _log.debug('Reconnecting to external platforms.')
        if self._vcp_reconnect_event is not None:
            # This won't hurt anything if we are canceling ourselves.
            self._vcp_reconnect_event.cancel()

        platforms = [x for x in self.vip.config.list()
                     if x.startswith('platforms/')]
        _log.debug('Platforms: {}'.format(platforms))
        for x in platforms:
            platform = self.vip.config.get(x)
            address = platform.get('address')
            serverkey = platform.get('serverkey')
            _log.debug('Address: {} Serverkey: {}'.format(address, serverkey))
            cn = self.vcp_connections.get(platform.get('instance_uuid'))
            if cn is not None:
                if cn.is_connected() and cn.is_peer_connected():
                    _log.debug('Platform {} already connected'.format(
                        platform.get('address')))
                    continue
                elif cn.is_connected() and not cn.is_peer_connected():
                    _log.debug("Connection available, missing peer.")
                    continue

            _log.debug('Reconnecting to: {}'.format(platform.get('address')))
            try:
                cn = self._build_connection(address, serverkey)
            except gevent.Timeout:
                _log.error("Unable to reconnect to the external instances.")
                continue

            if cn is not None and cn.is_connected() and cn.is_peer_connected():
                self.vcp_connections[x] = cn
                cn.call('manage', self.runtime_config['local_external_address'])
            else:
                _log.debug('Not connected nor managed.')

        now = get_aware_utc_now()
        next_update_time = now + datetime.timedelta(seconds=10)

        self._vcp_reconnect_event = self.core.schedule(
            next_update_time, self._periodic_reconnect_to_platforms)

    @PubSub.subscribe("pubsub", "heartbeat/platform")
    def _on_platform_heartbeat(self, peer, sender, bus, topic, headers,
                               message):

        address_hash = topic[len("heartbeat/platforms"):]
        config_name = "platforms/{}".format(address_hash)
        if config_name not in self.vip.config.list():
            _log.warn("config unrecoginized {}".format(config_name))
            _log.warn("Unrecognized platform {} sending heartbeat".format(
                address_hash
            ))
        else:
            platform = self.vip.config.get(config_name)
            platform['health'] = message

            # Because the status is only updated on the agent when it is changed
            # and we want to have the same api for health of an agent, we are
            # explicitly overwriting the last_update field of the health to
            # reflect the time passed in the header of the message.

            try:
                if platform['health']['last_updated'] == \
                        message['last_updated']:
                    if 'Date' in headers:
                        platform['health']['last_updated'] = headers['Date']
            except KeyError:
                _log.debug('Expected first time published.')

            if 'Date' in headers:
                platform['last_seen_utc'] = headers['Date']
            self.vip.config.set(config_name, platform, True)

    @PubSub.subscribe("pubsub", "platforms")
    def _on_platforms_messsage(self, peer, sender, bus, topic, headers,
                               message):
        """ Callback function for vcp agent to publish to.

        Platforms that are being managed should publish to this topic with
        the agent_list and other interesting things that the volttron
        central shsould want to know.
        """
        topicsplit = topic.split('/')
        if len(topicsplit) < 2:
            _log.error('Invalid topic length published to volttron central')
            return

        # Topic is platforms/<platform_uuid>/otherdata
        topicsplit = topic.split('/')

        if len(topicsplit) < 3:
            _log.warn("Invalid topic length no operation or datatype.")
            return

        _, platform_uuid, op_or_datatype, other = topicsplit[0], \
                                                  topicsplit[1], \
                                                  topicsplit[2], topicsplit[3:]

        _log.warn(platform_uuid)
        _log.warn(op_or_datatype)
        _log.warn(other)
        if op_or_datatype in ('iam', 'configure'):
            if not other:
                _log.error("Invalid response to iam or configure endpoint")
                _log.error(
                    "the sesson token was not included in response from vcp.")
                return

            ws_endpoint = "/vc/ws/{}/{}".format(other[0], op_or_datatype)
            _log.debug('SENDING MESSAGE TO {}'.format(ws_endpoint))
            self.vip.web.send(ws_endpoint, jsonapi.dumps(message))

        # platform = self._registered_platforms.get(platform_uuid)
        # if platform is None:
        #     _log.warn('Platform {} is not registered but sent message {}'
        #               .format(platform_uuid, message))
        #     return
        #
        # _log.debug('Doing operation: {}'.format(op_or_datatype))
        # _log.debug('Topic was: {}'.format(topic))
        # _log.debug('Message was: {}'.format(message))
        #
        # if op_or_datatype == 'devices':
        #     md5hash = message.get('md5hash')
        #     if md5hash is None:
        #         _log.error('Invalid topic for devices datatype.  Must contain '
        #                    'md5hash in message.')
        #     if message['md5hash'] not in self._hash_to_topic:
        #         devices = platform.get("devices", {})
        #         lookup_topic = '/'.join(other)
        #         _log.debug("Lookup topic is: {}".format(lookup_topic))
        #         vcp = self._get_connection(platform_uuid)
        #         device_node = vcp.call("get_device", lookup_topic)
        #         if device_node is not None:
        #             devices[lookup_topic] = device_node
        #             self._hash_to_topic[md5hash] = lookup_topic
        #         else:
        #             _log.error("Couldn't retrive device topic {} from platform "
        #                        "{}".format(lookup_topic, platform_uuid))
        # elif op_or_datatype in ('iam', 'configure'):
        #     ws_endpoint = "/vc/ws/{}".format(op_or_datatype)
        #     self.vip.web.send(ws_endpoint, jsonapi.dumps(message))

    @PubSub.subscribe("pubsub", "datalogger/platforms")
    def _on_platform_log_message(self, peer, sender, bus, topic, headers,
                                 message):
        """ Receive message from a registered platform

        This method is called with stats from the registered platform agents.

        """
        _log.debug('Got datalogger/platforms message (topic): {}'.format(topic))
        _log.debug('Got datalogger/platforms message (message): {}'.format(
            message))

        topicsplit = topic.split('/')
        platform_hash = topicsplit[2]
        config_name = "platforms/{}".format(platform_hash)

        # For devices we use everything between devices/../all as a unique
        # key for determining the last time it was seen.
        key = '/'.join(topicsplit[:])
        uuid = topicsplit[2]

        point_list = []

        for point, item in message.iteritems():
            point_list.append(point)

        stats = {
            'topic': key,
            'points': point_list,
            'last_published_utc': format_timestamp(get_aware_utc_now())
        }

        platform = self.vip.config.get(config_name)
        platform['stats_point_list'] = stats
        self.vip.config.set(config_name, platform)

    # @RPC.export
    # def get_platforms(self):
    #     """ Retrieves the platforms that have been registered with VC.
    #
    #     @return:
    #     """
    #
    #     _log.debug("Passing platforms back: {}".format(
    #         self._registered_platforms.keys()))
    #     return self._registered_platforms.values()
    #
    # @RPC.export
    # def get_platform(self, platform_uuid):
    #     platform = self._registered_platforms.get(platform_uuid)
    #     if platform is not None:
    #         platform = deepcopy(platform)
    #
    #     return platform

    @RPC.export
    def get_publickey(self):
        """
        RPC method allowing the caller to retrieve the publickey of this agent.

        This method is available for allowing :class:`VolttronCentralPlatform`
        agents to allow this agent to be able to connect to its instance.

        :return: The publickey of this volttron central agent.
        :rtype: str
        """
        return self.core.publickey

    @RPC.export
    def unregister_platform(self, platform_uuid):
        _log.debug('unregister_platform')

        platform = self._registered_platforms.get(platform_uuid)
        if platform:
            connected = self._platform_connections.get(platform_uuid)
            if connected is not None:
                connected.call('unmanage')
                connected.kill()
            address = None
            for v in self._address_to_uuid.values():
                if v == platform_uuid:
                    address = v
                    break
            if address:
                del self._address_to_uuid[address]
            del self._platform_connections[platform_uuid]
            del self._registered_platforms[platform_uuid]
            self._registered_platforms.sync()
            context = 'Unregistered platform {}'.format(platform_uuid)
            return {'status': 'SUCCESS', 'context': context}
        else:
            msg = 'Unable to unregistered platform {}'.format(platform_uuid)
            return {'error': {'code': UNABLE_TO_UNREGISTER_INSTANCE,
                              'message': msg}}

    def _build_connected_agent(self, address):
        _log.debug('Building or returning connection to address: {}'.format(
            address))

        cn_uuid = self._address_to_uuid.get(address)
        if not cn_uuid:
            raise ValueError("Can't connect to address: {}".format(
                address
            ))

        cn = self._platform_connections.get(cn_uuid)
        if cn is not None:
            if not cn.is_connected():
                cn.kill()
                cn = None

        if cn is None:
            entry = self._registered_platforms.get(cn_uuid)
            entry or _log.debug('Platform registry is empty for uuid {}'
                                .format(cn_uuid))
            assert entry

            cn = Connection(address, peer=VOLTTRON_CENTRAL_PLATFORM,
                            serverkey=entry['serverkey'],
                            secretkey=self.core.secretkey,
                            publickey=self.core.publickey)

            self._platform_connections[cn_uuid] = cn
        return cn

    def _build_connection(self, address, serverkey=None):
        """ Creates a Connection object instance if one doesn't exist for the
        passed address.

        :param address:
        :param serverkey:
        :return:
        """

        address_hash = hashlib.md5(address).hexdigest()

        cn = self.vcp_connections.get(address_hash)

        if cn is None:
            cn = Connection(address=address, serverkey=serverkey,
                            publickey=self.core.publickey,
                            secretkey=self.core.secretkey,
                            peer=VOLTTRON_CENTRAL_PLATFORM)
            _log.debug('Connection established for publickey: {}'.format(
                self.core.publickey))

        assert cn.is_connected(), "Connection unavailable for address {}"\
            .format(address)

        self.vcp_connections[address_hash] = cn
        return cn

    def _get_connection(self, platform_hash):
        cn = self.vcp_connections.get(platform_hash)

        if cn is None:
            raise ValueError('Invalid platform_hash specified {}'
                             .format(platform_hash))
        #
        # if cn is None:
        #     if self._registered_platforms.get(platform_hash) is None:
        #         raise ValueError('Invalid platform_hash specified {}'
        #                          .format(platform_hash))
        #
        #     cn = self._build_connected_agent(
        #         self._registered_platforms[platform_hash]['address']
        #     )
        #
        #     self._platform_connections[platform_hash] = cn

        return cn

    def _handle_list_platforms(self):

        platform_configs = [x for x in self.vip.config.list()
                            if x.startswith('platforms/')]

        results = []

        platform_keys = (('uuid', 'instance_uuid'),
                         ('name', 'display_name'),
                         ('health', 'health'))

        for x in platform_configs:
            config = self.vip.config.get(x)

            obj = dict()
            for k in platform_keys:
                obj[k[0]] = config.get(k[1])
            results.append(obj)

        return results

    def _register_instance(self, discovery_address, display_name=None):
        """ Register an instance with VOLTTRON Central based on jsonrpc.

        NOTE: This method is meant to be called from the jsonrpc method.

        The registration of the instance will fail in the following cases:
        - no discoverable instance at the passed uri
        - no platform.agent installed at the discoverable instance
        - is a different volttron central managing the discoverable
          instance.

        If the display name is not set then the display name becomes the
        same as the discovery_address.  This will be used in the
        volttron central ui.

        :param discovery_address: A ip:port for an instance of volttron
               discovery.
        :param display_name:
        :return: dictionary:
            The dictionary will hold either an error object or a result
            object.
        """

        _log.info(
            'Attempting to register name: {} with address: {}'.format(
                display_name, discovery_address))

        try:
            discovery_response = DiscoveryInfo.request_discovery_info(
                discovery_address)
        except DiscoveryError as e:
            return {
                'error': {
                    'code': DISCOVERY_ERROR, 'message': e.message
                }}

        pa_instance_serverkey = discovery_response.serverkey
        pa_vip_address = discovery_response.vip_address

        assert pa_instance_serverkey
        assert pa_vip_address

        self.register_platform(pa_vip_address, pa_instance_serverkey)

        if pa_vip_address not in self._address_to_uuid.keys():
            return {'status': 'FAILURE',
                    'context': "Couldn't register address: {}".format(
                        pa_vip_address)}

        return {'status': 'SUCCESS',
                'context': 'Registered instance {}'.format(display_name)}

    def _store_registry(self):
        self._store('registry', self._registry.package())

    def _to_jsonrpc_obj(self, jsonrpcstr):
        """ Convert data string into a JsonRpcData named tuple.

        :param object data: Either a string or a dictionary representing a json document.
        """
        return jsonrpc.JsonRpcData.parse(jsonrpcstr)

    def jsonrpc(self, env, data):
        """ The main entry point for ^jsonrpc data

        This method will only accept rpcdata.  The first time this method
        is called, per session, it must be using get_authorization.  That
        will return a session token that must be included in every
        subsequent request.  The session is tied to the ip address
        of the caller.

        :param object env: Environment dictionary for the request.
        :param object data: The JSON-RPC 2.0 method to call.
        :return object: An JSON-RPC 2.0 response.
        """
        if env['REQUEST_METHOD'].upper() != 'POST':
            return jsonrpc.json_error('NA', INVALID_REQUEST,
                                      'Invalid request method, only POST allowd'
                                      )

        try:
            rpcdata = self._to_jsonrpc_obj(data)
            _log.info('rpc method: {}'.format(rpcdata.method))
            if rpcdata.method == 'get_authorization':
                args = {'username': rpcdata.params['username'],
                        'password': rpcdata.params['password'],
                        'ip': env['REMOTE_ADDR']}
                sess = self.web_sessions.authenticate(**args)
                if not sess:
                    _log.info('Invalid username/password for {}'.format(
                        rpcdata.params['username']))
                    return jsonrpc.json_error(
                        rpcdata.id, UNAUTHORIZED,
                        "Invalid username/password specified.")
                _log.info('Session created for {}'.format(
                    rpcdata.params['username']))
                return jsonrpc.json_result(rpcdata.id, sess)

            token = rpcdata.authorization
            ip = env['REMOTE_ADDR']
            _log.debug('REMOTE_ADDR: {}'.format(ip))
            session_user = self.web_sessions.check_session(token, ip)
            _log.debug('SESSION_USER IS: {}'.format(session_user))
            if not session_user:
                _log.debug("Session Check Failed for Token: {}".format(token))
                return jsonrpc.json_error(rpcdata.id, UNAUTHORIZED,
                                          "Invalid authentication token")
            _log.debug('RPC METHOD IS: {}'.format(rpcdata.method))

            # Route any other method that isn't
            result_or_error = self._route_request(session_user,
                                                  rpcdata.id, rpcdata.method,
                                                  rpcdata.params)

        except AssertionError:
            return jsonrpc.json_error(
                'NA', INVALID_REQUEST, 'Invalid rpc data {}'.format(data))
        except Unreachable:
            return jsonrpc.json_error(
                rpcdata.id, UNAVAILABLE_PLATFORM,
                "Couldn't reach platform with method {} params: {}"
                .format(rpcdata.method, rpcdata.params)
            )
        except Exception as e:

            return jsonrpc.json_error(
                'NA', UNHANDLED_EXCEPTION, e
            )

        _log.debug("RETURNING: {}".format(self._get_jsonrpc_response(
            rpcdata.id, result_or_error)))
        return self._get_jsonrpc_response(rpcdata.id, result_or_error)

    def _get_jsonrpc_response(self, id, result_or_error):
        """ Wrap the response in either a json-rpc error or result.

        :param id:
        :param result_or_error:
        :return:
        """
        if result_or_error is not None:
            if 'error' in result_or_error:
                error = result_or_error['error']
                _log.debug("RPC RESPONSE ERROR: {}".format(error))
                return jsonrpc.json_error(id, error['code'], error['message'])
        return jsonrpc.json_result(id, result_or_error)

    def _get_agents(self, instance_uuid, groups):
        """ Retrieve the list of agents on a specific platform.

        :param instance_uuid:
        :param groups:
        :return:
        """
        _log.debug('_get_agents')
        connected_to_pa = self._platform_connections[instance_uuid]

        agents = connected_to_pa.agent.vip.rpc.call(
            'platform.agent', 'list_agents').get(timeout=30)

        for a in agents:
            if 'admin' in groups:
                if "platformagent" in a['name'] or \
                                "volttroncentral" in a['name']:
                    a['vc_can_start'] = False
                    a['vc_can_stop'] = False
                    a['vc_can_restart'] = True
                else:
                    a['vc_can_start'] = True
                    a['vc_can_stop'] = True
                    a['vc_can_restart'] = True
            else:
                # Handle the permissions that are not admin.
                a['vc_can_start'] = False
                a['vc_can_stop'] = False
                a['vc_can_restart'] = False

        _log.debug('Agents returned: {}'.format(agents))
        return agents

    def _setupexternal(self):
        _log.debug(self.vip.ping('', "PING ROUTER?").get(timeout=3))

    def _configure_agent(self, endpoint, message):
        _log.debug('Configure agent: {} message: {}'.format(endpoint, message))

    def _received_data(self, endpoint, message):
        print('Received from endpoint {} message: {}'.format(endpoint, message))
        self.vip.web.send(endpoint, message)

    @Core.receiver('onstop')
    def onstop(self, sender, **kwargs):
        """ Clean up the  agent code before the agent is killed
        """
        pass
        # for v in self._platform_connections.values():
        #     try:
        #         if v is not None:
        #             v.kill()
        #     except AttributeError:
        #         pass
        #
        # self._platform_connections.clear()
        #
        # self.vip.rpc.call(MASTER_WEB, 'unregister_all_agent_routes',
        #                   self.core.identity).get(timeout=30)

    # #@Core.periodic(10)
    # def _update_device_registry(self):
    #     """ Updating the device registery from registered platforms.
    #
    #     :return:
    #     """
    #     try:
    #         if not self._flag_updating_deviceregistry:
    #             _log.debug("Updating device registry")
    #             self._flag_updating_deviceregistry = True
    #             self._sync_connected_platforms()
    #             unreachable = []
    #             # Loop over the connections to the registered agent platforms.
    #             for k, v in self._platform_connections.items():
    #                 _log.debug('updating for {}'.format(k))
    #                 # Only attempt update if we have a connection to the
    #                 # agent instance.
    #                 if v is not None:
    #                     try:
    #                         devices = v.agent.vip.rpc.call(
    #                             VOLTTRON_CENTRAL_PLATFORM,
    #                             'get_devices').get(timeout=30)
    #
    #                         anon_devices = defaultdict(dict)
    #
    #                         # for each device returned from the query to
    #                         # get_devices we need to anonymize the k1 in the
    #                         # anon_devices dictionary.
    #                         for k1, v1 in devices.items():
    #                             _log.debug(
    #                                 "before anon: {}, {}".format(k1, v1))
    #                             # now we need to do a search/replace on the
    #                             # self._topic_list so that the devices are
    #                             # known as the correct itme nin the tree.
    #                             anon_topic = self._topic_replace_map[k1]
    #
    #                             # if replaced has not already been replaced
    #                             if not anon_topic:
    #                                 anon_topic = k1
    #                                 for sr in self._topic_replace_list:
    #                                     anon_topic = anon_topic.replace(
    #                                         sr['from'], sr['to'])
    #
    #                                 self._topic_replace_map[k1] = anon_topic
    #
    #                             anon_devices[anon_topic] = v1
    #
    #                         _log.debug('Anon devices are: {}'.format(
    #                             anon_devices))
    #
    #                         self._registry.update_devices(k, anon_devices)
    #                     except (gevent.Timeout, Unreachable) as e:
    #                         _log.error(
    #                             'Error getting devices from platform {}'
    #                                 .format(k))
    #                         unreachable.append(k)
    #             for k in unreachable:
    #                 if self._platform_connections[k]:
    #                     self._platform_connections[k].disconnect()
    #                 del self._platform_connections[k]
    #
    #     finally:
    #         self._flag_updating_deviceregistry = False

    def _handle_list_performance(self):
        _log.debug('Listing performance topics from vc')

        config_list = [x for x in self.vip.config.list()
                       if x.startswith('platforms/')]
        _log.debug("Registered platforms: {}".format(config_list))

        performances = []
        for x in config_list:
            platform = self.vip.config.get(x)
            performances.append(
                {
                    'platform.uuid': platform['instance_uuid'],
                    'performance': platform.get('stats_point_list', {})
                }
            )
        return performances

    def _handle_get_devices(self, platform_uuid):
        _log.debug('handling get_devices platform: {}'.format(platform_uuid))

        try:
            platform = self.vip.config.get('platforms/{}'.format(platform_uuid))
            return platform['devices_health'].copy()
        except KeyError:
            _log.warn('Unknown platform platform_uuid specified! {}'.format(platform_uuid))

    def _handle_bacnet_props(self, session_user, platform_uuid, params):
        _log.debug('Handling bacnet_props platform: {}'.format(platform_uuid))

        configure_topic = "{}/configure".format(session_user['token'])
        ws_socket_topic = "/vc/ws/{}".format(configure_topic)
        self.vip.web.register_websocket(ws_socket_topic,
                                        self.open_authenticate_ws_endpoint,
                                        self._ws_closed, self._ws_received)

        def start_sending_props():
            response_topic = "configure/{}".format(session_user['token'])
            # Two ways we could have handled this is to pop the identity off
            # of the params and then passed both the identity and the response
            # topic.  Or what I chose to do and to put the argument in a
            # copy of the params.
            cp = params.copy()
            cp['publish_topic'] = response_topic
            cp['device_id'] = int(cp['device_id'])
            vcp_conn = self._get_connection(platform_uuid)
            _log.debug('PARAMS: {}'.format(cp))
            vcp_conn.call("publish_bacnet_props", **cp)

        gevent.spawn_later(3, start_sending_props)

    def _handle_bacnet_scan(self, session_user, platform_uuid, params):
        _log.debug('Handling bacnet_scan platform: {}'.format(platform_uuid))

        scan_length = params.pop('scan_length', 5)

        try:
            scan_length = float(scan_length)
            params['scan_length'] = scan_length
            vcp_conn = self._get_connection(platform_uuid)
            iam_topic = "{}/iam".format(session_user['token'])
            ws_socket_topic = "/vc/ws/{}".format(iam_topic)
            self.vip.web.register_websocket(ws_socket_topic,
                                            self.open_authenticate_ws_endpoint,
                                            self._ws_closed, self._ws_received)

            def start_scan():
                # We want the datatype (iam) to be second in the response so
                # we need to reposition the iam and the session id to the topic
                # that is passed to the rpc function on vcp
                iam_session_topic = "iam/{}".format(session_user['token'])
                vcp_conn.call("start_bacnet_scan", iam_session_topic, **params)

                def close_socket():
                    _log.debug('Closing bacnet scan for {}'.format(platform_uuid))
                    self.vip.web.unregister_websocket(ws_socket_topic)

                gevent.spawn_later(scan_length, close_socket)
            # By starting the scan a couple seconds later we allow the websockt
            # client to subscribe to the newly available endpoint.
            gevent.spawn_later(3, start_scan)
        except ValueError:
            return jsonrpc.json_error(id, UNAVAILABLE_PLATFORM,
                                      "Couldn't connect to platform {}".format(
                                          platform_uuid
                                      ))
        except KeyError:
            return jsonrpc.json_error(id, UNAUTHORIZED,
                                      "Invalid user session token")

    def _handle_store_agent_config(self, req_args, params):
        required = ('agent_identity', 'config_name', 'raw_contents')
        errors = []
        for r in required:
            if r not in params:
                errors.append('Missing {}'.format(r))
        config_type = params.get('config_type', None)
        if config_type:
            if config_type not in ('raw', 'json', 'csv'):
                errors.append('Invalid config_type parameter')

        if errors:
            return jsonrpc.json_error(req_args.id, INVALID_PARAMS,
                                      "\n".join(errors))
        vcp_conn = self._get_connection(req_args.platform_uuid)
        vcp_conn.call("store_agent_config", **params)

    def _handle_get_agent_config(self, req_args, params):
        vcp_conn = self._get_connection(req_args.platform_uuid)
        return vcp_conn.call("get_agent_config", **params)

    def _handle_list_agent_configs(self, req_args, params):
        vcp_conn = self._get_connection(req_args.platform_uuid)
        return vcp_conn.call("list_agent_configs", **params)

    def _route_request(self, session_user, id, method, params):
        """ Handle the methods volttron central can or pass off to platforms.

        :param session_user:
            The authenticated user's session info.
        :param id:
            JSON-RPC id field.
        :param method:
        :param params:
        :return:
        """
        _log.debug(
            'inside _route_request {}, {}, {}'.format(id, method, params))

        def err(message, code=METHOD_NOT_FOUND):
            return {'error': {'code': code, 'message': message}}

        platform_methods = dict(
            start_bacnet_scan=self._handle_bacnet_scan,
            publish_bacnet_props=self._handle_bacnet_props,
            store_agent_config=self._handle_store_agent_config,
            get_agent_config=self._handle_get_agent_config,
            list_agent_configs=self._handle_list_agent_configs
        )

        if method in platform_methods:
            platform_uuid = params.pop('platform_uuid', None)
            if not platform_uuid:
                return err("Invalid platform_uuid specified as parameter",
                           INVALID_PARAMS)
            try:
                cn = self._get_connection(platform_uuid)
                if not cn.is_connected:
                    return jsonrpc.json_error(id, UNAVAILABLE_PLATFORM,
                                              "Couldn't connect to platform "
                                              "{}".format(platform_uuid))

            except ValueError:
                return jsonrpc.json_error(id, UNAVAILABLE_PLATFORM,
                                          "Couldn't connect to platform "
                                          "{}".format(platform_uuid))

            # No matter what else, we are going to need to pass the session
            # and the platform we are talking to.  The methods may not use
            # both, but they are available if we need to extend this to
            # more arguments.
            req_args = RequiredArgs(id, session_user, platform_uuid)

            return platform_methods[method](req_args, params)

        if method == 'open_websockets':
            token = session_user['token']

            websockets = [
                ('/vc/ws/{}/configure', self._configure)
                #\('/vc/ws/{}/iam', self._w)
                # ('/vc/ws/{}/platforms', self._platform_update) #,
                # ('/vc/ws/{}/iam', self._i)
            ]

            routes = [x[0] for x in websockets]

            for x in websockets:
                self.vip.web.register_websocket(x[0], x[1])

            return jsonrpc.json_result(id, routes)

        if method.endswith('get_devices'):
            _, _, platform_uuid, _ = method.split('.')
            return self._handle_get_devices(platform_uuid)


        method_dict = {
            'list_platforms': self._handle_list_platforms,
            'list_performance': self._handle_list_performance
        }

        if method in method_dict.keys():
            return method_dict[method]()

        if method == 'register_instance':
            if isinstance(params, list):
                return self._register_instance(*params)
            else:
                return self._register_instance(**params)
        elif method == 'unregister_platform':
            return self.unregister_platform(params['instance_uuid'])
        elif method == 'get_setting':
            if 'key' not in params or not params['key']:
                return err('Invalid parameter key not set',
                           INVALID_PARAMS)
            setting_key = "setting/{}".format(params['key'])
            value = self.vip.config.get(setting_key)
            if value is None:
                return err('Invalid key specified', INVALID_PARAMS)
            return value
        elif method == 'get_setting_keys':
            keys = [x[8:] for x in self.vip.config.list()
                    if x.startswith("setting/")]
            return keys
        elif method == 'set_setting':
            if 'key' not in params or not params['key']:
                return err('Invalid parameter key not set',
                           INVALID_PARAMS)
            _log.debug('VALUE: {}'.format(params))
            if 'value' not in params:
                return err('Invalid parameter value not set',
                           INVALID_PARAMS)

            setting_key = "setting/{}".format(params['key'])

            # if passing None value then remove the value from the keystore
            # don't raise an error if the key isn't present in the store.
            if params['value'] is None:
                self.vip.config.delete(setting_key)
            else:
                self.vip.config.set(setting_key, params['value'])
            return 'SUCCESS'
        elif 'historian' in method:
            has_platform_historian = PLATFORM_HISTORIAN in \
                                     self.vip.peerlist().get(timeout=30)
            if not has_platform_historian:
                return err('The VOLTTRON Central platform historian is unavailable.',
                           UNAVAILABLE_AGENT)
            _log.debug('Trapping platform.historian to vc.')
            _log.debug('has_platform_historian: {}'.format(
                has_platform_historian))
            if 'historian.query' in method:
                return self.vip.rpc.call(
                    PLATFORM_HISTORIAN, 'query', **params).get(timeout=30)
            elif 'historian.get_topic_list' in method:
                return self.vip.rpc.call(
                    PLATFORM_HISTORIAN, 'get_topic_list').get(timeout=30)

        fields = method.split('.')
        if len(fields) < 3:
            return err('Unknown method {}'.format(method))
        instance_uuid = fields[2]
        _log.debug('Instance uuid is: {}'.format(instance_uuid))
        cn = self.vcp_connections.get(instance_uuid)
        if not cn:
            return err('Unknown platform {}'.format(instance_uuid))
        platform_method = '.'.join(fields[3:])
        _log.debug("Platform method is: {}".format(platform_method))
        if not cn:
            return jsonrpc.json_error(id,
                                      UNAVAILABLE_PLATFORM,
                                      "cannot connect to platform."
                                      )
        _log.debug('Routing to {}'.format(VOLTTRON_CENTRAL_PLATFORM))

        if platform_method == 'install':
            if 'admin' not in session_user['groups']:
                return jsonrpc.json_error(
                    id, UNAUTHORIZED,
                    "Admin access is required to install agents")

        if platform_method == 'list_agents':
            _log.debug('Callling list_agents')
            agents = cn.call('list_agents')

            if agents is None:
                _log.warn('No agents found for instance_uuid {}'.format(
                    instance_uuid
                ))
                agents = []

            for a in agents:
                if 'admin' not in session_user['groups']:
                    a['permissions'] = {
                        'can_stop': False,
                        'can_start': False,
                        'can_restart': False,
                        'can_remove': False
                    }
                else:
                    _log.debug('Permissionse for {} are {}'
                               .format(a['name'], a['permissions']))
            return agents
        else:
            try:
                _log.debug('Routing request {} {} {}'.format(id, platform_method, params))
                return cn.call('route_request', id, platform_method, params)
            except (Unreachable, gevent.Timeout) as e:
                del self._platform_connections[instance_uuid]
                return err("Can't route to platform",
                           UNAVAILABLE_PLATFORM)

    def _validate_config_params(self, config):
        """
        Validate the configuration parameters of the default/updated parameters.

        This method will return a list of "problems" with the configuration.
        If there are no problems then an empty list is returned.

        :param config: Configuration parameters for the volttron central agent.
        :type config: dict
        :return: The problems if any, [] if no problems
        :rtype: list
        """
        problems = []
        webroot = config.get('webroot')
        if not webroot:
            problems.append('Invalid webroot in configuration.')
        elif not os.path.exists(webroot):
            problems.append(
                'Webroot {} does not exist on machine'.format(webroot))

        users = config.get('users')
        if not users:
            problems.append('A users node must be specified!')
        else:
            has_admin = False

            try:
                for user, item in users.items():
                    if 'password' not in item.keys():
                        problems.append('user {} must have a password!'.format(
                            user))
                    elif not item['password']:
                        problems.append('password for {} is blank!'.format(
                            user
                        ))

                    if 'groups' not in item.keys():
                        problems.append('missing groups key for user {}'.format(
                            user
                        ))
                    elif not isinstance(item['groups'], list):
                        problems.append('groups must be a list of strings.')
                    elif not item['groups']:
                        problems.append(
                            'user {} must belong to at least one group.'.format(
                                user))

                    # See if there is an adminstator present.
                    if not has_admin and isinstance(item['groups'], list):
                        has_admin = 'admin' in item['groups']
            except AttributeError:
                problems.append('invalid user node.')

            if not has_admin:
                problems.append("One user must be in the admin group.")

        return problems


def main(argv=sys.argv):
    """ Main method called by the eggsecutable.
    :param argv:
    :return:
    """
    utils.vip_main(VolttronCentralAgent, identity=VOLTTRON_CENTRAL)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
