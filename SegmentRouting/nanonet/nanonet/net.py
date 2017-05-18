#!/usr/bin/env python

from addr import *
from route import *
import socket, os, sys
import pickle

class Nanonet(object):
	def __init__(self, topo, linknet=None, loopnet=None,mask=32,submask=64):
		self.topo = topo
		self.orig_topo = topo

		if linknet is None:
			linknet = V6Net('fc00:42::', mask, submask)

		if loopnet is None:
			loopnet = V6Net('fc00:2::', mask, submask)

		self.linknet = linknet
		self.loopnet = loopnet
	@staticmethod
	def load(fname):
		f = open(fname, 'r')
		obj = pickle.load(f)
		f.close()
		return obj

	def assign(self):
		count = 0
		# for e in self.topo.edges:
		# 	enet = self.linknet.next_net()
		# 	a1 = enet[:]
		# 	a2 = enet[:]
		# 	a1[-1] = 1
		# 	a2[-1] = 2

			# print 'Assigning %s - %s' % (socket.inet_ntop(socket.AF_INET6, str(a1)), socket.inet_ntop(socket.AF_INET6, str(a2)))
			# print 'With submask %d' % self.linknet.submask
			# print e.port1
			# print e.port2
			# print 'For port1 %d and port2 %d' % (e.port1, e.port2)

		for n in self.topo.nodes:
			enet = self.loopnet.next_net()
			enet[-1] = 1

			n.addr = socket.inet_ntop(socket.AF_INET6, str(enet))+'/'+str(self.loopnet.submask)

	def start(self, netname=None):
		# print '# Building topology...'
		self.topo.build()

		# print '# Assigning prefixes...'
		# self.assign()

		# print '# Running dijkstra... (%d nodes)' % len(self.topo.nodes)
		# self.topo.compute()

		if netname is not None:
			f = open(netname, 'w')
			pickle.dump(self, f)
			f.close()

	def call(self, cmd):
		sys.stdout.write('%s\n' % cmd)

	def dump_commands(self, wr=(lambda x: self.call(x)), noroute=False):
		host_cmd = []
		node_cmd = {}

		for n in self.topo.nodes:
			host_cmd.append('ip netns add %s' % n.name)
			node_cmd[n] = []
			node_cmd[n].append('ifconfig lo up')
			node_cmd[n].append('ip -6 ad ad %s dev lo' % n.addr)
			node_cmd[n].append('sysctl net.ipv6.conf.all.forwarding=1')
			node_cmd[n].append('sysctl net.ipv6.conf.all.seg6_enabled=1')

		for e in self.topo.edges:
			dev1 = '%s-%d' % (e.node1.name, e.port1)
			dev2 = '%s-%d' % (e.node2.name, e.port2)

			host_cmd.append('ip link add name %s type veth peer name %s' % (dev1, dev2))
			host_cmd.append('ip link set %s netns %s' % (dev1, e.node1.name))
			host_cmd.append('ip link set %s netns %s' % (dev2, e.node2.name))
			node_cmd[e.node1].append('ifconfig %s add %s up' % (dev1, e.node1.intfs_addr[e.port1]))
			node_cmd[e.node1].append('sysctl net.ipv6.conf.%s.seg6_enabled=1' % (dev1))
			node_cmd[e.node2].append('ifconfig %s add %s up' % (dev2, e.node2.intfs_addr[e.port2]))
			node_cmd[e.node2].append('sysctl net.ipv6.conf.%s.seg6_enabled=1' % (dev2))
			if e.delay > 0 and e.bw == 0:
				node_cmd[e.node1].append('tc qdisc add dev %s root handle 1: netem delay %.2fms' % (dev1, e.delay))
				node_cmd[e.node2].append('tc qdisc add dev %s root handle 1: netem delay %.2fms' % (dev2, e.delay))
			elif e.bw > 0:
				node_cmd[e.node1].append('tc qdisc add dev %s root handle 1: htb' % (dev1))
				node_cmd[e.node1].append('tc class add dev %s parent 1: classid 1:1 htb rate %dkbit ceil %dkbit' % (dev1, e.bw, e.bw))
				node_cmd[e.node1].append('tc filter add dev %s protocol ipv6 parent 1: prio 1 u32 match ip6 dst ::/0 flowid 1:1' % (dev1))
				node_cmd[e.node2].append('tc qdisc add dev %s root handle 1: htb' % (dev2))
				node_cmd[e.node2].append('tc class add dev %s parent 1: classid 1:1 htb rate %dkbit ceil %dkbit' % (dev2, e.bw, e.bw))
				node_cmd[e.node2].append('tc filter add dev %s protocol ipv6 parent 1: prio 1 u32 match ip6 dst ::/0 flowid 1:1' % (dev2))
				if e.delay > 0:
					node_cmd[e.node1].append('tc qdisc add dev %s parent 1:1 handle 10: netem delay %.2fms' % (dev1, e.delay))
					node_cmd[e.node2].append('tc qdisc add dev %s parent 1:1 handle 10: netem delay %.2fms' % (dev2, e.delay))

		if not noroute:
			for n in self.topo.nodes:
				for dst in n.routes.keys():
					rts = n.routes[dst]
					laddr = n.addr.split('/')[0]
					if len(rts) == 1:
						r = rts[0]
						node_cmd[n].append('ip -6 ro ad %s via %s metric %d src %s' % (r.dst, r.nh, r.cost, laddr))
					else:
						allnh = ''
						for r in rts:
							allnh += 'nexthop via %s weight 1 ' % (r.nh)
						node_cmd[n].append('ip -6 ro ad %s metric %d src %s %s' % (r.dst, r.cost, laddr, allnh))

		for c in host_cmd:
			wr('%s' % c)

		for n in node_cmd.keys():
			wr('ip netns exec %s bash -c \'%s\'' % (n.name, "; ".join(node_cmd[n])))

	def igp_prepare_link_down(self, name1, name2):
		t = self.topo.copy()

		edge = t.get_minimal_edge(t.get_node(name1), t.get_node(name2))
		t.edges.remove(edge)
		t.compute()

		rm_routes = {}
		chg_routes = {}
		for n in self.topo.nodes:
			n2 = t.get_node(n.name)
			rm_routes[n2] = []
			chg_routes[n2] = []

			for r in n.routes:
				if r not in n2.routes:
					rm_routes[n2].append(r)
					continue
				r2 = n2.routes[n2.routes.index(r)]
				if r.nh != r2.nh or r.cost != r2.cost:
					chg_routes[n2].append(r2)

		return (t, edge, rm_routes, chg_routes)

