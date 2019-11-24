#
# -*- coding: utf-8 -*-
# Copyright 2019 Red Hat
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
The nxos_static_routes class
It is in this file where the current configuration (as dict)
is compared to the provided configuration (as dict) and the command set
necessary to bring the current configuration to it's desired end-state is
created
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.module_utils.network.common.cfg.base import ConfigBase
from ansible.module_utils.network.common.utils import to_list, remove_empties, dict_diff
from ansible.module_utils.network.nxos.facts.facts import Facts
from ansible.module_utils.network.nxos.utils.utils import flatten_dict, search_obj_in_list, get_interface_type, normalize_interface

import q


class Static_routes(ConfigBase):
    """
    The nxos_static_routes class
    """

    gather_subset = [
        '!all',
        '!min',
    ]

    gather_network_resources = [
        'static_routes',
    ]

    def __init__(self, module):
        super(Static_routes, self).__init__(module)

    def get_static_routes_facts(self, data=None):
        """ Get the 'facts' (the current configuration)

        :rtype: A dictionary
        :returns: The current configuration as a dictionary
        """
        facts, _warnings = Facts(self._module).get_facts(
            self.gather_subset, self.gather_network_resources, data=data)
        static_routes_facts = facts['ansible_network_resources'].get(
            'static_routes')
        if not static_routes_facts:
            return []
        return static_routes_facts

    def execute_module(self):
        """ Execute the module

        :rtype: A dictionary
        :returns: The result from module execution
        """
        result = {'changed': False}
        warnings = list()
        commands = list()
        state = self._module.params['state']
        existing_static_routes_facts = self.get_static_routes_facts()
        result['before'] = existing_static_routes_facts
        q(state)
        if state == 'gathered':
            result['gathered'] = result['before']
            del result['before']
        else:
            commands.extend(self.set_config(existing_static_routes_facts))
            action_states = ['merged', 'replaced', 'deleted', 'overridden']
            if commands and state in action_states:
                if not self._module.check_mode:
                    self._connection.edit_config(commands)
                result['changed'] = True
                result['commands'] = commands
            if state == 'rendered':
                result['rendered'] = commands
                del result['before']
            elif state == 'parsed':
                result['parsed'] = commands
                del result['before']
            changed_static_routes_facts = self.get_static_routes_facts()
            if result['changed']:
                result['after'] = changed_static_routes_facts

        result['warnings'] = warnings
        q(result)
        return result

    def set_config(self, existing_static_routes_facts):
        """ Collect the configuration from the args passed to the module,
            collect the current configuration (as a dict from facts)

        :rtype: A list
        :returns: the commands necessary to migrate the current configuration
                  to the desired configuration
        """
        config = self._module.params['config']
        q(config)
        want = []
        if config:
            for w in config:
                want.append(remove_empties(w))
        have = existing_static_routes_facts
        resp = self.set_state(want, have)
        return to_list(resp)

    def set_state(self, want, have):
        """ Select the appropriate function based on the state provided

        :param want: the desired configuration as a dictionary
        :param have: the current configuration as a dictionary
        :rtype: A list
        :returns: the commands necessary to migrate the current configuration
                  to the desired configuration
        """
        state = self._module.params['state']
        commands = []
        if state == 'overridden':
            commands = (self._state_overridden(want, have))
        elif state == 'deleted':
            commands = (self._state_deleted(want, have))
        elif state == 'rendered':
            commands = self._state_rendered(want, have=[])
        elif state == 'parsed':
            want = self._module.params['running_config']
            commands = self._state_parsed(want)
        else:
            q(want)
            for w in want:
                if state == 'merged':
                    commands.extend(self._state_merged(w, have))
                    q(commands)
                elif state == 'replaced':
                    commands.extend(self._state_replaced(w, have))
                    q(commands)
        q(commands)
        return commands

    def _state_parsed(self, want):
        q(want)
        d = (self.get_static_routes_facts(want))
        q(d)
        return d

    def _state_rendered(self, want, have):
        commands = []
        for w in want:
            commands.extend(self.set_commands(w, {}))
        q(commands)
        return commands

    def _state_replaced(self, want, have):
        """ The command generator when state is replaced

        :rtype: A list
        :returns: the commands necessary to migrate the current configuration
                  to the desired configuration
        """
        commands = []
        delete_commands = []
        merged_commands = []
        q(have)
        obj_in_have = search_obj_in_list(want['vrf'], have, 'vrf')
        q(obj_in_have)
        if obj_in_have and obj_in_have != {'vrf': '__global__'}:
            afi_list = [w['afi'] for w in want['address_families']]
            q(afi_list)
            for h in obj_in_have['address_families']:
                if h['afi'] in afi_list:
                    q(h['afi'], want)
                    want_afi = search_obj_in_list(
                        h['afi'], want['address_families'], 'afi')
                    q(want_afi)
                    want_dest_list = [w['dest'] for w in want_afi['routes']]
                    for ro in h['routes']:
                        if ro['dest'] in want_dest_list:
                            q(ro)
                            want_dest = search_obj_in_list(
                                ro['dest'], want_afi['routes'], 'dest')
                            want_next_hops = [
                                nh for nh in want_dest['next_hops']]
                            q(want_next_hops)
                            for next_hop in ro['next_hops']:
                                if next_hop in want_next_hops:
                                    {}
                                else:
                                    q(next_hop)
                                    if obj_in_have['vrf'] is '__global__':
                                        obj_in_have['vrf'] = 'default'
                                    if h['afi'] == 'ipv4':
                                        com = 'no ip route ' + \
                                            ro['dest'] + ' ' + \
                                            self.add_commands(next_hop)
                                        q(com)

                                    else:
                                        com = 'no ipv6 route ' + \
                                            ro['dest'] + ' ' + \
                                            self.add_commands(next_hop)
                                    delete_commands.append(com.strip())
                                    # string = 'vrf context ' + \
                                    #     str(obj_in_have['vrf'])
                                    # if string not in delete_commands:
                                    #     delete_commands.insert(0, string)
                                    # delete next_hop
                        else:
                            delete_dict = {'vrf': obj_in_have['vrf'], 'address_families': [
                                {'afi': h['afi'], 'routes':[ro]}]}
                            q(delete_dict)
                            delete_commands.extend(
                                self.del_commands([delete_dict]))
                            # delete ro['dest']
                else:
                    q(h)
                    delete_commands.extend(self.del_commands(
                        [{'address_families': [h], 'vrf': obj_in_have['vrf']}]))
                    # delete h['afi']
        q(delete_commands)
        final_delete_commands = []
        for d in delete_commands:
            if d not in final_delete_commands:
                final_delete_commands.append(d)
        # if there are two afis, 'vrf context..' is added twice fom del_commands. set() gets unique commands
        merged_commands = (self.set_commands(want, have))
        q(merged_commands)
        if merged_commands:
            cmds = set(final_delete_commands).intersection(
                set(merged_commands))
            for cmd in cmds:
                merged_commands.remove(cmd)
        q(merged_commands)
        commands.extend(final_delete_commands)
        commands.extend(merged_commands)
        q(commands)
        return commands

    def _state_overridden(self, want, have):
        """ The command generator when state is overridden

        :rtype: A list
        :returns: the commands necessary to migrate the current configuration
                  to the desired configuration
        """
        commands = []
        q('at overridden')
        want_vrfs = [w['vrf'] for w in want]
        q(want_vrfs)
        for h in have:
            if h['vrf'] not in want_vrfs:
                q(h['vrf'])
                commands.extend(self._state_deleted([h], have))
        for w in want:
            q('inside over2')
            commands.extend(self._state_replaced(w, have))
        return commands

    def _state_merged(self, want, have):
        """ The command generator when state is merged

        :rtype: A list
        :returns: the commands necessary to merge the provided into
                  the current configuration
        """
        return self.set_commands(want, have)

    def _state_deleted(self, want, have):
        """ The command generator when state is deleted

        :rtype: A list
        :returns: the commands necessary to remove the current configuration
                  of the provided objects
        """
        commands = []
        q(want)
        if want:
            for w in want:
                obj_in_have = search_obj_in_list(w['vrf'], have, 'vrf')
                if obj_in_have:
                    commands.extend(self.del_commands([obj_in_have]))
        else:
            if have:
                commands = self.del_commands(have)
        return commands

    def del_commands(self, have):
        q(have)
        commands = []
        # if have != [{'vrf': '__global__'}]:
        for h in have:
            if h != {'vrf': '__global__'}:
                if h['vrf'] == '__global__':
                    h['vrf'] = 'default'
                commands.append('vrf context ' + h['vrf'])
                # q(h)
                for af in h['address_families']:
                    # q(af)
                    for route in af['routes']:
                        # q(route)
                        for next_hop in route['next_hops']:
                            # q(next_hop)
                            if af['afi'] == 'ipv4':
                                command = 'no ip route ' + \
                                    route['dest'] + ' ' + \
                                    self.add_commands(next_hop)
                            else:
                                command = 'no ipv6 route ' + \
                                    route['dest'] + ' ' + \
                                    self.add_commands(next_hop)
                            commands.append(command.strip())
        q(commands)
        return commands

    def add_commands(self, want):
        command = ''
        params = want.keys()
        # q(want)
        pref = vrf = ip = intf = name = tag = track = ''
        if 'admin_distance' in params:
            pref = str(want['admin_distance']) + ' '
        if 'track' in params:
            track = 'track ' + str(want['track'])+' '
        if 'dest_vrf' in params:
            vrf = 'vrf '+str(want['dest_vrf']) + ' '

        if 'forward_router_address' in params:
            ip = want['forward_router_address']+' '
        if 'interface' in params:
            intf = normalize_interface(want['interface'])+' '
        if 'route_name' in params:
            name = 'name ' + str(want['route_name'])+' '
        if 'tag' in params:
            tag = 'tag '+str(want['tag'])+' '

        command = intf+ip+vrf+name+tag+track+pref
        # q(command)
        return command

    def set_commands(self, want, have):
        commands = []
        h1 = h2 = h3 = {}
        q(want, have)
        want = remove_empties(want)
        vrf_list = []
        if have:
            vrf_list = [h['vrf'] for h in have]
        q(vrf_list)
        q(want['vrf'])
        if want['vrf'] in vrf_list and have != [{'vrf': '__global__'}]:
            for x in have:
                if x['vrf'] == want['vrf']:
                    h1 = x  # this has the 'have' dict with same vrf as want
            q(h1)
            if 'address_families' in h1.keys():
                afi_list = [h['afi'] for h in h1['address_families']]
                q(want)
                for af in want['address_families']:
                    if af['afi'] in afi_list:
                        for x in h1['address_families']:
                            if x['afi'] == af['afi']:
                                h2 = x  # this has the have dict with same vrf and afi as want
                        q(h2)
                        dest_list = [h['dest'] for h in h2['routes']]
                        for ro in af['routes']:
                            q(dest_list)
                            # if want['vrf'] is '__global__':
                            #     want['vrf'] = 'default'
                            # commands.append('vrf context '+str(want['vrf']))

                            if ro['dest'] in dest_list:
                                for x in h2['routes']:
                                    if x['dest'] == ro['dest']:
                                        h3 = x  # this has the have dict with same vrf, afi and dest as want
                                q(h3)
                                flag = 0
                                next_hop_list = [h for h in h3['next_hops']]
                                q(next_hop_list, ro['next_hops'], commands)
                                for nh in ro['next_hops']:
                                    if 'interface' in nh.keys():
                                        nh['interface'] = normalize_interface(
                                            nh['interface'])
                                    if nh not in next_hop_list:
                                        if want['vrf'] is '__global__':
                                            want['vrf'] = 'default'
                                        if h2['afi'] == 'ipv4':
                                            com = 'ip route ' + \
                                                ro['dest'] + ' ' + \
                                                self.add_commands(nh)
                                            q(com)

                                        else:
                                            com = 'ipv6 route ' + \
                                                ro['dest'] + ' ' + \
                                                self.add_commands(nh)

                                        vrf_list.append(want['vrf'])
                                        commands.append(com.strip())
                                        string = 'vrf context ' + \
                                            str(want['vrf'])
                                        if string not in commands:
                                            commands.insert(0, string)
                                        q(commands)
                                    # if not flag:
                                    #     # 'vrf context ' command is added initially and then next hop commands are added, but vrf context command is not needed if there is no new next hop to add
                                    #     q(commands)
                                    #     commands.pop()
                                    #     flag = 1
                            else:
                                q('no match for dest')

                                for nh in ro['next_hops']:
                                    if h2['afi'] == 'ipv4':
                                        com = 'ip route ' + \
                                            ro['dest'] + ' ' + \
                                            self.add_commands(nh)
                                    else:
                                        com = 'ipv6 route ' + \
                                            ro['dest'] + ' ' + \
                                            self.add_commands(nh)
                                    if want['vrf'] is '__global__':
                                        want['vrf'] = 'default'
                                    # commands.append(
                                    #     'vrf context '+str(want['vrf']))
                                    string = 'vrf context '+str(want['vrf'])
                                    if string not in commands:
                                        commands.insert(0, string)
                                    commands.append(com.strip())

                    else:
                        q('no match for afi')
                        if want['vrf'] is '__global__':
                            want['vrf'] = 'default'
                        # commands.append('vrf context '+str(want['vrf']))
                        for ro in af['routes']:
                            for nh in ro['next_hops']:
                                if af['afi'] == 'ipv4':
                                    com = 'ip route ' + \
                                        ro['dest'] + ' ' + \
                                        self.add_commands(nh)
                                else:
                                    com = 'ipv6 route ' + \
                                        ro['dest'] + ' ' + \
                                        self.add_commands(nh)
                                commands.append(com.strip())
                                string = 'vrf context '+str(want['vrf'])
                                if string not in commands:
                                    commands.insert(0, string)

        else:
            q('no match for vrf')
            q(want['vrf'])
            if want['vrf'] is '__global__':
                want['vrf'] = 'default'
            # commands.append('vrf context ' + str(want['vrf']))
            vrf_list.append(want['vrf'])
            for wa in want['address_families']:
                for ro in wa['routes']:
                    for nh in ro['next_hops']:
                        if wa['afi'] == 'ipv4':
                            com = 'ip route ' + \
                                ro['dest'] + ' ' + \
                                self.add_commands(nh)
                        else:
                            com = 'ipv6 route ' + \
                                ro['dest'] + ' ' + \
                                self.add_commands(nh)
                        commands.append(com.strip())
                        string = 'vrf context '+str(want['vrf'])
                        if string not in commands:
                            commands.insert(0, string)

        q(commands)
        return commands
