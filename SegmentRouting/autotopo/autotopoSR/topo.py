from autotopoSR.util import *
from autotopoSR import *
from mako.template import Template


def render(filename, node, dest) :
    text = Template(filename=filename).render(requirements=node)
    with open(dest, 'w') as f:
        f.write(text)
        f.close()

# Types:
DEST_LINK = 1
OSPF_LINK = 2
class SimulationSchedule(object) :
    def __init__(self, dirname) :
        self.filename_base = 'requirement-'
        self.schedule = {}
        self.timestamp = 0

        self.dirname = dirname


    def gen_schedule_xml(self):
        for timestamp in self.schedule.keys() :
            self.gen_timestamp_xml(timestamp)

    def gen_timestamp_xml(self, timestamp) :
        assert timestamp in self.schedule, "No requirement for this timestamp"
        filename = self.filename_base+'%d.xml' % timestamp
        render('%s/requirement.mako' % path ,self.schedule[timestamp],'%s/%s' %(self.dirname, filename) )


    def build_requirement(self):
        """
            Function to overrride to
            build the requirements
        """
        pass

    def add_requirement(self, Req) :
        assert isinstance(Req, Requirement), "Req must be a Requirement"
        self.check_requirement(Req)
        if self.timestamp in self.schedule :
            self.schedule[self.timestamp].append(Req)
        else :
            self.schedule[self.timestamp] = list()
            self.schedule[self.timestamp].append(Req)



    def check_requirement(self, req) :
        assert req.state, "Requirement must have a state"
        if req.state == SCHED :
            assert req.Type, "Scheduled requirement must have a type"
            assert req.start_time,"Scheduled requirement must have a start_time"
            assert req.end_time,"Scheduled requirement must have a end_time"
            if req.Type != SCHEDTIME :
                assert req.link , "bandwidth or backup requirement must have a link"
                if req.Type == SCHEDBW :
                    assert req.link.bw , "bandwidth requirement must have a bw"

    def next_timestamp(self) :
        self.timestamp +=1

class Topo(object) :
    def __init__(self ) :
        self.routers = set()
        self.links = list()

        self.destinations = set()
        self.controller = None

    def build(self) :
        """
            function to overrride to add all
            the component of the topology,
            with def 'add_link_by_name', def set_destination, and
            def set_controller
        """
        pass

    def add_edge_by_type(self, src, dest, link_type, cost=None, bw=None) :
        """
            Unified API for two solutions
        """
        assert link_type in [OSPF_LINK,DEST_LINK], "Error type does not exist"
        if link_type == OSPF_LINK :
            self.add_link_by_name(src,dest,ospf_enabled=True,cost=cost,bw=bw)
        elif link_type == DEST_LINK :
            self.add_link_by_name(src,dest,ospf_enabled=True,cost=cost,bw=bw)
            self.set_destination(src)


    def add_link_by_name(self, src, dest, ospf_enabled=True, cost=None, bw=None):
        src_router = self.get_node(src)
        if not src_router :
            src_router = self.add_router_by_name(src)

        dest_router = self.get_node(dest)
        if not dest_router :
            dest_router = self.add_router_by_name(dest)

        self.add_link(src_router, dest_router, ospf_enabled, cost, bw)

    def set_destination(self, rname) :
        """
            specifies which router is a destination
        """

        assert self.get_node(rname), "Router %s must first be declared " % rname
        Dest = Destination(rname)
        self.destinations.add(Dest)

    def set_controller(self,name) :
        router = self.get_node(name)
        assert router, "Router %s must first be declared " % name
        self.controller = router


    def add_router_by_name(self, router) :
        assert not self.get_node(router), "Router %s already exists" % router
        r = Router(router)
        self.routers.add(r)
        return r

    def add_link(self, src, dest, ospf_enabled, cost,bw):
        """
            src and dest are both Router
        """
        assert isinstance(src,Router) and isinstance(dest,Router), "src and dest must be Router"
        if ospf_enabled :
            src.enable_ospf6()
            dest.enable_ospf6()
        l = RouterLink(src, dest,ospf_enabled, cost, bw)
        self.links.append(l)


    def get_node(self,node) :
        for n in self.routers:
            if n.name == node:
                return n
        return None
