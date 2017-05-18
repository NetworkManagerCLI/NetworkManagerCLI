#IP router
from mininet.node import Node

from ipaddress import ip_interface

from fibbingnode.misc.mininetlib import get_logger, PRIVATE_IP_KEY,\
                                        FIBBING_MIN_COST, otherIntf,\
                                        L3Router,\
                                        FIBBING_DEFAULT_AREA
import fibbingnode.misc.router
from fibbingnode.misc.router import QuaggaRouter, RouterConfigDict
from fibbingnode.misc.utils import ConfigDict

from util import OSPF_KEY,LOG
from fibbingnode import CFG

log = get_logger()
fibbingnode.misc.router.log = log


class MininetRouter(QuaggaRouter):
    def __init__(self, node, *args, **kwargs):
        super(MininetRouter, self).__init__(name=node.name,
                                            working_dir='/tmp',
                                            *args, **kwargs)
        self.mnode = node

    def call(self, *args, **kwargs):
        return self.mnode.cmd(*args, **kwargs)

    def pipe(self, *args, **kwargs):
        return self.mnode.popen(*args, **kwargs)

    def get_config_node(self):
        return MininetRouterConfig(
                self.mnode,
                debug_ospf=self.mnode.debug.get('ospf', ()),
                debug_zebra=self.mnode.debug.get('zebra', ()))
# -----------------------------------------------------------------------

# -----------------------------------------------------------------------
class IPRouter(Node, L3Router):
    def __init__(self, name,
                 private_net='10.0.0.0/8',
                 routerid=None, static_routes=(), debug=None,
                 # default advertisement cost
                 cost_host=1000,
                 subrouter=MininetRouter,
                 **kwargs):
        """static_routes in the form of (prefix, via_node_id)*
        debug as a dict with the daemon name as key and the value
        is a list of quagga debug flags to set for that daemon"""
        self.private_net = str(private_net)
        self.debug = debug if debug else {}
        self.rid = routerid
        self.static_routes = static_routes
        self.hello_interval = '1' # Default value
        self.dead_interval = 'minimal hello-multiplier 5' # default value
        self.cost_host = cost_host


        super(IPRouter, self).__init__(name, **kwargs)
        self.router = subrouter(self) if subrouter else None

    def start(self):
        self.cmd('ip', 'link', 'set', 'dev', 'lo', 'up')
        for itf in self.intfList():
            # Set up the private ip
            ip = itf.params.get(PRIVATE_IP_KEY, ())
            self.cmd('ip', 'address', 'add', ip,
                     'dev', itf.name)
            # set up the secondary-ips
            if itf.params.get('secondary-ips') :
                for sec in itf.params.get('secondary-ips') :
                    self.cmd('ip', 'address', 'add', sec,
                             'dev', itf.name)

        neighbor_to_intf = {otherIntf(itf).name: itf
                            for itf in self.intfList()}
        self.static_routes = [(p, v if v not in neighbor_to_intf
                               else neighbor_to_intf[v])
                              for p, v in self.static_routes]

        if self.router:
            self.router.start()

    def terminate(self):
        if self.router:
            self.router.delete()
        super(IPRouter, self).terminate()

    @staticmethod
    def is_l3router_intf(itf):
        # We override the instance check in order to not match Controllers
        return (isinstance(itf.node, IPRouter) and
                itf.params.get('cost', 1) >= 0)

    @property
    def id(self):
        return self.rid if self.rid else self.intfList()[0].ip

    def ospf_interfaces(self):
        # Dont't add the interfaces connected to host
        return filter(lambda intf: intf.params.get('Host', False ) != True, self.intfList() )

# --------------------------------------------------------------------------
class MininetRouterConfig(RouterConfigDict):
    def __init__(self, router, *args, **kwargs):
        super(MininetRouterConfig, self).__init__(router, *args, **kwargs)

        self.ospf.redistribute.connected = router.cost_host
        self.ospf.redistribute.static = router.cost_host
        self.ospf.router_id = router.id

        #  # Parse LSA throttling parameters
        # delay = CFG.get("DEFAULT", 'delay')
        # initial_holdtime = CFG.get("DEFAULT", 'initial_holdtime')
        # max_holdtime = CFG.get("DEFAULT", 'max_holdtime')
        #
        # # Parse minimum LS intervals
        # min_ls_interval = CFG.get("DEFAULT", 'min_ls_interval')
        # min_ls_arrival = CFG.get("DEFAULT", 'min_ls_arrival')
        ospf_intf = router.ospf_interfaces()[0]

        delay = ospf_intf.params.get('odelay')
        initial_holdtime = ospf_intf.params.get('initial_holdtime')
        max_holdtime = ospf_intf.params.get('max_holdtime')
        min_ls_arrival = ospf_intf.params.get('min_ls_arrival')
        min_ls_interval = ospf_intf.params.get('min_ls_interval')

        self.ospf.throttling = ConfigDict(spf=ConfigDict(delay=delay,
                                                         initial_holdtime=initial_holdtime,
                                                         max_holdtime=max_holdtime),
                                          lsa_all=ConfigDict(min_ls_interval=min_ls_interval))

        self.ospf.lsa = ConfigDict(min_ls_arrival=min_ls_arrival)

    def build_ospf(self, router):
        cfg = super(MininetRouterConfig, self).build_ospf(router)
        networks = []
        for itf in router.ospf_interfaces():
            c = itf.params.get('cost', FIBBING_MIN_COST)
            if c > 0:
                cfg.interfaces.append(
                    ConfigDict(name=itf.name,
                               description=str(itf.link),
                               ospf=ConfigDict(
                                    cost=c,
                                    priority=10,# TODO add in configuration
                                    dead_int=itf.params.get('dead-interval'),
                                    hello_int=itf.params.get('hello-interval'))))
                area = itf.params.get('area')
                networks.append((ip_interface('%s/%s' %
                                              (itf.ip, itf.prefixLen))
                                .network, area))

                # TODO figure out the private config knob so that the private
                # addresses dont create redundant OSPF session over the same
                # interface ...
                try:
                    PrivateIP = itf.params[PRIVATE_IP_KEY]
                    networks.append( (ip_interface(unicode(PrivateIP)).network, area ) )

                    for sec in itf.params.get('secondary-ips') :
                        networks.append( (ip_interface(unicode(sec)).network, area ) )
                except KeyError:
                    pass  # No private ip on that interface
            else:
                cfg.passive_interfaces.append(itf)

        for net, area in networks:
            cfg.networks.append(ConfigDict(domain=net.with_prefixlen,
                                           area=area))

        return cfg

    def build_zebra(self, router):
        cfg = super(MininetRouterConfig, self).build_zebra(router)
        # TODO custom private net
        plen = int(router.private_net.split('/')[1])
        cfg.prefixlists = [ConfigDict(name='PRIVATE',
                                      action='permit',
                                      prefix=router.private_net,
                                      ge=plen + 1)
                            ]
        cfg.routemaps = [ConfigDict(name='IMPORT',
                                    action='deny',
                                    prio='10',
                                    prefix=['PRIVATE'],
                                    proto=[]),
                         ConfigDict(name='IMPORT',
                                    action='permit',
                                    prio='20',
                                    prefix=[],
                                    proto=['ospf'])]

        cfg.static_routes.extend(router.static_routes)
        return cfg
