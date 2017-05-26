#!/usr/bin/env python3

from route import *
import copy, random
from util.helper.Quagga import *
from util.helper import *
import subprocess
LOOPBACKPORT = -1

def normalize(name):
	if len(name) > 12:
		return name[-12:]
	return name

class Intf(object) :
	"""
		Obj representing a IPv6 interface
	"""
	def __init__(self, name, port,addr, **params) :
		self.name = name
		self.port = port
		self.addr = addr
		if 'cost' not in params :
			self.cost = 10
		else :
			self.cost = int(params.get('cost'))
		if 'hello-interval' not in params :
			self.hello_interval = 10
		else :
			self.hello_interval = int(params.get('hello-interval'))

		if 'dead-interval' not in params :
			self.dead_interval = 40
		else :
			self.dead_interval = int(params.get('dead-interval'))

		if 'area' not in params :
			self.area = '0.0.0.0'
		else :
			self.area = str(params.get('area'))

		self.neighbor_edge = None

		assert self.dead_interval > self.hello_interval,\
		'dead interval must be greater than hello interval, for %s' % self.name

	def set_cost(self,cost) :
		self.cost = cost

	def set_hello_dead_int(self, hello, dead) :
		self.hello_interval = hello
		self.dead_interval = dead

	def set_neighbor_edge(self, neigh) :
		self.neighbor_edge = neigh

	def get_addr(self) :
		"""
			return address without prefix
		"""
		return self.addr.split('/')[0]

class Node(object):
	def __init__(self, name):
		self.name = name
		self.cur_intf = 0
		self.intfs = []
		self.intfs_addr = {}
		self.addr = None

		self.routes = {}

	def add_route(self, r):
		if r.dst not in self.routes.keys():
			self.routes[r.dst] = [r]
		else:
			self.routes[r.dst].append(r)

	def loopback(self) :
		return self.addr.split('/')[0]

	def add_intf(self, intf):
		self.intfs.append(intf)

	def new_intf(self):
		i = self.cur_intf
		self.cur_intf += 1
		return i

	def get_portaddr(self, intf):
		return self.intfs_addr[intf].split("/")[0]

	def cmd_process(self,cmd) :
		"""
			run the command <cmd> in the namespace of
            this node
		"""
		return run_process(IPNETNSEXEC % (self.name,cmd))

	def cmd_os(self, cmd) :
		"""
			run the command <cmd> in the namespace of
            this node
		"""
		runOS(IPNETNSEXEC % (self.name,cmd))


	def __hash__(self):
		return self.name.__hash__()

	def __eq__(self, o):
		return self.name == o.name

class Host(Node) :
	"""
		A Host is a node
	"""
	def __init__(self, name) :
		self.opp_intf = None
		super(Host, self).__init__(name)
		self.lo_temp = None

	def setup_default_route(self) :
		"""
			set up a default route
		"""

		self.cmd_os('ip -6 ro ad default via %s' % self.opp_intf)
		self.addr = self.lo_temp

	def set_opposite_intf(self, intf) :
		"""
		"""
		self.opp_intf = intf.split('/')[0]

	def set_loopback(self,lo) :
		"""
			Override loopback by the
			link IP address
		"""
		self.lo_temp = lo


class Router(Node) :
	"""
		A router is Node
	"""
	def __init__(self, name,addr, **params) :
		self.intfs_name = {}
		if 'router-id' in params :
			self.router_id = params.get('router-id')
		else :
			self.router_id = None

		super(Router, self).__init__(name)
		# setup loopback
		self.intfs_name['lo'] = Intf('lo',LOOPBACKPORT,addr,**params)
		self.addr = addr
		self.quagga_router = None

	def add_ospf_intf(self, intf,ip, **params) :
		"""
			Override : add a OSPF interface
		"""
		name = '%s-%d' % (self.name, intf)
		self.intfs_name[name] = Intf(name, intf,ip, **params)
		return name

	def build_quagga_router(self,subrouter=QuaggaRouter) :
		"""
			Build the corresponding quagga router
		"""
		self.quagga_router = subrouter(self)


class Controller(Router) :
	"""
		Controller is a Router
	"""
	pass

