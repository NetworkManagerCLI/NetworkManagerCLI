# Testing Network
import sys
import time
import math
import json
import itertools

from ipaddress import ip_interface, ip_network

from mininet.net import Mininet
from mininet.node import Host
from mininet.nodelib import LinuxBridge

import fibbingnode.misc.mininetlib as _lib
from fibbingnode.misc.mininetlib import get_logger, PRIVATE_IP_KEY,\
                                        otherIntf, FIBBING_MIN_COST,\
                                        FIBBING_DEFAULT_AREA




from fibbingnode.misc.utils import cmp_prefixlen, is_container

from util.network.iprouter import IPRouter
from util.network.fibbingcontroller import FibbingController

log = get_logger()


def isBroadcastDomainBoundary(node):
    return isinstance(node, Host) or isinstance(node, IPRouter)


class CustomIPNet(Mininet):
    """
        :param private_ip_net: The network used for private addresses
        :param private_ip_bindings: The file name for the private ip binding
        :param controller_net: The prefix to use for the Fibbing controllers
                                Internal networks
        :param wait_for_convergence: Set of nodes that should be able to ping
                                     each other when starting the network
    """
    def __init__(self,
                 router=IPRouter,
                 controller=FibbingController,
                 private_ip_net='10.0.0.0/24',
                 controller_net='172.16.0.0/12',
                 ipBase='192.168.0.0/24',
                 private_ip_bindings='private_ip_binding.json',
                 debug=_lib.DEBUG_FLAG,
                 switch=LinuxBridge,
                 wait_for_convergence=(),
                 *args, **kwargs):
        _lib.DEBUG_FLAG = debug
        if debug:
            log.setLogLevel('debug')
        self.private_ip_net = private_ip_net
        self.unallocated_private_net = [private_ip_net]
        self.router = router
        self.private_ip_bindings = private_ip_bindings
        self.controller_net = controller_net
        self.routers = []
        self.ip_allocs = {}
        self.unallocated_ip_base = [ipBase]
        self.wait_for_convergence = wait_for_convergence
        super(CustomIPNet, self).__init__(ipBase=ipBase, controller=controller,
                                    switch=switch, *args, **kwargs)

    def addRouter(self, name, cls=None, **params):
        if not cls:
            cls = self.router
        r = cls(name, **params)
        self.routers.append(r)
        self.nameToNode[name] = r
        return r

    def addController(self, name, cls=None, **params):
        super(CustomIPNet, self).addController(name, controller=cls, **params)

    def addLink(self, node1, node2, port1=None, port2=None,
                cost=FIBBING_MIN_COST, area=FIBBING_DEFAULT_AREA, **params):
        """:param cost: The IGP metric of this link (applied to both
        interfaces) if not set in params1/2. If it is <= 0, this will disable
        OSPF on this interface! (passive-interface)
        :param area: The IGP area for the interfaces on this link"""
        params1 = params.get('params1', {})
        if 'cost' not in params1:
            params1.update(cost=cost)

        params2 = params.get('params2', {})
        if 'cost' not in params2:
            params2.update(cost=cost)

        if 'area' not in params1 :
            params1.update(area=area)
        if 'area' not in params2 :
            params2.update(area=area)

        print 'cost = ' + str(params1.get('cost'))
        params.update(params1=params1)
        params.update(params2=params2)
        super(CustomIPNet, self).addLink(node1, node2, port1, port2, **params)

    def __iter__(self):
        for r in self.routers:
            yield r.name
        for n in super(CustomIPNet, self).__iter__():
            yield n

    def __len__(self):
        return len(self.routers) + super(CustomIPNet, self).__len__()

    def buildFromTopo(self, topo=None):
        log.info('\n*** Adding Routers:\n')
        for routerName in topo.routers():
            self.addRouter(routerName, **topo.nodeInfo(routerName))
            log.info(routerName + ' ')
        log.info('\n\n*** Adding FibbingControllers:\n')
        ctrlrs = topo.controllers()
        if not ctrlrs:
            self.controller = None
        for cName in topo.controllers():
            self.addController(cName, **topo.nodeInfo(cName))
            log.info(cName + ' ')
        log.info('\n')
        super(CustomIPNet, self).buildFromTopo(topo)

    def start(self, timeout=None):
        """If the network has a set of nodes to test for convergence, this
        method will block until they can all ping each other.

        :param timeout: Maximal time in sec before giving up on the convergence
                        test"""
        for n in self.values():
            for i in n.intfList():
                self.ip_allocs[str(i.ip)] = n
                try:
                    private = i.params[PRIVATE_IP_KEY]
                    self.ip_allocs[str(private)] = n
                    for sec in i.params.get('secondary-ips') :
                        self.ip_allocs[str(sec)] = n
                except KeyError:
                    pass
        log.info('*** Starting %s routers\n' % len(self.routers))
        for router in self.routers:
            log.info(router.name + ' ')
            router.start()
        log.info('\n')
        log.info('*** Setting default host routes\n')
        for h in self.hosts:
            if 'defaultRoute' in h.params:
                continue  # Skipping hosts with explicit default route

        log.info('\n')
        super(CustomIPNet, self).start()
        if self.wait_for_convergence:
            self._convergence_test(timeout)

    def _convergence_test(self, timeout):
        log.info('Waiting for the network to converge\n')
        log.info('(Watching:', self.wait_for_convergence, ')')
        start_t = time.time()
        converged = 0
        while converged < 100:
            sent_tot, received_tot = 0, 0
            for src, dst in itertools.combinations(
                    self.wait_for_convergence, 2):
                r = self[src].cmd('ping -c1 -W 1 %s' % self[dst].IP())
                sent, received = self._parsePing(r)
                sent_tot += sent
                received_tot += received
            converged = received_tot / sent_tot * 100
            if timeout and time.time() - start_t > timeout:
                break
            log.info(converged, '%/')
        if converged >= 100:
            log.info('Converged in', time.time() - start_t, 'sec\n')
        else:
            log.error('The network did not converge !!\n')

    def stop(self):
        log.info('*** Stopping %i routers\n' % len(self.routers))
        for router in self.routers:
            log.info(router.name + ' ')
            router.terminate()
        log.info('\n')
        super(CustomIPNet, self).stop()


    def node_for_ip(self, ip):
        return self.ip_allocs[ip]


