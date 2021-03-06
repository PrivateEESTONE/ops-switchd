# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Hewlett Packard Enterprise Development LP
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""
OpenSwitch Test for sFlow polling interval configuration changes.
"""

import time


TOPOLOGY = """
#                    +----------------+
#                    |                |
#                    |   Host 2       |
#                    |  (sflowtool)   |
#                    |                |
#                    +-+--------------+
#                      |
#                      |
#         +------------+--+
#         |               |
#         |               |
#         |    Open       |
#         |    Switch     |
#         |               |
#         |               |
#         +-+-------------+
#           |
#           |
#+----------+--+
#|             |
#|             |
#|  Host 1     |
#|             |
#+-------------+

# Nodes
[type=openswitch name="OpenSwitch"] ops1
[type=host name="Host 1"] hs1
[type=host name="Host 2" image="openswitch/sflowtool:latest"] hs2

# Links
hs1:1 -- ops1:1
hs2:1 -- ops1:2
"""


def test_sflow_ft_polling_interval(topology, step):
    """
    Tests sflow polling interval.
    """
    ops1 = topology.get('ops1')
    hs1 = topology.get('hs1')
    hs2 = topology.get('hs2')

    assert ops1 is not None
    assert hs1 is not None
    assert hs2 is not None

    ping_count = 200
    ping_interval = 0.1
    sampling_rate = 10
    polling_interval = 10
    p1 = ops1.ports['1']

    # Configure host interfaces
    step("### Configuring host interfaces ###")
    hs1.libs.ip.interface('1', addr='10.10.10.2/24', up=True)
    hs2.libs.ip.interface('1', addr='10.10.11.2/24', up=True)

    # Configure interfaces on the switch
    step("Configuring interface 1 of switch")
    with ops1.libs.vtysh.ConfigInterface('1') as ctx:
        ctx.ip_address('10.10.10.1/24')
        ctx.no_shutdown()

    step("Configuring interface 2 of switch")
    with ops1.libs.vtysh.ConfigInterface('2') as ctx:
        ctx.ip_address('10.10.11.1/24')
        ctx.no_shutdown()

    # Configure sFlow
    step("### Configuring sFlow ###")
    with ops1.libs.vtysh.Configure() as ctx:
        ctx.sflow_enable()
        ctx.sflow_sampling(sampling_rate)
        ctx.sflow_agent_interface(p1)
        ctx.sflow_collector('10.10.11.2')
        ctx.sflow_polling(polling_interval)

    collector = {}
    collector['ip'] = '10.10.11.2'
    collector['port'] = '6343'
    collector['vrf'] = 'vrf_default'

    sflow_config = ops1.libs.vtysh.show_sflow()
    assert sflow_config['sflow'] == 'enabled'
    assert int(sflow_config['sampling_rate']) == sampling_rate
    assert sflow_config['collector'][0] == collector
    assert str(sflow_config['agent_interface']) == p1
    assert int(sflow_config['polling_interval']) == polling_interval

    time.sleep(20)

    # Start sflowtool
    hs2.libs.sflowtool.start(mode='line')

    # Generate CPU destined traffic
    hs1.libs.ping.ping(ping_count, '10.10.10.1', ping_interval)

    time.sleep(30)
    # Stop sflowtool
    result = hs2.libs.sflowtool.stop()

    # Checking if packets are present
    assert len(result['packets']) > 0

    # Get the CNTR packet count for polling 10 sec
    count_10 = int(result['sample_count'])
    step("\n\nCNTR packets - 10sec polling: " + str(result['sample_count']))

    # Get the interfaces in CNTR packets
    index = []
    for packet in result['packets']:
        if str(packet['packet_type']) == 'CNTR':
                step("\n\npacket----"+str(packet))
                if packet['if_index'] not in index:
                    assert packet['agent_address'] == '10.10.10.1'
                    index.append(int(packet['if_index']))

    # Check if atleast 2 interfaces are present in CNTR packets
    assert len(index) >= 2

    # Reset to default polling interval
    with ops1.libs.vtysh.Configure() as ctx:
        ctx.no_sflow_polling()

    sflow_config = ops1.libs.vtysh.show_sflow()
    assert int(sflow_config['polling_interval']) == 30

    time.sleep(20)

    # Start sflowtool
    hs2.libs.sflowtool.start(mode='line')

    # Generate CPU destined traffic
    hs1.libs.ping.ping(ping_count, '10.10.10.1', ping_interval)

    time.sleep(30)
    # Stop sflowtool
    result = hs2.libs.sflowtool.stop()

    # Checking if packets are present
    assert len(result['packets']) > 0

    # Get the CNTR packet count for polling 30 sec
    count_30 = int(result['sample_count'])
    step("\n\nCNTR packets - 30sec polling: " + str(result['sample_count']))

    # Check if CNTR packets are more than double for 10 vs 30 sec polling
    assert count_10 > count_30

    # Get the interfaces in CNTR packets
    index = []
    for packet in result['packets']:
        if str(packet['packet_type']) == 'CNTR':
            if packet['if_index'] not in index:
                assert packet['agent_address'] == '10.10.10.1'
                index.append(int(packet['if_index']))

    # Check if atleast 2 interfaces are present in CNTR packets
    assert len(index) >= 2
