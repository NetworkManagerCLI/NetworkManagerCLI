from autotopoSR.util import *
from autotopoSR.topo import *
from autotopoSR.addr import *
from autotopoSR import *
from mako.template import Template
import os


def render(filename, node, dest) :
    text = Template(filename=filename).render(topo=node)
    with open(dest, 'w') as f:
        f.write(text)
        f.close()


class Network(ConfigDict) :
    def __init__(self, topo, dirname, mask=32, submask=64) :
        assert isinstance(topo, Topo), "topo must be a Topo"
        self.topo = topo
        self.topo.build()
        self.mask = mask
        self.submask = submask

        self.dirname = dirname

        self.link_pfx = 'fc00:10::'
        self.dest_pfx = 'fc00:42::'
        self.ctrl_pfx = 'fc12:12::'
        self.router_pfx = 'fc00:23::'

        self.linknet = V6Net(self.link_pfx, mask, submask)
        self.routernet = V6Net(self.router_pfx, mask, submask)
        self.ctrlnet = V6Net(self.ctrl_pfx, mask, submask)
        self.destnet = V6Net(self.dest_pfx, mask, submask)
        self.routerid = [0,0,0,1]

    def gen_topo_xml(self, filename):
        render('%s/template.mako' % path, self.topo, '%s/%s' % (self.dirname,filename))

        os.system('cp %s/restore.xml %s/' % (path, self.dirname))

    def print_topo(self) :
        for link in self.topo.links :
            print str(link)


    def assign(self) :
        self.assign_links()
        self.assign_routers()

    def assign_links(self) :
        for edge in self.topo.links :
            tmp_net = self.linknet.next_net()
            src = tmp_net[:]
            dest = tmp_net[:]
            src[-1] = 1
            dest[-1] = 2
            str_src = socket.inet_ntop(socket.AF_INET6, str(src))
            str_dest = socket.inet_ntop(socket.AF_INET6, str(dest))
            edge.set_ips('%s/64' % str_src,'%s/64' %  str_dest)

    def assign_routers(self) :
        for router in self.topo.routers :
            if router.ospf6_enabled :
                router.set_routerid(self.next_routerid())

            if router in self.topo.destinations :
                lo_net = self.destnet.next_net()
                lo = lo_net[:]
                lo[-1] = 1
                str_lo = socket.inet_ntop(socket.AF_INET6, str(lo))
                router.set_loopback( '%s/64' % str_lo)
            elif router == self.topo.controller :
                ctrl_net = self.ctrlnet.next_net()
                ctrl_lo = ctrl_net[:]
                ctrl_lo[-1] = 1
                str_ctrl_lo = socket.inet_ntop(socket.AF_INET6, str(ctrl_lo))
                router.set_loopback('%s/64' % str_ctrl_lo)
            else:
                lo_net = self.routernet.next_net()
                lo = lo_net[:]
                lo[-1] = 1
                str_lo = socket.inet_ntop(socket.AF_INET6, str(lo))
                router.set_loopback('%s/64' %  str_lo)



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
