from autotopoSR.topo import *
from autotopoSR.util import *
from autotopoSR.net import *

import os
buildpath = os.path.dirname(__file__)

class Test(Topo) :
    def build(self) :
        self.add_link_by_name('NEWY', 'CHIC', True, cost=1)
        self.add_link_by_name('LOSA', 'HOUS', True, cost=1)
        self.add_link_by_name('LOSA', 'SEAT', True, cost=1)
        self.add_link_by_name('LOSA', 'SALT', True, cost=1)
        self.add_link_by_name('SEAT', 'SALT', True, cost=1)
        self.add_link_by_name('SALT', 'KANS', True, cost=1)
        self.add_link_by_name('KANS', 'CHIC', True, cost=1)
        self.add_link_by_name('CHIC', 'WASH', True, cost=1)
        self.add_link_by_name('NEWY', 'WASH', True, cost=1)
        self.add_link_by_name('WASH', 'ATLA', True, cost=1)
        self.add_link_by_name('ATLA', 'HOUS', True, cost=1)
        self.add_link_by_name('HOUS', 'KANS', True, cost=1)


        self.add_link_by_name('Ctrl', 'HOUS', True, cost=1)

        self.add_link_by_name('Hawaii', 'LOSA', True)
        self.add_link_by_name('Sidney', 'LOSA', True)
        self.add_link_by_name('China', 'SEAT', True)
        self.add_link_by_name('London', 'NEWY', True)
        self.add_link_by_name('Amst', 'ATLA', True)


        self.set_destination('Hawaii')
        self.set_destination('Sidney')
        self.set_controller('China')


class Simulation(SimulationSchedule) :
    def build_requirement(self):
        # configuring a simple requirement
        Req1 = Requirement('Hawaii',  ['NEWY' , 'CHIC', '*', 'LOSA'])
        Req1.set_state(RUNNNING)
        self.add_requirement(Req1)

        Req2 = Requirement('Sidney',  ['NEWY' ,  '*', 'LOSA'])
        Req2.set_state(SCHED)
        Req2.set_type(SCHEDTIME)
        Req2.set_start_time('10:00')
        Req2.set_end_time('23:30')
        Req2.set_days([MONDAY, TUESDAY,WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY])
        self.add_requirement(Req2)



        # finish the set of requiremnt for this timestamp
        self.next_timestamp()

        Req3 = Requirement('Hawaii',  ['ATLA' ,  '*', 'LOSA'])
        Req3.set_state(RUNNNING)
        self.add_requirement(Req3)


        # configuring a path with *
        Req4 = Requirement('Sidney',  ['NEWY' ,  '*', 'LOSA'])
        Req4.set_state(SCHED)
        Req4.set_type(SCHEDBW)
        Req4.set_start_time('10:00')
        Req4.set_end_time('23:30')
        Req4.set_days([MONDAY, TUESDAY,WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY])

        # configuring link with bw at 50%
        link =  ReqLink('ATLA', 'HOUS')
        link.set_bw(50)
        Req4.set_link(link)
        self.add_requirement(Req4)

        Req5 = Requirement('Sidney', ['NEWY' ,  '*', 'LOSA'])
        Req5.set_state(SCHED)
        Req5.set_type(SCHEDBACKUP)
        Req5.set_start_time('10:00')
        Req5.set_end_time('23:30')
        Req5.set_days([MONDAY, TUESDAY,WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY])

        # configuring link with bw at 50%
        link =  ReqLink('ATLA', 'HOUS')
        Req5.set_link(link)
        self.add_requirement(Req5)


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
