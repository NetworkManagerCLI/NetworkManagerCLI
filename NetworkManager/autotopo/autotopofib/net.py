from autotopofib.topo import *
from autotopofib.util import *
from autotopofib import *
from mako.template import Template
import os

def render(filename, node, dest) :
    text = Template(filename=filename).render(topo=node)
    with open(dest, 'w') as f:
        f.write(text)
        f.close()

class Network(object):
    def __init__(self, topo, dirname):
        assert isinstance(topo, Topo), "topo must be a Topo"
        self.topo = topo
        self.topo.build()
        self.o_link_pfx = 198
        self.dest_pfx = 192
        self.ctrl_pfx = 168

        self.dirname = dirname

        self.routerid = [0,0,0,1]
        self.ol_link = [0,0]
        self.d_link = [0,0]
        self.c_link = [0,0]

    def gen_topo_xml(self, filename):
        render('%s/template.mako' % path, self.topo, '%s/%s' % (self.dirname, filename))
        os.system('cp %s/restore.xml %s/' % (path, self.dirname))

    def print_net(self) :
        for router in self.topo.ospfrouters :
            print str(router)

        for edge in self.topo.ospflinks :
            print str(edge)

        for edge in self.topo.destinationlink :
            print str(edge)

        print str(self.topo.controllerlink)

    def assign(self):
        self.assign_routerid()
        self.assign_ospf_ips()
        self.assign_dest_ips()
        self.assign_ctrl_ips()

    def assign_routerid(self) :
        for router in self.topo.ospfrouters :
            router.set_routerid(self.next_routerid())

    def assign_ospf_ips(self) :
        for edge in self.topo.ospflinks:
            ip1, ip2 =self.next_o_link_ips()
            edge.set_ips('%s/24' % ip1,'%s/24' % ip2)

    def assign_dest_ips(self) :
        for edge in self.topo.destinationlink:
            ip1, ip2 = self.next_dest_link_ips()
            edge.set_ips('%s/24' % ip1,'%s/24' % ip2)

    def assign_ctrl_ips(self) :
        for edge in self.topo.controllerlink:
            ip1, ip2 = self.next_ctrl_link_ips()
            edge.set_ips('%s/24' % ip1,'%s/24' % ip2)

    def next_dest_link_ips(self):
        self.d_link[1] += 1
        if self.d_link[1] == 255 :
            self.d_link[0] += 1

        assert self.d_link[0] < 255, "Error no enough Destinations link ips"
        a1 = [self.dest_pfx,self.d_link[0], self.d_link[1],1]
        a2 = [self.dest_pfx,self.d_link[0], self.d_link[1],2]

        return self.str_array(a1), self.str_array(a2)

    def next_ctrl_link_ips(self):
        self.c_link[1] += 1
        if self.c_link[1] == 255 :
            self.c_link[0] += 1

        assert self.c_link[0] < 255, "Error no enough Destinations link ips"
        a1 = [self.ctrl_pfx,self.c_link[0], self.c_link[1],1]
        a2 = [self.ctrl_pfx,self.c_link[0], self.c_link[1],2]

        return self.str_array(a1), self.str_array(a2)

    def next_o_link_ips(self):
        self.ol_link[1] += 1
        if self.ol_link[1] == 255 :
            self.ol_link[0] += 1

        assert self.ol_link[0] < 255, "Error no enough OSPF link ips"
        a1 = [self.o_link_pfx,self.ol_link[0], self.ol_link[1],1]
        a2 = [self.o_link_pfx,self.ol_link[0], self.ol_link[1],2]

        return self.str_array(a1), self.str_array(a2)

    def next_routerid(self) :
        self.routerid[3] +=1
        if self.routerid[3] == 255 :
            self.routerid[3] = 0
            self.routerid[2] += 1

        if self.routerid[2] == 255 :
            self.routerid[2] = 0
            self.routerid[1] += 1

        if self.routerid[1] == 255 :
            self.routerid[1] = 0
            self.routerid[0] += 1

        assert self.routerid[0] < 255, "Error no enough routerid"
        return self.str_array(self.routerid)

    def str_array(self, array) :
        return '.'.join(map(str, array))
