

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


class Router(Node) :
    def __init__(self, name) :
        super(Router, self).__init__(name)
        self.loopback = None

        self.ospf6_enabled = None
        self.routerid = None

    def enable_ospf6(self) :
        self.ospf6_enabled = True

    def set_routerid(self, routerid) :
        self.routerid = routerid

    def set_loopback(self, lo) :
        self.loopback = lo

class Destination(Router) :
    def __init__(self, name) :
        super(Destination, self).__init__(name)
        self.dest_name = 'to%s' % self.name

class Controller(Router) :
    pass



class Link(ConfigDict) :
    def __init__(self, node1, node2):
        self.node1 =node1
        self.node2 = node2
        self.port1 = self.node1.new_intf()
        self.port2 = self.node2.new_intf()


    def __eq__(self, o) :
        return self.node1 == self.node1\
        and self.node2 == self.node2


class RouterLink(Link) :
    def __init__(self, src, dest,ospf6_enabled = None,cost=None, bw=None) :
        super(RouterLink, self).__init__(src, dest)

        self.src = self.node1
        self.dest = self.node2

        self.srcip = None
        self.destip = None
        self.ospf6_enabled = ospf6_enabled
        self.name = '%sTo%s' % (src.name, dest.name)
        self.cost = cost
        self.bw = bw

    def set_ips(self, srcip, destip):
        self.srcip = srcip
        self.destip = destip

    def __str__(self):
        print 'LINK : '
        print '  name : %s' % self.name
        print '    srcip : %s ' % (self.srcip)
        print '    destip : %s' % (self.destip)
        if self.cost :
            print '    cost: %d' %  (int(self.cost))
        if self.bw :
            print '    bw: %d' %  (int(self.bw))
        return '-------------'


# States
RUNNNING = 'running'
RUNNING = 'running'
NOTRUNNING = 'not-running'
SCHED = 'scheduled'
STATES = [RUNNING, RUNNNING, NOTRUNNING, SCHED]


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