class Edge(object):
	def __init__(self, node1, node2, port1, port2, cost, delay, bw):
		self.node1 = node1
		self.node2 = node2
		self.port1 = port1
		self.port2 = port2
		self.cost = cost
		self.delay = delay
		self.bw = bw

	def equal(self, n1, n2) :
		"""
			evaluate if this edge is bewteen n1 and n2 (as string)
		"""
		return (self.node1.name == n1 and self.node2.name == n2) or\
		(self.node1.name == n2 and self.node2.name == n1)

	def shutdown(self):
		"""
			shutdown this edge
		"""
		intf1 = '%s-%d' % (self.node1.name, self.port1)
		intf2 = '%s-%d' % (self.node2.name, self.port2)
		self.node1.cmd_os(LINKDOWN % intf1)
		self.node2.cmd_os(LINKDOWN % intf2)

	def restart(self) :
		"""
			restart this edge (after a shutdown)
		"""
		intf1 = '%s-%d' % (self.node1.name, self.port1)
		intf2 = '%s-%d' % (self.node2.name, self.port2)
		self.node1.cmd_os(LINKUP % intf1)
		self.node2.cmd_os(LINKUP % intf2)


	def __eq__(self, o) :
		return self.node1 == o.node1 and\
		self.node2 == o.node2 and\
		self.port1 == o.port1 and\
		self.port2 == o.port2 and\
		self.cost == o.cost and\
		self.delay == o.delay and\
		self.bw == o.bw

class OSPFEdge(Edge):
	def __init__(self, node1, node2, port1, port2, cost, delay, bw, directed=None, cost1=None, cost2=None):
		super(OSPFEdge, self).__init__(node1, node2, port1, port2, cost, delay, bw)
		self.directed = False
		self.cost1 = cost1
		self.cost2 = cost2

		if directed :
			assert cost1 and cost2, 'Must have cost'
			self.directed = True


