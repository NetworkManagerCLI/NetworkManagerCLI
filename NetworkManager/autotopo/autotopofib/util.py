
class ConfigDict(dict):
    """
    A dictionary whose attributes are its keys
    """

    def __init__(self, **kwargs):
        super(ConfigDict, self).__init__()
        for key, val in kwargs.iteritems():
            self[key] = val

    def __getattr__(self, item):
        # so that self.item == self[item]
        try:
            # But preserve i.e. methods
            return super(ConfigDict, self).__getattr__(item)
        except:
            try:
                return self[item]
            except KeyError:
                return None

    def __setattr__(self, key, value):
        # so that self.key = value <==> self[key] = key
        self[key] = value


class Node(ConfigDict):
    def __init__(self,name) :
        self.name = name
        self.cur_intf = 0

    def new_intf(self):
		i = self.cur_intf
		self.cur_intf += 1
		return i

    def __hash__(self):
		return self.name.__hash__()

    def __eq__(self, o):
    	return self.name == o.name



class OSPFRouter(Node):
    def __init__(self,name) :
        super(OSPFRouter, self).__init__(name)
        self.routerid = None

    def set_routerid(self, rid) :
        self.routerid = rid

    def __str__(self):
        return 'Router\n name : %s\n routerid : %s ' % (self.name, self.routerid)



class Host(Node) :
    def __init__(self,name) :
        super(Host, self).__init__(name)


class Controller(Node) :
    def __init__(self,name) :
        super(Controller, self).__init__(name)


class Link(ConfigDict) :
    def __init__(self, node1, node2):
        self.node1 =node1
        self.node2 = node2
        self.port1 = self.node1.new_intf()
        self.port2 = self.node2.new_intf()
        self.intf1 = 'eth%s' % self.port1
        self.intf2 = 'eth%s' % self.port2

    def __eq__(self, o) :
        return self.node1 == self.node1\
        and self.node2 == self.node2

class OSPFLink(Link) :
    def __init__(self, src, dest, cost, bw=None) :
        super(OSPFLink, self).__init__(src, dest)
        self.src = src
        self.dest = dest
        self.name = '%sTo%s' % (self.src.name, self.dest.name)
        self.cost = cost
        self.bw = bw
        if not bw :
            self.bw = 100
        self.srcip = None
        self.destip = None
        self.pfx = 24
        self.slash = '/%d' % self.pfx

    def set_ips(self, srcip, destip) :
        self.srcip = srcip
        self.destip = destip

    def __str__(self):
        print 'OSPFLINK : '
        print '  name : %s' % self.name
        print '    srcip : %s intf: %s' % (self.srcip, self.intf1)
        print '    destip : %s intf: %s' % (self.destip, self.intf2)
        print '    cost: %d, bw: %d' %  (int(self.cost), int(self.bw))


        return '-------------'

class DestinationLink(Link) :

    def __init__(self, dest, router) :
        super(DestinationLink, self).__init__(dest, router)

        self.dest = dest
        self.router = router
        self.name = '%sTo%s' % (self.dest.name, self.router.name)

        self.routerip = None
        self.destip = None
        self.pfx = 24
        self.slash ='/%d' % self.pfx

    def set_ips(self, destip, routerip) :
        self.routerip = routerip
        self.destip = destip

    def __str__(self):
        print 'DESTLINK:'
        print '  name : %s' % self.name
        print '    router %s , ip : %s intf: %s' % (self.router.name, self.routerip, self.intf2)
        print '    dest %s , ip : %s intf: %s' % ( self.dest.name, self.destip, self.intf1)
        return '-------------'


class ControllerLink(Link) :
    def __init__(self, ctrl, router) :
        super(ControllerLink, self).__init__(ctrl,router)
        self.ctrl = ctrl
        self.router = router
        self.name = '%sTo%s' % (self.ctrl.name, self.router.name)

        self.routerip = None
        self.ctrlip = None
        self.pfx = 24
        self.slash ='/%d' % self.pfx

    def set_ips(self, ctrlip,routerip) :
        self.routerip = routerip
        self.ctrlip = ctrlip

    def __str__(self):
        print 'CTRLLINK:'
        print '  name : %s' % self.name
        print '    router %s , ip : %s intf: %s' % (self.router.name, self.routerip, self.intf2)
        print '    ctrl %s , ip : %s intf: %s' % ( self.ctrl.name, self.ctrlip, self.intf1)
        return '-------------'

# States
RUNNNING = 'running'
RUNNING = 'running'
NOTRUNNING = 'not-running'
SCHED = 'scheduled'
STATES = [RUNNING,RUNNNING, NOTRUNNING, SCHED]


SCHEDTIME = 'time'
SCHEDBW = 'bandwidth'
SCHEDBACKUP = 'backup'
TYPES = [SCHEDTIME, SCHEDBACKUP, SCHEDBW]
MONDAY = 'Monday'
TUESDAY = 'Tuesday'
WEDNESDAY = 'Wednesday'
THURSDAY = 'Thursday'
FRIDAY = 'Friday'
SATURDAY = 'Saturday'
SUNDAY = 'Sunday'
DAYS = [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY]
class ReqLink(ConfigDict) :
    def __init__(self, src, dest) :
        self.src = src
        self.dest = dest
        self.bw = None

    def set_bw(self,bw) :
        assert 0 < bw and bw <100, "Error bw must be between 0 and 100"
        self.bw = bw

class Requirement(ConfigDict) :
    def __init__(self , dest, path, name=None) :
        self.dest = dest
        assert path[-1] != '*', "A path cannot end by * router"
        self.path = path

        self.name = name
        if not name :
            self.name = 'to%s' % dest


        self.state = None
        self.Type = SCHEDTIME
        self.link = None
        self.start_time=None
        self.end_time = None
        self.days = None

    def set_state(self, state) :
        assert state in STATES, "State must be one of %s" % str(STATES)
        self.state = state

    def set_type(self, Type) :
        assert Type in TYPES , "Type must be one of %s" % str(TYPES)
        self.Type = Type

    def set_link(self, link):
        assert isinstance(link, ReqLink) , "Link must be a ReqLink"
        self.link = link

    def set_start_time(self, start) :
        # assert time format
        self.start_time = start

    def set_end_time(self, end) :
        self.end_time = end

    def set_days(self, days) :
        self.days = days
