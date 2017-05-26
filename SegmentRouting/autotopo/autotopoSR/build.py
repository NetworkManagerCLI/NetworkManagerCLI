from autotopoSR.topo import *
from autotopoSR.util import *
from autotopoSR.net import *

import os
buildpath = os.path.dirname(__file__)

class Test(Topo) :
    """
        API:
        - self.add_edge_by_type(src, dest, OSPF_LINK, cost, bw):
            :src and :dest type string, :cost and :bw (in Kbps) type int
            declare a link with OSPF enabled
        - self.add_edge_by_type(src, dest, DEST_LINK):
            :src and :dest type string
            declare a link between destination (:src attribute) and
            router (:dest attribute)
        - self.set_controller(ctrl):
            :ctrl an existing destination that will act as the main controller

    """
    def build(self) :
        self.add_edge_by_type('NEWY', 'CHIC', OSPF_LINK, cost=1)
        self.add_edge_by_type('LOSA', 'HOUS', OSPF_LINK, cost=1)
        self.add_edge_by_type('LOSA', 'SEAT', OSPF_LINK, cost=1)
        self.add_edge_by_type('LOSA', 'SALT', OSPF_LINK, cost=1)
        self.add_edge_by_type('SEAT', 'SALT', OSPF_LINK, cost=1)
        self.add_edge_by_type('SALT', 'KANS', OSPF_LINK, cost=1)
        self.add_edge_by_type('KANS', 'CHIC', OSPF_LINK, cost=1)
        self.add_edge_by_type('CHIC', 'WASH', OSPF_LINK, cost=1)
        self.add_edge_by_type('NEWY', 'WASH', OSPF_LINK, cost=1)
        self.add_edge_by_type('WASH', 'ATLA', OSPF_LINK, cost=1)
        self.add_edge_by_type('ATLA', 'HOUS', OSPF_LINK, cost=1)
        self.add_edge_by_type('HOUS', 'KANS', OSPF_LINK, cost=1)


        self.add_edge_by_type('Ctrl', 'HOUS', OSPF_LINK)

        self.add_edge_by_type('Hawaii', 'LOSA', DEST_LINK)
        self.add_edge_by_type('Sidney', 'LOSA', DEST_LINK)
        self.add_edge_by_type('China', 'SEAT', DEST_LINK)
        self.add_edge_by_type('London', 'NEWY', DEST_LINK)
        self.add_edge_by_type('Amst', 'ATLA', DEST_LINK)



        self.set_controller('Ctrl')


class Simulation(SimulationSchedule) :
    """
        API:
        - Requirement(dest,  Path):
            :dest type string, :Path type array of string
            create a simple requirement for destinations :dest and
            with Path :Path (can use the * router in the Path)
        - Requirement.set_state(state):
            :state global variale
            and must be included in [RUNNING, NOTRUNNING, SCHED]
        - Requirement.set_type(type)
            :type global variale and must be included
            in [SCHEDTIME, SCHEDBACKUP, SCHEDBW]
        - Requirement.set_start_time(time) (resp. set_end_time(time)) :
            :time string following time format hh:mm (e.g. 10:42)
            indicate the start (resp. end) time for the requirement
        - Requirement.set_days(days):
            :days array of global variale, that must be included in
            [MONDAY, TUESDAY,WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY]
        - Link(from, to):
            :from and :to type string
            declare a link between source (:from) router and
            destination (:to) router
        - Link.set_bw(bw):
            :bw an integer between 0 and 100
            indicate the bandwidth threshold in percent
        - Requirement.set_link(link):
            :link type Link
            an existing link


        - self.add_requirement(requirement):
            :requirement type Requirement
            add :requirement to schedule

        - self.next_timestamp():
            indicates that all following requirements will be added
            in a new configuration file (until the next call to self.next_timestamp())

    """
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
