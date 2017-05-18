#!/usr/bin/env python

from node import *
from net import *

class Test(Topo):
	def build(self):
		self.add_node("A")
		self.add_node("B")
		self.add_node("C")
		self.add_link_name("A", "B", cost=1, delay=3, bw=1)
		self.add_link_name("A", "C", cost=1, delay=3, bw=1)
		self.add_link_name("B", "C", cost=1, delay=3, bw=1)
topos = { 'Test': (lambda: Test()) }