#		for n in rm_routes.keys():
#			print '# Removed routes for node %s:' % n.name
#			for r in rm_routes[n]:
#				print '# %s via %s metric %d' % (r.dst, r.nh, r.cost)
#		for n in chg_routes.keys():
#			print '# Changed routes for node %s:' % n.name
#			for r in chg_routes[n]:
#				print '# %s via %s metric %d' % (r.dst, r.nh, r.cost)

	def igp_apply_link_down(self, edge, rm_routes, chg_routes, timer=50):
		n1, n2 = edge.node1, edge.node2

		S = set()
		Q = set(self.topo.nodes)
		visited = set()
		S.add(n1)
		S.add(n2)

		# shut down interfaces
		self.call('ip netns exec %s ifconfig %s-%d down' % (n1.name, n1.name, edge.port1))
		self.call('ip netns exec %s ifconfig %s-%d down' % (n2.name, n2.name, edge.port2))

		while len(Q) > 0:
			S2 = set()
			self.call('sleep %f' % (timer/1000.0))
			for n in S:
				for r in rm_routes[n]:
					self.call('ip netns exec %s ip -6 ro del %s' % (n.name, r.dst))
				for r in chg_routes[n]:
					self.call('ip netns exec %s ip -6 ro replace %s via %s metric %d' % (n.name, r.dst, r.nh, r.cost))
				visited.add(n)
				S2.update(self.topo.get_neighbors(n))
				S2.difference_update(visited)
				Q.remove(n)
			S = S2

	def apply_topo(self, t):
		self.topo = t
