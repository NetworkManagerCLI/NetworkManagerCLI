from autotopoSR.topo import *
from autotopoSR.util import *
from autotopoSR.net import *

import os
buildpath = os.path.dirname(__file__)

class Test(Topo) :
    def build(self) :
        # adding the network routers
        #                     src     dest    ospf       cost
        self.add_link_by_name('NEWY', 'CHIC', True, cost=1000)
        self.add_link_by_name('LOSA', 'HOUS', True, cost=1705)
        self.add_link_by_name('LOSA', 'SEAT', True, cost=1342)
        self.add_link_by_name('LOSA', 'SALT', True, cost=1303)
        self.add_link_by_name('SEAT', 'SALT', True, cost=913)
        self.add_link_by_name('SALT', 'KANS', True, cost=1330)
        self.add_link_by_name('KANS', 'CHIC', True, cost=690)
        self.add_link_by_name('CHIC', 'WASH', True, cost=905)
        self.add_link_by_name('NEWY', 'WASH', True, cost=278)
        self.add_link_by_name('WASH', 'ATLA', True, cost=700)
        self.add_link_by_name('CHIC', 'ATLA', True, cost=1045)
        self.add_link_by_name('ATLA', 'HOUS', True, cost=1385)
        self.add_link_by_name('HOUS', 'KANS', True, cost=818)

        # adding main controller
        # NB: the main controller is a routers
        self.add_link_by_name('Ctrl', 'HOUS', True,cost=100)

        # adding destinations
        # NB: destinations are simply routers for the sake
        # of simplicity
        self.add_link_by_name('Hawaii', 'LOSA', True)
        self.add_link_by_name('Sidney', 'LOSA', True)
        self.add_link_by_name('China', 'SEAT', True)
        self.add_link_by_name('London', 'NEWY', True)
        self.add_link_by_name('Amst', 'ATLA', True)

        # specify which of the routers will
        # act as destinations
        self.set_destination('Hawaii')
        self.set_destination('Sidney')
        # specify which one of the router will
        # act as main-controller
        self.set_controller('Ctrl')


class Simulation(SimulationSchedule) :
    def build_requirement(self):
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
    print '*** Generating Netconf file ***'
    net.gen_topo_xml(filename)

    sim = Simulation(buildpath)
    print '*** Creating the Simulation schedule ***'
    sim.build_requirement()
    print '*** Generating Simulation Netconf file ***'
    sim.gen_schedule_xml()
