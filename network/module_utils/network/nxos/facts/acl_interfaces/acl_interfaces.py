#
# -*- coding: utf-8 -*-
# Copyright 2019 Red Hat
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
The nxos acl_interfaces fact class
It is in this file the configuration is collected from the device
for a given resource, parsed, and the facts tree is populated
based on the configuration.
"""
import q
import re
from copy import deepcopy

from ansible.module_utils.network.common import utils
from ansible.module_utils.network.nxos.argspec.acl_interfaces.acl_interfaces import Acl_interfacesArgs


class Acl_interfacesFacts(object):
    """ The nxos acl_interfaces fact class
    """

    def __init__(self, module, subspec='config', options='options'):
        self._module = module
        self.argument_spec = Acl_interfacesArgs.argument_spec
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
        """ Populate the facts for acl_interfaces
        :param connection: the device connection
        :param ansible_facts: Facts dictionary
        :param data: previously collected conf
        :rtype: dictionary
        :returns: facts
        """
        if not data:
            data = connection.get('show running-config | section interface')
            data = data.split('interface')
            for i in range(len(data)):
                if not re.search('ip(v6)?( port)? (access-group|traffic-filter)', data[i]):
                    data[i] = ''
            resources = list(filter(None, data))

        objs = []
        for resource in resources:
            if resource:
                obj = self.render_config(self.generated_spec, resource)
                if obj:
                    objs.append(obj)

        q(objs)
        ansible_facts['ansible_network_resources'].pop('acl_interfaces', None)
        facts = {}
        if objs:
            params = utils.validate_config(
                self.argument_spec, {'config': objs})
            params = utils.remove_empties(params)
            facts['acl_interfaces'] = params['config']

        ansible_facts['ansible_network_resources'].update(facts)
        return ansible_facts

    def render_config(self, spec, conf):
        """
        Render config as dictionary structure and delete keys
          from spec for null values

        :param spec: The facts tree, generated from the argspec
        :param conf: The configuration
        :rtype: dictionary
        :returns: The generated config
        """
        config = deepcopy(spec)
        q(conf)
        config['name'] = conf.split('\n')[0]
        config['access_groups'] = []
        v4 = {'afi': 'ipv4', 'acls': []}
        v6 = {'afi': 'ipv6', 'acls': []}
        for c in conf.split('\n')[1:]:
            if c:
                acl4 = re.search('ip( port)? access-group (\w*) (\w*)', c)
                acl6 = re.search('ipv6( port)? traffic-filter (\w*) (\w*)', c)
                if acl4:
                    acl = {'name': acl4.group(2), 'direction': acl4.group(3)}
                    if acl4.group(1):
                        acl.update({'port': True})
                    v4['acls'].append(acl)
                elif acl6:
                    acl = {'name': acl6.group(2), 'direction': acl6.group(3)}
                    if acl6.group(1):
                        acl.update({'port': True})
                    v6['acls'].append(acl)

        q(v4, v6)
        if len(v4['acls']) > 0:
            config['access_groups'].append(v4)
        if len(v6['acls']) > 0:
            config['access_groups'].append(v6)

        q(config)
        return utils.remove_empties(config)
