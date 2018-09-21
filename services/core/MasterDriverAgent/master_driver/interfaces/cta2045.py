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

from csv import DictReader
from datetime import datetime
import json
import logging
import requests
import paho.mqtt.client as mqtt

from master_driver.interfaces import (BaseInterface,
                                      BaseRegister,
                                      BasicRevert,
                                      DriverInterfaceError)

_log = logging.getLogger(__name__)


def get_value(data, key, value = -1):
    return data[key] if key in data else value


def parse_temperature(d):
    return (65536 - d) * (-1.0) if d & (1 << 15) else d


def parse_data(data):
    x = dict()

    d = bytearray.fromhex(data['d'])
    if 1 <= len(d):
        x['override'] = 1 if d[0] & 0x80 else 0

        i = 1
        while i < len(d) - 1:
            m = (d[i] << 8) | d[i + 1]
            s = (d[i + 2] << 8) | d[i + 3]
            if 0 < s and i + 4 + s <= len(d):
                c = (d[i + 4] << 8) | (d[i + 5] & 0x7f)
                if 0x1300 <= c and 0x130c >= c:
                    x['state'] = d[i + 5] & 0x7f
                elif 0x0600 == c:
                    n = [
                        'Electricity Consumed',
                        'Electricity Produced',
                        'Natural gas',
                        'Water',
                        'Natural gas',
                        'Water',
                        'Total Energy Storage Capacity',
                        'Present Energy Storage Capacity'
                    ]

                    u = [
                        'W & W-hr',
                        'W & W-hr',
                        'cu-ft/hr & cu-ft',
                        'Gal/hr & Gallons',
                        'cubic meters/hour (m3) & & cubic meters (m3)',
                        'liters/hr & liters',
                        'W & W-hr',
                        'W & W-hr'
                    ]

                    x['commodities'] = []

                    j = i + 7
                    while j <= (i + 7 + (s - 3)) - 13:
                        x['commodities'].append({
                            'code': d[j] & 0x7f,
                            'name': n[d[j] & 0x7f],
                            'units': u[d[j] & 0x7f],
                            'estimated': 1 if d[j] & 0x80 else 0,
                            'instantaneous': (d[j + 1] << 0x28) | (d[j + 2] << 0x20) | (d[j + 3] << 0x18) | (d[j + 4] << 0x10) | (d[j + 5] << 0x08) | (d[j + 6]),
                            'cumulative': (d[j + 7] << 0x28) | (d[j + 8] << 0x20) | (d[j + 9] << 0x18) | (d[j + 10] << 0x10) | (d[j + 11] << 0x08) | (d[j + 12])
                        })
                        j += 13
                elif 0x0302 == c:
                    if 0 == d[i + 6]:
                        x['offset'] = {
                            'data': d[i + 7],
                            'units': d[i + 8]
                        }
                elif 0x0303 == c:
                    if 8 <= s:
                        x['setpoint'] = {
                            'type': ([i + 7] << 8) | d[i + 8],
                            'units': d[i + 9],
                            'data': [parse_temperature((d[i + 10] << 8) | d[i + 11])]
                        }
                    if 10 <= s:
                        x['setpoint']['data'].append(parse_temperature((d[i + 12] << 8) | d[i + 13]))
                elif 0x0304 == c:
                    if 0 == d[i + 6] and 8 <= s:
                        x['temperature'] = {
                            'data': [(d[i + 10] << 8) | d[i + 11]],
                            'units': d[i + 9],
                            'device': (d[i + 7] << 8) | d[i + 8]
                        }
                elif 0x0701 == c:
                    if 0 == d[i + 6] and 4 <= s:
                        x['thermostat_mode'] = d[i + 7]
                elif 0x0702 == c:
                    if 0 == d[i + 6] and 4 <= s:
                        x['fan_mode'] = d[i + 7]
                elif 0xfe00 == c:
                    pass

            i += (s + 4)

    return x


