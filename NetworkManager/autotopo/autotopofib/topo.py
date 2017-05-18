from autotopofib.util import *
from autotopofib import *
from mako.template import Template


def render(filename, node, dest) :
    text = Template(filename=filename).render(requirements=node)
    with open(dest, 'w') as f:
        f.write(text)
        f.close()
# Types:
CTRL_LINK = 0
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
        render('%s/requirement.mako' % path ,self.schedule[timestamp],'%s/%s' %(self.dirname, filename))


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

class Topo(object):
    def __init__(self):
        self.ospfrouters = set()
        self.ospflinks = list()

        self.destinations = set()
        self.destinationlink = list()

        self.controller = set()
        self.controllerlink = list()

        self.main_controller = None

    def build(self) :
        """
            Function to overrride to
            build the topology
        """
        pass

    def get_node(self, name):
        for n in self.ospfrouters:
            if n.name == name:
                return n

        for n in self.destinations :
            if n.name == name:
				return n

        for n in self.controller :
            if n.name == name:
				return n

        return None





    def add_edge_by_type(self, src, dest, link_type, cost=None, bw=None) :
        assert link_type in [OSPF_LINK,DEST_LINK,CTRL_LINK], "Error type does not exist"
        if link_type == OSPF_LINK :
            assert cost and bw , "For OSPF link a cost and bw must be specified"
            self.add_ospf_link_by_name(src,dest,cost,bw)
        elif link_type == DEST_LINK :
            self.add_dest_link_by_name(src,dest)
        elif link_type == CTRL_LINK :
            self.add_ctrl_link_by_name(src,dest)

    def specify_main_controller(self, node) :
        assert self.get_node(node), "Node must be declared as a Host"

        Found = False
        for n in self.destinations :
            if n.name == node:
                self.main_controller = node
                Found = True

        assert Found, "Node must be declared as a Host"


    def add_ospf_router(self,router) :
        assert isinstance(router, OSPFRouter), "add_ospf_router needs a OSPFRouter"
        self.ospfrouters.add(router)

    def add_host(self, host) :
        assert isinstance(host, Host), "add_host needs a Host"
        self.destinations.add(host)


    def add_ospf_link_by_name(self, src, dest, cost, bw) :
        src_router = self.get_node(src)
        if not src_router :
            src_router = OSPFRouter(src)
            self.add_ospf_router(src_router)
        dest_router = self.get_node(dest)
        if not dest_router :
            dest_router = OSPFRouter(dest)
            self.add_ospf_router(dest_router)

        self.add_ospf_link(src_router, dest_router,cost, bw)

    def add_dest_link_by_name(self, host, router) :
        h = self.get_node(host)
        if not h :
            h = Host(host)
            self.add_host(h)
        r = self.get_node(router)
        if not r :
            r = OSPFRouter(router)
            self.add_ospf_router(r)



        self.add_dest_link(h,r)

    def add_ctrl_link_by_name(self, ctrl, router) :
        c = Controller(ctrl)
        assert self.get_node(ctrl) == None, "Controller %s exists" % ctrl
        r = self.get_node(router)
        if not r :
            r = OSPFRouter(router)
            self.add_ospf_router(r)
        l = ControllerLink(c,r)
        self.controllerlink.append(l)

    def add_dest_link(self, host, router):
        link =  DestinationLink(host, router)
        self.destinationlink.append(link)


    def add_ospf_link(self, src, dest, cost, bw) :
        O_L = OSPFLink(src,dest, cost, bw)
        self.ospflinks.append(O_L)