class Topo(object):
	def __init__(self, config):
		self.nodes = set()
		self.edges = list()
		self.dmin = 0
		self.dmax = 0
		self.config = config
		self.controller = None

	def copy(self):
		t = Topo()
		t.nodes = copy.deepcopy(self.nodes)
		t.edges = copy.deepcopy(self.edges)

		for e in t.edges:
			e.node1 = t.get_node(e.node1.name)
			e.node2 = t.get_node(e.node2.name)

		return t

	def copy_unit(self):
		t = self.copy()

		for e in t.edges:
			e.cost = 1

		t.compute()
		return t

	def build(self):
		pass

	def add_node(self, name):
		n = Node(normalize(name))
		self.nodes.add(n)
		return n

	def get_node(self, name):
		for n in self.nodes:
			if n.name == normalize(name):
				return n

		return None

	def get_loopback_by_name(self, name) :
		"""
			return the loopback addr of the node with
			name = <name>
		"""
		node = self.get_node(name)
		return node.addr.split('/')[0]

	def add_router(self, name,loaddr, **params) :
		r = Router(normalize(name),loaddr, **params)
		self.nodes.add(r)
		return r

	def add_host(self, name) :
		h = Host(normalize(name))
		self.nodes.add(h)
		return h

	def add_controller(self, name,loaddr, **params) :
		c = Controller(normalize(name),loaddr, **params)
		self.nodes.add(c)
		self.controller = c
		return c

	def add_link(self, node1, node2,ip1, ip2,
			port1=None, port2=None, cost=1, delay=None, bw=None):
		if port1 is None:
			port1 = node1.new_intf()
		if port2 is None:
			port2 = node2.new_intf()

		node1.add_intf(port1)
		node2.add_intf(port2)

		node1.intfs_addr[port1] = ip1
		node2.intfs_addr[port2] = ip2
		if isinstance(node1, Host) :
			node1.set_loopback(ip1)
		if isinstance(node2, Host) :
			node2.set_loopback(node2, ip2)


		if delay is None:
			delay = random.uniform(self.dmin, self.dmax)

		e = Edge(node1, node2, port1, port2, int(cost), delay, bw)
		self.edges.append(e)
		return e

	def add_link_directed(self, node1, node2,ip1, ip2,
			port1=None, port2=None, cost=1, delay=None, bw=None,
			directed=None, cost1=None, cost2=None):
		if port1 is None:
			port1 = node1.new_intf()
		if port2 is None:
			port2 = node2.new_intf()

		node1.add_intf(port1)
		node2.add_intf(port2)

		node1.intfs_addr[port1] = ip1
		node2.intfs_addr[port2] = ip2
		if isinstance(node1, Host) :
			node1.set_loopback(ip1)
		if isinstance(node2, Host) :
			node2.set_loopback(node2, ip2)


		if delay is None:
			delay = random.uniform(self.dmin, self.dmax)
		if directed :
			e = OSPFEdge(node1, node2, port1, port2, int(cost), delay, bw, directed=directed,cost1=cost1, cost2=cost2 )
		else:
			e = OSPFEdge(node1, node2, port1, port2, int(cost), delay, bw)
		self.edges.append(e)
		return e

	def add_ospf_link(self, router1, router2,
						ip1, ip2,
						port1=None, port2=None,
						cost=1, delay=None, bw=None,
						directed=None, cost1=None, cost2=None,
						**params ) :
		"""
			Add a OSPF link and configure the two interfaces
		"""
		assert isinstance(router1, Router), 'router1 is not a OSPF Router'
		assert isinstance(router2, Router), 'router2 is not a OSPF Router'

		e = self.add_link_directed(router1, router2,ip1,ip2,port1, port2,cost, delay, bw,directed=directed, cost1=cost1, cost2=cost2)
		param1 = params.get('params1', {})
		param2 = params.get('params2', {})

		p1 = port1
		if not port1 :
			p1 = router1.cur_intf -1
		p2 = port2
		if not port2 :
			p2 = router2.cur_intf -1
		name2 = router2.add_ospf_intf(p2,ip2, **param2)
		router2.intfs_name[name2].set_neighbor_edge(e)

		name1 = router1.add_ospf_intf(p1,ip1, **param1)
		router1.intfs_name[name1].set_neighbor_edge(e)

		return e


	def add_link_name(self, name1, name2, *args, **kwargs):
		return self.add_link(self.get_node(name1), self.get_node(name2), *args, **kwargs)

	def get_edges(self, node1, node2):
		res = []

		for e in self.edges:
			if e.node1 == node1 and e.node2 == node2 or e.node1 == node2 and e.node2 == node1:
				res.append(e)

		return res

	def get_minimal_edge_cost(self, edges):
		cost = 2**32
		for e in edges:
			if e.cost < cost:
				cost = e.cost
		return cost

	def get_all_minimal_edges(self, node1, node2):
		edges = self.get_edges(node1, node2)
		cost = self.get_minimal_edge_cost(edges)
		res = []

		for e in edges:
			if e.cost == cost:
				res.append(e)

		return res

	def get_minimal_edge(self, node1, node2):
		edges = self.get_all_minimal_edges(node1, node2)

		if len(edges) == 0:
			return None

		return edges[0]

	def get_neighbors(self, node1):
		res = set()

		for e in self.edges:
			if e.node1 == node1:
				res.add(e.node2)
			elif e.node2 == node1:
				res.add(e.node1)

		return res

	def set_default_delay(self, dmin, dmax):
		self.dmin = dmin
		self.dmax = dmax



	def get_paths(self, Q, S, prev, u):
		w = prev[u]

		if w is None:
			Q.append(S)
			return

		S.append(u)

		for p in w:
			self.get_paths(Q, S[:], prev, p)

	def dijkstra(self, src):
		dist = {}
		prev = {}
		path = {}
		Q = set()

		dist[src] = 0
		prev[src] = None

		for v in self.nodes:
			if v != src:
				dist[v] = 2**32
				prev[v] = []
				path[v] = []
			Q.add(v)

		while len(Q) > 0:
			u = None
			tmpcost = 2**32
			for v in Q:
				if dist[v] < tmpcost:
					tmpcost = dist[v]
					u = v

			S = []
			path[u] = []

			self.get_paths(S, [], prev, u)
			for p in S:
				path[u].append(list(reversed(p)))

			Q.remove(u)

			neighs = self.get_neighbors(u)
			for v in neighs:
				if v not in Q:
					continue
				alt = dist[u] + self.get_minimal_edge(u, v).cost
				if alt < dist[v]:
					dist[v] = alt
					prev[v] = [u]
				elif alt == dist[v]:
					prev[v].append(u)

		return dist, path

	def get_port(self, n, e):
		if e.node1 == n:
			return e.port1
		if e.node2 == n:
			return e.port2
		return None

	def get_nh_from_paths(self, paths):
		nh = []
		for p in paths:
			if len(p) == 0:
				continue
			if p[0] not in nh:
				nh.append(p[0])
		return nh

	def compute_node(self, n):
		n.routes = {}
		dist, path = self.dijkstra(n)
		for t in dist.keys():
			if len(path[t]) == 0:
				continue
			nh = self.get_nh_from_paths(path[t])
			for p in nh:
				e = self.get_minimal_edge(n, p)
				tmp = self.get_port(p, e)
				r = Route(t.addr, p.get_portaddr(tmp), dist[t])
				n.add_route(r)

	def compute(self):
		cnt = 0
		for n in self.nodes:
			print '# Running dijkstra for node %s (%d/%d)' % (n.name, cnt+1, len(self.nodes))
			self.compute_node(n)
			cnt += 1
