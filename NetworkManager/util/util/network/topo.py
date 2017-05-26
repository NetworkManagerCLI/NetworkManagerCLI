import fibbingnode.misc.mininetlib as _lib
from fibbingnode.misc.mininetlib.iptopo import IPTopo

from fibbingnode.misc.mininetlib import  PRIVATE_IP_KEY, CFG_KEY
from util import LOG


from ipaddress import ip_interface
import json
# package un util/util
from util import TOPOLOGY_CONFIG, REQUIREMENT_CONFIG,\
                        OSPF_KEY,C1_cfg, TOPOlOGY_FILE,\
                        NETWORK_port, CONTROLLER_port,\
                        PACKETSIZE, ACK, LOCALHOST, NETLISTENER_port



class CustomTopo(IPTopo):
    """
    Topology class that is passed to the Mininet network class
    to add and connect all the routers, hosts and controller
    """

    def __init__(self, config, *args, **kwargs):
        self.config = config.get('config')
        super(CustomTopo, self).__init__(*args, **kwargs)
    def build(self, *args, **kwargs):


        if not self.config :
            LOG.error(' not received config')
        else :
            LOG.info(' SUCCESS received config')
            conf = self.config

        fibbing_ctrl = conf.get('fibbing-controller')
        ospf_links = conf.get('link-ospf')
        hosts_link  = conf.get('hosts-link')
        ctrl_links = fibbing_ctrl.get('links')
        ospf_routers = conf.get('routers')
        # get private network
        private_net = fibbing_ctrl.get('controller-config').get('private-ip-prefix')
        base_net = fibbing_ctrl.get('controller-config').get('base-net-perfix')

        # mapping router name, iprouter obj
        routers = {}

        # configure ospf routers
        for o_r in ospf_routers :
            name = o_r.get('name')
            routers[name] = self.addRouter(name,
                                routerid= str(o_r.get('ospf').get('router-id')),
                                private_net=private_net)

        # configure ospf links
        for ol in ospf_links :
            src  = ol.get('src')
            dest = ol .get('dest')
            src_router  = routers.get(src.get('name'))
            dest_router = routers.get(dest.get('name'))
            src_intfName  = src.get('intf')
            dest_intfName = dest.get('intf')

            src_cost = int(ol.get('cost'))
            dest_cost= int(ol.get('cost'))
            if not ol.get('bidirectional') :
                src_cost = int(ol.get('src').get('cost'))
                dest_cost= int(ol.get('dest').get('cost'))


            src_params = {
                'cost' : src_cost,
                'bw' : int(ol.get('bw')),
                'ip' : src.get('ip'),
                PRIVATE_IP_KEY : src.get('private-ip'),
                'prefixLen' : int(src.get('ip').split('/')[1]),
                'area' : src.get('ospf').get('area'),
                'hello-interval' : src.get('ospf').get('hello-interval'),
                'dead-interval' : src.get('ospf').get('dead-interval'),
                'secondary-ips' : [],
                'min_ls_arrival' : int(src.get('ospf').get('lsa').get('min_ls_arrival')),
                'min_ls_interval' : int(src.get('ospf').get('lsa').get('min_ls_interval')),
                'odelay' : int(src.get('ospf').get('throttle').get('delay')),
                'initial_holdtime' : int(src.get('ospf').get('throttle').get('initial_holdtime')),
                'max_holdtime' : int(src.get('ospf').get('throttle').get('max_holdtime'))
            }

            dest_params = {
                'cost' : dest_cost,
                'bw' : int(ol.get('bw')),
                'ip' : dest.get('ip'),
                PRIVATE_IP_KEY : dest.get('private-ip'),
                'prefixLen' : int(dest.get('ip').split('/')[1]),
                'area' : dest.get('ospf').get('area'),
                'hello-interval' : dest.get('ospf').get('hello-interval'),
                'dead-interval' : str(dest.get('ospf').get('dead-interval')),
                'secondary-ips' : [],
                'min_ls_arrival' : int(dest.get('ospf').get('lsa').get('min_ls_arrival')),
                'min_ls_interval' : int(dest.get('ospf').get('lsa').get('min_ls_interval')),
                'odelay' : int(dest.get('ospf').get('throttle').get('delay')),
                'initial_holdtime' : int(dest.get('ospf').get('throttle').get('initial_holdtime')),
                'max_holdtime' : int(dest.get('ospf').get('throttle').get('max_holdtime'))
            }

            self.addLink(routers[src.get('name')],
                        routers[dest.get('name')],
                        intfName1=src_intfName,
                        intfName2=dest_intfName,
                        params1=src_params,
                        params2=dest_params)




        # configure destinations link
        for d in hosts_link :
            host = d.get('host')
            router = d.get('router')
            routerip = router.get('ip')
            host_obj = self.addHost(host.get('name'),
                                    ip=str(host.get('ip')),
                                    defaultRoute='via '+ str(routerip.split('/')[0]))
            #
            host_intfname   = host.get('intf')
            router_intfname = router.get('intf')
            host_params = {
                'ip' : str(host.get('ip')),
                'cost' : 1000,
                'bw' : int(d.get('bw')),
                'prefixLen' : int(host.get('ip').split('/')[1])
            }

            router_params = {
                'ip' : str(router.get('ip')),
                'cost' : 1000,
                'bw' : int(d.get('bw')),
                'prefixLen' : int(router.get('ip').split('/')[1]),
                'Host' : True
            }

            self.addLink(host_obj,
                        routers[router.get('name')],
                        intfName1=host_intfname,
                        intfName2=router_intfname,
                        params1=host_params,
                        params2=router_params
                        )


        # Get controller configurations
        controller_o_conf = fibbing_ctrl.get('controller-config').get('ospf')
        th_initial_holdtime = controller_o_conf.get('throttle').get('initial_holdtime')
        th_delay = controller_o_conf.get('throttle').get('delay')
        th_max_holdtime = controller_o_conf.get('throttle').get('max_holdtime')
        min_ls_arrival = controller_o_conf.get('lsa').get('min_ls_arrival')
        min_ls_interval = controller_o_conf.get('lsa').get('min_ls_interval')
        hello = controller_o_conf.get('hello-interval')
        dead = controller_o_conf.get('dead-interval')
        area = controller_o_conf.get('area')

        defaults = {CFG_KEY: {'base_net': base_net,
                              'controller_prefixlen': 24,
                              'debug': int(_lib.DEBUG_FLAG),
                              'private_net':private_net,
                              'draw_graph': 0,
                              'private_ips': 'private_ip_binding.json',
                              'area' : str(area),
                              'hello_interval' : str(hello),
                              'dead_interval' : str(dead),
                              'min_ls_arrival' : int(min_ls_arrival),
                              'min_ls_interval' : int(min_ls_interval),
                              'delay' : int(th_delay),
                              'initial_holdtime' : int(th_initial_holdtime),
                              'max_holdtime' : int(th_max_holdtime)

                              }}

        ctrl_map = {}
        for c_l in ctrl_links :
            router = c_l.get('router')
            controller = c_l.get('controller')
            if not ctrl_map.get(controller.get('name')) :
                # configure the fibbing controllers
                CFG_path = '/tmp/%s.cfg' % controller.get('name')
                ctrl = self.addController(controller.get('name'), cfg_path=None, **defaults)
                ctrl_map[controller.get('name')] = ctrl
            ctrl_ip = controller.get('ip')
            rc   = routers[router.get('name')]
            ctrl_intfname = controller.get('intf')
            rc_intfname   = router.get('intf')
            ctrl_params = {
                'bw' : int(c_l.get('bw')),
                'ip' : str(ctrl_ip)
            }

            rc_params = {
                'bw' : int(c_l.get('bw')),
                'ip' : str(router.get('ip')),
                'area' : str(area),
                'hello-interval' : str(hello),
                'dead-interval' : str(dead),
                'min_ls_arrival' : int(min_ls_arrival),
                'min_ls_interval' : int(min_ls_interval),
                'delay' : int(th_delay),
                'initial_holdtime' : int(th_initial_holdtime),
                'max_holdtime' : int(th_max_holdtime)
            }

            # default cost=100000
            ctrl = ctrl_map[controller.get('name')]
            self.addLink(ctrl, rc, cost=10000,
                        intfName1=ctrl_intfname,
                        intfName2=rc_intfname,
                        params1=ctrl_params,
                        params2=rc_params)