def get_sgd_value(data, key, value = 0):
    return data[key] if key in data else value


def parse_sgd_data(data):
    return {}


class NetworkStatus(BaseRegister):
    def __init__(self):
        super(NetworkStatus, self).__init__('byte', True, 'NetworkStatus', 'string')

    def value(self, data):
#        dt = datetime.strptime(data['time'], '%Y-%m-%d %H:%M:%S%Z')
#        # Assume the device is offline if the HB more than 3 minutes old.
#        if (datetime.now() - dt).total_seconds() > 180:
#            return 'Offline'

        return 'Connected'


class DeviceType(BaseRegister):
    def __init__(self):
        super(DeviceType, self).__init__('byte', True, 'DeviceType', 'int')

    def value(self, data):
        # 0x0000 designates an Unspecified Type
        return get_sgd_value(data, 'device_type')


class DeviceVendorId(BaseRegister):
    def __init__(self):
        super(DeviceVendorId, self).__init__('byte', True, 'DeviceVendorId', 'string')

    def value(self, data):
        return get_sgd_value(data, 'vendor_id', 'N/A')


class OperationalState(BaseRegister):
    state_desc = [
        'Idle Normal',
        'Running Normal',
        'Running Curtailed',
        'Running Heightened',
        'Idle Curtailed',
        'SGD Error Condition',
        'Idle Heightened',
        'Cycling On',
        'Cycling Off',
        'Variable Following',
        'Variable Not Following',
        'Idle Opted Out',
        'Running Opted Out'
    ]

    def __init__(self):
        super(OperationalState, self).__init__('byte', True, 'OperationalState', 'int')

    def value(self, data):
        return get_value(data, 'state')


class CustomerOverride(BaseRegister):
    def __init__(self):
        super(CustomerOverride, self).__init__('byte', True, 'CustomerOverride', 'int')

    def value(self, data):
        return get_value(data, 'override')


def get_commodity(data, code):
    commodity = None
    if 'commodities' in data:
        for x in data['commodities']:
            if code == x['code']:
                commodity = x

    return commodity


class CommodityCode(object):
    ElectricityConsumed = 0
    ElectricityProduced = 1
    TotalStorageCapacity = 6
    PresentStorageCapacity = 7


class InstantaneousElectricityConsumption(BaseRegister):
    def __init__(self):
        super(InstantaneousElectricityConsumption, self).__init__('byte', True, 'InstantaneousElectricityConsumption', 'int')

    def value(self, data):
        commodity = get_commodity(data, CommodityCode.ElectricityConsumed)
        return commodity['instantaneous'] if commodity else -1


class CumulativeElectricityConsumption(BaseRegister):
    def __init__(self):
        super(CumulativeElectricityConsumption, self).__init__('byte', True, 'CumulativeElectricityConsumption', 'int')

    def value(self, data):
        commodity = get_commodity(data, CommodityCode.ElectricityConsumed)
        return commodity['cumulative'] if commodity else -1


class TotalEnergyStorageCapacity(BaseRegister):
    def __init__(self):
        super(TotalEnergyStorageCapacity, self).__init__('byte', True, 'TotalEnergyStorageCapacity', 'int')

    def value(self, data):
        commodity = get_commodity(data, CommodityCode.TotalStorageCapacity)
        return commodity['cumulative'] if commodity else -1


class PresentEnergyStorageCapacity(BaseRegister):
    def __init__(self):
        super(PresentEnergyStorageCapacity, self).__init__('byte', True, 'PresentEnergyStorageCapacity', 'int')

    def value(self, data):
        commodity = get_commodity(data, CommodityCode.PresentStorageCapacity)
        return commodity['cumulative'] if commodity else -1


class PresentTemperature(BaseRegister):
    def __init__(self):
        super(PresentTemperature, self).__init__('byte', True, 'PresentTemperature', 'int')

    def value(self, data):
        return data['temperature'][0] if 'temperature' in data else -1


