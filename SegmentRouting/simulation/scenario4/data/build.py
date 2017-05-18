from autotopoSR.topo import *
from autotopoSR.util import *
from autotopoSR.net import *

import os
buildpath = os.path.dirname(__file__)

class Test(Topo) :
    def build(self) :

        self.add_link_by_name('A', 'B', True, cost=1,bw=1000)
        self.add_link_by_name('B', 'C', True, cost=1,bw=1000)

        self.add_link_by_name('A', 'D', True, cost=2,bw=1000)
        self.add_link_by_name('D', 'C', True, cost=2,bw=1000)

        self.add_link_by_name('A', 'E', True, cost=4,bw=1000)
        self.add_link_by_name('E', 'C', True, cost=4,bw=1000)


        self.add_link_by_name('Dst', 'C', True, cost=100,bw=1000)
        self.add_link_by_name('Ctrl', 'A', True, cost=100,bw=1000)



        self.set_destination('Dst')
        self.set_controller('Ctrl')



class Simulation(SimulationSchedule) :
    def build_requirement(self):
        # configuring a simple requirement
        Req1 = Requirement('Dst',  ['A' , 'E', 'C'], name='AtoC')
        Req1.set_state(SCHED)
        Req1.set_type(SCHEDBW)

        link =  ReqLink('A', 'B')
        link.set_bw(45)
        Req1.set_link(link)
        Req1.set_start_time('10:30')
        Req1.set_end_time('23:30')
        Req1.set_days([MONDAY, TUESDAY,WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY])
        self.add_requirement(Req1)

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
