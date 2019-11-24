#
# -*- coding: utf-8 -*-
# Copyright 2019 Red Hat
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
The nxos static_routes fact class
It is in this file the configuration is collected from the device
for a given resource, parsed, and the facts tree is populated
based on the configuration.
"""
import re
import q
from copy import deepcopy
from ansible.module_utils.network.common import utils
from ansible.module_utils.network.nxos.argspec.static_routes.static_routes import Static_routesArgs


class Static_routesFacts(object):
    """ The nxos static_routes fact class
    """

    def __init__(self, module, subspec='config', options='options'):
        self._module = module
        self.argument_spec = Static_routesArgs.argument_spec
        spec = deepcopy(self.argument_spec)
        if subspec:
            if options:
                facts_argument_spec = spec[subspec][options]
            else:
                facts_argument_spec = spec[subspec]
        else:
            facts_argument_spec = spec

        self.generated_spec = utils.generate_dict(facts_argument_spec)

    def populate_facts(self, connection, ansible_facts, data=None):
        """ Populate the facts for static_routes
        :param connection: the device connection
        :param ansible_facts: Facts dictionary
        :param data: previously collected conf
        :rtype: dictionary
        :returns: facts
        """
        vrf_data = []
        non_vrf_data = []
        q(connection)
        q(data)
        if not data:
            non_vrf_data = connection.get(
                "show running-config | include '^ip(v6)* route'")
            vrf_data = connection.get(
                "show running-config | section '^vrf context'")
            non_vrf_data = non_vrf_data.split('\n')
            vrf_data = vrf_data.split('\nvrf context')
            q(vrf_data)
        else:
            data = data.split('\n')
            q(data)
            i = 0
            while i <= (len(data)-1):
                # q(i)
                if 'vrf context ' in data[i]:
                    vrf_conf = data[i]
                    j = i+1
                    # q(j)
                    while j < len(data) and 'vrf context ' not in data[j]:
                        # q(data[j])
                        vrf_conf += '\n'+data[j]
                        j += 1
                    i = j
                    vrf_data.append(vrf_conf)
                else:
                    non_vrf_data.append(data[i])
                    i += 1
        q(data, vrf_data, non_vrf_data)
        objs = []
        # as we split based on 'vrf context', it is stripped from the data except the first element
        new_vrf_data = []
        # q(vrf_data)
        for v in vrf_data:
            if re.search('management', v):
                continue
                # ignore management vrf
            if re.search('\n\s*ip(v6)? route', v):
                # q('hereh')
                # q(v)
                new_vrf_data.append(v)
                # dont consider vrf if it does not have routes
        q(new_vrf_data)
        for i in range(len(new_vrf_data)):
            if not re.search('^vrf context', new_vrf_data[i]):
                new_vrf_data[i] = 'vrf context'+new_vrf_data[i]

        resources = non_vrf_data+new_vrf_data
        q(resources)
        objs = self.render_config(self.generated_spec, resources)

        ansible_facts['ansible_network_resources'].pop('static_routes', None)
        facts = {}
        # q(objs)
        if objs:
            params = utils.validate_config(
                self.argument_spec, {'config': objs})
            params = utils.remove_empties(params)
            # q(params)
            for c in params['config']:
                if c == {'vrf': '__global__'}:
                    params['config'].remove(c)
            # q(params)
            facts['static_routes'] = params['config']
        ansible_facts['ansible_network_resources'].update(facts)
        return ansible_facts

    def get_inner_dict(self, conf, inner_dict):
        ''' 
        This method parses the command to create the innermost dictionary of the config
        '''

        conf = re.sub('\s*ip(v6)? route', '', conf)
        # strip 'ip route'
        # q(conf)
        inner_dict['dest'] = re.match("^\s*(\S+\/\d+) .*", conf).group(1)

        # ethernet1/2/23
        iface = re.match(".* ([a-zA-Z0-9]+\d*\/\d+(\/?\.?\d*)*) .*", conf)
        if iface:
            inner_dict['interface'] = (iface.group(1))
            conf = re.sub(inner_dict['interface'], '', conf)

        if '.' in inner_dict['dest']:
            inner_dict['afi'] = 'ipv4'
            ipv4 = re.match(r'.* (\d+\.\d+\.\d+\.\d+).*',
                            conf)  # gets next hop ip
            inner_dict['forward_router_address'] = ipv4.group(1)

        else:
            inner_dict['afi'] = 'ipv6'
            ipv6 = re.match(r'.* (\S*:\S*:\S*).*', conf)
            inner_dict['forward_router_address'] = ipv6.group(1)
        conf = re.sub(inner_dict['forward_router_address'], '', conf)

        nullif = re.search('null0', conf, re.IGNORECASE)
        if nullif:
            inner_dict['interface'] = 'Null0'
            inner_dict['forward_router_address'] = None
            return inner_dict  # dest IP not needed for null if

        keywords = ['vrf', 'name', 'tag', 'track']
        for key in keywords:
            pattern = re.match('.* (?:%s) (\S+).*' % key, conf)
            if pattern:
                inner_dict[key] = pattern.group(1).strip()
                # q(key + ' ' + inner_dict[key])
                conf = re.sub(key + ' ' + inner_dict[key], '', conf)

        # q(conf)
        pref = re.match('(?:.*) (\d+)$', conf)
        if pref:
            # q(pref)
            inner_dict['admin_distance'] = pref.group(1)

        return inner_dict

    def process_command(self, conf, afi_list, dest_list, af):
        '''
        This uses the 
        '''
        inner_dict = {}

        inner_dict = self.get_inner_dict(conf, inner_dict)
        if inner_dict['afi'] not in afi_list:
            af.append({'afi': inner_dict['afi'], 'routes': []})
            afi_list.append(inner_dict['afi'])
        next_hop = {}
        # q(inner_dict.keys())
        params = ['forward_router_address', 'interface',
                  'admin_distance', 'name', 'tag', 'track', 'vrf']
        for p in params:
            if p in inner_dict.keys():
                if p == 'name':
                    next_hop.update({'route_name': inner_dict[p]})
                elif p == 'vrf':
                    next_hop.update({'dest_vrf': inner_dict[p]})
                else:
                    next_hop.update({p: inner_dict[p]})

        if inner_dict['dest'] not in dest_list:
            dest_list.append(inner_dict['dest'])
            af[-1]['routes'].append({'dest': inner_dict['dest'],
                                     'next_hops': []})
            # if 'dest' is new, create new list under 'routes'
            af[-1]['routes'][-1]['next_hops'].append(next_hop)
        else:
            af[-1]['routes'][-1]['next_hops'].append(next_hop)
            # just append if dest already exists
        # q(af)
        return af

    def render_config(self, spec, con):
        """
        Render config as dictionary structure and delete keys
          from spec for null values

        :param spec: The facts tree, generated from the argspec
        :param conf: The configuration
        :rtype: dictionary
        :returns: The generated config
        """
        # config=deepcopy(spec)
        config = []
        global_afi_list = []
        global_af = []
        global_dest_list = []
        if con:
            for conf in con:
                # q(conf)
                if conf.startswith('vrf context'):
                    svrf = re.match('vrf context (\S+)\n', conf).group(1)
                    # q(svrf)
                    if 'management' not in svrf:
                        afi_list = []
                        af = []
                        dest_list = []
                        config_dict = {'vrf': svrf, 'address_families': []}
                        conf = conf.split('\n')
                        # considering from the second line as first line is 'vrf context..'
                        conf = conf[1:]
                        for c in conf:
                            if 'ip route' in c or 'ipv6 route' in c:
                                self.process_command(
                                    c, afi_list, dest_list, af)
                                config_dict['address_families'] = af
                    else:
                        continue
                    config.append(config_dict)
                else:
                    if 'ip route' in conf or 'ipv6 route' in conf:
                        self.process_command(
                            conf, global_afi_list, global_dest_list, global_af)
                        # q(global_af)
            config.append(utils.remove_empties(
                {'address_families': global_af}))
            # q(config)
        return config