class TemperatureOffset(BaseRegister):
    def __init__(self):
        super(TemperatureOffset, self).__init__('byte', False, 'TemperatureOffset', 'int')
        self._value = -1
        self._timestamp = datetime.now()

    def value(self, data):
        self._value = data['offset']['data'] if 'offset' in data else -1
        self._timestamp = datetime.now()
        return self._value

    def set_value(self, x, client, mac):
        try:
            self._value = self.data_type(x)
            client.publish('devices/{0}/ctl/offset'.format(mac),
                '{"d":"{0}"}'.format(self._value))
        except Exception as ex:
            _log.critical('Could not set value of {0}'.format(self.point_name))
            self._value = x
        self._timestamp = datetime.now()
        return self._value


class HeatTemperatureSetPoint(BaseRegister):
    def __init__(self):
        super(HeatTemperatureSetPoint, self).__init__('byte', False, 'HeatTemperatureSetPoint', 'int')
        self._value = -1
        self._timestamp = datetime.now()

    @property
    def value(self, data):
        self._value = data['setpoint']['data'][0] if 'setpoint' in data else -1
        self._timestamp = datetime.now()
        return self._value

    def set_value(self, x, client, mac):
        try:
            self._value = self.data_type(x)
            client.publish('devices/{0}/ctl/setpoint'.format(mac),
                '{"d":"[{0},-1]"}'.format(self._value))
        except Exception as ex:
            _log.critical('Could not set value of {0}'.format(self.point_name))
            self._value = x
        self._timestamp = datetime.now()
        return self._value


class CoolTemperatureSetPoint(BaseRegister):
    def __init__(self):
        super(CoolTemperatureSetPoint, self).__init__('byte', False, 'CoolTemperatureSetPoint', 'int')
        self._value = -1
        self._timestamp = datetime.now()

    @property
    def value(self, data):
        self._value = data['setpoint']['data'][1] if 'setpoint' in data else -1
        self._timestamp = datetime.now()
        return self._value

    def set_value(self, x, client, mac):
        try:
            self._value = self.data_type(x)
            client.publish('devices/{0}/ctl/setpoint'.format(mac),
                '{"d":"[-1,{0}]"}'.format(self._value))
        except Exception as ex:
            _log.critical('Could not set value of {0}'.format(self.point_name))
            self._value = x
        self._timestamp = datetime.now()
        return self._value


class ThermostatMode(BaseRegister):
    def __init__(self):
        super(ThermostatMode, self).__init__('byte', False, 'ThermostatMode', 'int')
        self._value = -1
        self._timestamp = datetime.now()

    @property
    def value(self, data):
        self._value = get_value('thermostat_mode')
        self._timestamp = datetime.now()
        return self._value

    def set_value(self, x, client, mac):
        try:
            self._value = self.data_type(x)
            client.publish('devices/{0}/ctl/mode'.format(mac),
                '{"d":"{0}"}'.format(self._value))
        except Exception as ex:
            _log.critical('Could not set value of {0}'.format(self.point_name))
            self._value = x
        self._timestamp = datetime.now()
        return self._value


class FanMode(BaseRegister):
    def __init__(self):
        super(FanMode, self).__init__('byte', False, 'FanMode', 'int')
        self._value = -1
        self._timestamp = datetime.now()

    @property
    def value(self, data):
        self._value = get_value('fan_mode')
        self._timestamp = datetime.now()
        return self._value

    def set_value(self, x, client, mac):
        try:
            self._value = self.data_type(x)
            client.publish('devices/{0}/ctl/fan'.format(mac),
                '{"d":"{0}"}'.format(self._value))
        except Exception as ex:
            _log.critical('Could not set value of {0}'.format(self.point_name))
            self._value = x
        self._timestamp = datetime.now()
        return self._value


