from autotopoSR.topo import *
from autotopoSR.util import *
from autotopoSR.net import *

import os
buildpath = os.path.dirname(__file__)

class Test(Topo) :
    def build(self) :

        self.add_link_by_name('A', 'B', True, cost=10)
        self.add_link_by_name('A', 'C', True, cost=1)
        self.add_link_by_name('C', 'D', True, cost=1)
        self.add_link_by_name('B', 'D', True, cost=1)

        self.add_link_by_name('F', 'H', True, cost=10)
        self.add_link_by_name('F', 'E', True, cost=1)
        self.add_link_by_name('E', 'G', True, cost=1)
        self.add_link_by_name('H', 'G', True, cost=1)

        self.add_link_by_name('D', 'E', True, cost=1)

        self.add_link_by_name('Src2', 'A', True, cost=1)
        self.add_link_by_name('Dst2', 'D', True, cost=1)
        self.add_link_by_name('Src1', 'G', True, cost=1)
        self.add_link_by_name('Dst1', 'F', True, cost=1)



        self.add_link_by_name('Ctrl', 'C', True, cost=100)



        self.set_destination('Dst1')
        self.set_destination('Dst2')
        self.set_controller('Ctrl')



class Simulation(SimulationSchedule) :
    def build_requirement(self):
        # configuring a simple requirement
        Req1 = Requirement('Dst1', ['G' , 'H', 'F'])
        Req1.set_state(RUNNNING)
        self.add_requirement(Req1)

        Req2 = Requirement('Dst2',  ['A' , 'B', 'D'])
        Req2.set_state(RUNNNING)
        self.add_requirement(Req2)


if __name__ == '__main__':
    filename = 'netconf-topo.xml'

    print '*** Creating the topology ***'
    net = Network(Test(),buildpath)
    print '*** Assigning IP addresses ***'
    net.assign()
    print '*** Generating Netconf file ***'
    net.gen_topo_xml(filename)

    sim = Simulation(buildpath)
    print '*** Creating the Simulation schedule ***'
    sim.build_requirement()
    print '*** Generating Simulation Netconf file ***'
    sim.gen_schedule_xml()
