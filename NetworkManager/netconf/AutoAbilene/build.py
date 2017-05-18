from autotopofib.net import *
from autotopofib.topo import *
from autotopofib.util import *
import sys

import os
buildpath = os.path.dirname(__file__)

class Test(Topo) :
    def build(self) :
        # Link of the network (speficied with OSPF_LINK)
        #                       src    dest      type    cost   bw
        self.add_edge_by_type('LOSA', 'SEAT', OSPF_LINK, 1342, 100)
        self.add_edge_by_type('LOSA', 'SALT', OSPF_LINK, 1303, 100)
        self.add_edge_by_type('SEAT','SALT', OSPF_LINK, 913, 100)
        self.add_edge_by_type('SALT', 'KANS', OSPF_LINK, 1330, 100)
        self.add_edge_by_type('KANS', 'CHIC', OSPF_LINK, 690, 100)
        self.add_edge_by_type('CHIC', 'NEWY', OSPF_LINK, 1000, 100)
        self.add_edge_by_type('NEWY', 'WASH', OSPF_LINK, 278, 100)
        self.add_edge_by_type('WASH', 'ATLA', OSPF_LINK, 700, 100)
        self.add_edge_by_type('ATLA', 'HOUS', OSPF_LINK, 1385, 100)
        self.add_edge_by_type('HOUS', 'LOSA', OSPF_LINK, 1705, 100)
        self.add_edge_by_type('WASH', 'CHIC', OSPF_LINK, 905, 100)
        self.add_edge_by_type('ATLA', 'CHIC', OSPF_LINK, 1045, 100)
        self.add_edge_by_type('HOUS', 'KANS', OSPF_LINK, 818, 100)

        # adding some destinations
        #                       dest     edge
        #                       name    router    type
        self.add_edge_by_type('Hawaii', 'LOSA', DEST_LINK)
        self.add_edge_by_type('Sidney', 'LOSA', DEST_LINK)
        self.add_edge_by_type('China', 'SEAT', DEST_LINK)
        self.add_edge_by_type('London', 'NEWY', DEST_LINK)
        self.add_edge_by_type('Amst', 'ATLA', DEST_LINK)

        # adding the main controller
        # NB: the main controller is specified as a host (DEST_LINK)
        #                 main-ctrl    router   type
        self.add_edge_by_type('Ctrl', 'HOUS', DEST_LINK)
        # then specified which one of the hosts will act as the
        # main-controller
        self.specify_main_controller('Ctrl')

        # adding a Fibbing controller
        #                     ctrl   router   type
        self.add_edge_by_type('C1', 'HOUS', CTRL_LINK)





class Simulation(SimulationSchedule) :
    def build_requirement(self):
        # configuring a simple requirement
        # configuring a simple requirement
        Req1 = Requirement('Hawaii',  ['NEWY' , 'CHIC', 'KANS','SALT', 'LOSA'])
        Req1.set_state(RUNNING)
        self.add_requirement(Req1)

        Req2 = Requirement('Sidney',  ['ATLA' , '*' , 'LOSA'])
        Req2.set_state(SCHED)
        Req2.set_type(SCHEDTIME)
        Req2.set_start_time('10:00')
        Req2.set_end_time('23:30')
        Req2.set_days([MONDAY, TUESDAY,WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY])
        self.add_requirement(Req2)




if __name__ == '__main__':
    filename = 'netconf-topo.xml'


    print '*** Creating the topology ***'
    net = Network(Test(), buildpath)
    print '*** Assigning IP addresses ***'
    net.assign()

    print '*** Generating Topo Netconf file ***'
    net.gen_topo_xml(filename)

    sim = Simulation(buildpath)
    print '*** Creating the Simulation schedule ***'
    sim.build_requirement()
    print '*** Generating Simulation Netconf file ***'
    sim.gen_schedule_xml()