cta2045_registers = {
    'NetworkStatus': NetworkStatus,
    'DeviceType': DeviceType,
    'DeviceVendorId': DeviceVendorId,
    'OperationalState': OperationalState,
    'CustomerOverride': CustomerOverride,
    'InstantaneousElectricityConsumption': InstantaneousElectricityConsumption,
    'CumulativeElectricityConsumption': CumulativeElectricityConsumption,
    'TotalEnergyStorageCapacity': TotalEnergyStorageCapacity,
    'PresentEnergyStorageCapacity': PresentEnergyStorageCapacity,
    'PresentTemperature': PresentTemperature,
    'TemperatureOffset': TemperatureOffset,
    'HeatTemperatureSetPoint': HeatTemperatureSetPoint,
    'CoolTemperatureSetPoint': CoolTemperatureSetPoint,
    'ThermostatMode': ThermostatMode,
    'FanMode': FanMode
}


class Interface(BasicRevert, BaseInterface):
    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.data = '{}'
        self.sgd = '{}'

    def configure(self, config_dict, register_config):
        self.config = config_dict

        # Connect to the MQTT broker. Note that '-VD' is appended to the MAC
        # address to avoid MQTT client IDs conflict.
        self.mqtt_client = mqtt.Client(client_id = self.config['macid'] + '-VD', userdata = self)
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message

        mqtt_config = self.config['mqtt']
        if mqtt_config['ca']:
            self.mqtt_client.tls_set(mqtt_config['ca'])
            self.mqtt_client.tls_insecure_set(True)

        self.mqtt_client.username_pw_set(mqtt_config['username'], mqtt_config['password'])
        self.mqtt_client.connect_async(mqtt_config['host'], mqtt_config['port'], mqtt_config['timeout'])
        self.mqtt_client.loop_start()

        if register_config is None:
            register_config = []

        for name in register_config:
            try:
                register = cta2045_registers[name['Volttron Point Name']]
                self.insert_register(register())
                _log.info('Added "{0}" register'.format(name['Volttron Point Name']))
            except:
                _log.info('Unknown register "{0}"'.format(name['Volttron Point Name']))

        # Always add a network status register
        try:
            self.get_register_by_name('NetworkStatus')
        except DriverInterfaceError:
            self.insert_register(NetworkStatus())

    def get_point(self, point_name):
        register = self.get_register_by_name(point_name)
        return register.value(self.data)

    def _set_point(self, point_name, value):
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise IOError(
                "Trying to write to a point configured read only: " + point_name)

        register.set_value(value, self.mqtt_client, self.config['macid'])
        return register.value(self.data)

    def _scrape_all(self):
        # skip the scrape if there are anomalous network conditions
        ns_register = self.get_register_by_name('NetworkStatus')
        network_status = ns_register.value(self.data)
        if network_status != 'Connected':
            return {ns_register.point_name: network_status}

        # scrape points
        result = {}
        registers = self.get_registers_by_type('byte', True)
        for r in registers:
            result[r.point_name] = r.value(self.data)

        _log.info('[MQTT] RESULT: {}'.format(result))
        return result

    @staticmethod
    def _on_mqtt_connect(client, data, flags, rc):
        data._on_connect(client, flags, rc)

    @staticmethod
    def _on_mqtt_message(client, data, msg):
        data._on_message(client, msg)

    def _on_connect(self, client, flags, rc):
        mac = self.config['macid']
        _log.info('[MQTT] Connected {0} to the MQTT broker ({1})'.format(mac, rc))
        self.mqtt_client.subscribe('devices/{0}/data'.format(mac), 2)

    def _on_message(self, client, msg):
        _log.info('[MQTT] Received "{0}" on "{1}"'.format(msg.payload, msg.topic))
        doc = json.loads(msg.payload)
        if 't' in doc:
            self.data = parse_data(doc)
        else:
            self.sgd = parse_sgd_data(doc)

