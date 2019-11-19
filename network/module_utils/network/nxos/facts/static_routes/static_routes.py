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
import re,pprint
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
        if not data:
             data = connection.get("show running-config | include '^ip(v6)* route'")
             vrf_data=connection.get("show running-config | section '^vrf context'")
        objs = []
        data = data.split('\n')
        vrf_data=vrf_data.split('\nvrf context') 
        
        for v in vrf_data:
            if not re.search('\n\s*ip(v6)? route',v):
                vrf_data.remove(v)

        for i in range(1,len(vrf_data)):
            vrf_data[i]='vrf context '+vrf_data[i]
        
        resources=data+vrf_data
        q(resources)
        objs = self.render_config(self.generated_spec, resources)

        ansible_facts['ansible_network_resources'].pop('static_routes', None)
        facts = {}
        q(self.argument_spec)
        if objs:
            params = utils.validate_config(self.argument_spec, {'config': objs})
            q(params)
            facts['static_routes'] = params['config']
        ansible_facts['ansible_network_resources'].update(facts)
        q(ansible_facts)
        return ansible_facts

    def process(self,conf,next_hop):
        conf = re.sub('\s*ip(v6)? route', '', conf)
        # strip 'ip route'
        next_hop['dest']= re.match("^\s*(\S+\/\d+) .*", conf).group(1)

        iface = re.match(".* ([a-zA-Z0-9]+\d*\/\d+(\/?\.?\d*)*) .*", conf) #ethernet1/2/23
        if iface:
            next_hop['interface'] = (iface.group(1))
            # if(iface.group(2)):
            #     next_hop['interface'] = (iface.group(2))

        if '.' in next_hop['dest']:
            next_hop['afi'] = 'ipv4'
            ipv4 = re.match(r'.* (\d+\.\d+\.\d+\.\d+).*',
                            conf)  # gets next hop ip
            next_hop['forward_router_address'] = ipv4.group(1)
        else:
            next_hop['afi'] = 'ipv6'
            ipv6 = re.match(r'.* (\S*:\S*:\S*).*', conf)
            next_hop['forward_router_address'] = ipv6.group(1)

        nullif=re.search('null0',conf,re.IGNORECASE)
        if nullif:
            next_hop['interface']='Null0'
            return next_hop#dest IP not needed for null if

        keywords = ['vrf','name', 'tag', 'track']
        for key in keywords:
            pattern = re.match('.* (?:%s) (\S+).*' % key, conf)
            if pattern:
                next_hop[key] = pattern.group(1)

        pref = re.match('(?:.*) (\d+) (\d+)', conf)
        if pref:
            next_hop['admin_distance'] = pref.group(2)
        # config['next_hops'].append(next_hop)
        return next_hop
    
    def process_command(self,c,afi_list,dest_list,af): 
        n={}
        n=self.process(c,n)
        # top_af={'afi'}
        if n['afi'] not in afi_list:
            af.append({'afi':n['afi'],'routes':[]})
            afi_list.append(n['afi']) 

        next_hop={}
        params=['forward_router_address','interface','admin_distance','name','tag','track','vrf']
        for p in params:
            if p in n.keys():
                if p=='name':
                    next_hop.update({'route_name':n[p]})
                else:
                    next_hop.update({p:n[p]})

        if n['dest'] not in dest_list:
            dest_list.append(n['dest'])
            af[-1]['routes'].append({'dest':n['dest'],'next_hops':[]})
            #if 'dest' is new, create new list under 'routes'
            af[-1]['routes'][-1]['next_hops'].append(next_hop)
        else:
            af[-1]['routes'][-1]['next_hops'].append(next_hop)
            # just append if dest already exists
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
        config=deepcopy(spec)
        q(spec)
        top_level=[]
        global_afi_list=[]
        global_af=[]
        global_dest_list=[]

        for conf in con:
            if conf.startswith('vrf context'):
                svrf = re.match('vrf context (.+)', conf).group(1)
                q(svrf)
                if 'management' not in svrf:  
                    afi_list=[]
                    af=[]
                    dest_list=[] 
                    config_dict={'vrf':svrf,'address_families':[]}
                    conf = conf.split('\n')
                    conf=conf[1:] #considering from the second line. First line is 'vrf context..'
                    for c in conf:
                        if 'ip route' in c or 'ipv6 route' in c:
                            q(conf,afi_list,af,dest_list)
                            (self.process_command(c,afi_list,dest_list,af))                                         
                            config_dict['address_families']=af
                else:
                    continue
                top_level.append(config_dict)
            else:
                if 'ip route' in conf or 'ipv6 route' in conf:
                    # q(conf,global_afi_list,global_af,global_dest_list)
                    (self.process_command(conf,global_afi_list,global_dest_list,global_af))
                    
        global_list={'address_families':global_af}
        top_level.append(global_list)
        # q(top_level)
        return top_level