class TopologyDB(object):
    """A convenience store for auto-allocated mininet properties.
    This is *NOT* to be used as IGP graph for a controller application,
    use the graphs reported by the southbound controller instead."""
    def __init__(self, db=None, net=None, *args, **kwargs):
        super(TopologyDB, self).__init__(*args, **kwargs)
        """
        dict keyed by node name ->
            dict keyed by - properties -> val
                          - neighbor   -> interface properties
        """
        self.network = {}
        if db:
            self.load(db)
        if net:
            # self.parse_net(net)
            self.network = net

    def load(self, fpath):
        """Load a topology database from the given filename"""
        with open(fpath, 'r') as f:
            self.network = json.load(f)

    def save(self, fpath):
        """Save the topology database to the given filename"""
        with open(fpath, 'w') as f:
            json.dump(self.network, f)

    def _interface(self, x, y):
        return self.network[x][y]

    def interface(self, x, y):
        """Return the ip_interface for node x facing node y"""
        return ip_interface(self._interface(x, y)['ip'])

    def interface_bandwidth(self, x, y):
        """Return the bandwidth capacity of the interface on node x
        facing node y. If it is unlimited, return -1"""
        return self._interface(x, y)['bw']

    def subnet(self, x, y):
        """Return the subnet linking node x and y"""
        return self.interface(x, y).network.with_prefixlen

    def routerid(self, x):
        """Return the OSPF router id for node named x"""
        n = self.network[x]
        if n['type'] != 'router':
            raise TypeError('%s is not a router' % x)
        return n['routerid']

    def interfaceIP(self,router,interface):
        """
        Returns the interface IP of a routers
        :param router:
        :param switch:
        :return:
        """
        return self._interface(router,interface)['ip'].split("/")[0]

    def type(self,node):
        return self.network[node]['type']

    def parse_net(self, net):
        """Stores the content of the given network"""
        for h in net.hosts:
            self.add_host(h)
        for s in net.switches:
            self.add_switch(s)
        for r in net.routers:
            self.add_router(r)
        for c in net.controllers:
            self.add_controller(c)

    def _add_node(self, n, props):
        """Register a network node"""
        for itf in n.intfList():
            nh = otherIntf(itf)
            if not nh:
                continue  # Skip loopback and the likes
            props[nh.node.name] = {
                'ip': '%s/%s' % (itf.ip, itf.prefixLen),
                'name': itf.name,
                'bw': itf.params.get('bw', -1)
            }
        self.network[n.name] = props

    def add_host(self, n):
        """Register an host"""
        self._add_node(n, {'type': 'host'})

    def add_controller(self, n):
        """Register an controller"""
        self._add_node(n, {'type': 'controller'})

    def add_switch(self, n):
        """Register an switch"""
        self._add_node(n, {'type': 'switch'})

    def add_router(self, n):
        """Register an router"""
        self._add_node(n, {'type': 'router',
                           'routerid': n.id})
