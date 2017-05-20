# Contains in a centralised place all the global variable

import os
UtilDir = os.path.dirname(__file__)
SRDir = '%s/../..' % UtilDir
# Network and controller manager
NETWORK_port = 50001
CONTROLLER_port = 60002
LOCALHOST = '0.0.0.0'
PACKETSIZE  = 63900
ACK = 'ACK'
NETLISTENER_port = 9999

# Ipv6 network
BOOTSTRAPFILE = 'bootstrap.sh'
REMOVEFILE = 'remove.sh'
RUNSH = 'sh '
CONNECT = 'ip netns exec '
BASHCMD = ' bash -c '
PING6 = 'ping6 -I %s %s -c %d'
TRACEROUTE6 = 'traceroute6 -s %s -n %s'
IPROUTE = 'ip -6 ro'


# SNMP query
SNMPWALK = 'snmpwalk -u bootstrap -l authPriv -a MD5 -x DES -A temp_password -X temp_password udp6:[%s]:161 %s'
SNMPBULKGET = 'snmpbulkget -u bootstrap -l authPriv -a MD5 -x DES -A temp_password -X temp_password udp6:[%s]:161 %s'
# Status
UP = 'running'
DOWN = 'not-running'
SCHED = 'scheduled'
PEND = 'pending'
TIME = 'time'
BAND = 'bandwidth'
BACK = 'backup'
# Flags
F_OK = 0
F_stop = 1
F_Add = 2
F_delete = 3
F_replace = 4
F_halt = 5
F_present = 6
# time scheduled
WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
# Requirement = namedtuple('Requirement', 'name, dest,router,req,status')
class Requirement :
    def __init__(self, name, dest,router,req,status):
        self.name = name
        self.dest = dest
        self.router = router
        self.req = req
        self.status = status
        self.flag = F_OK
        self.flags = [False,False,False,False,False,False,False,False]
        self.newRequirement = False
        self.start_hour_str = ''
        self.start_hour = (0,0)
        self.end_hour_str = ''
        self.end_hour = (0,0)
        self.weekdays = []
        self.runningstatus = DOWN
        self.scheduleType = TIME
        self.from_R =  ''
        self.to_R = ''
        self.bw_perc = 100

        # TODO: add bw properties and schedulde type
    def set_type(self, Type) :
        self.scheduleType = Type
    def set_bw_perc(self, bw) :
        self.bw_perc = bw

    def set_link(self,from_R, to_R ) :
        self.from_R = from_R
        self.to_R = to_R

    def set_start_hour(self, hour, hour_str) :
        self.start_hour_str = hour_str
        self.start_hour = hour

    def set_end_hour(self, hour, hour_str) :
        self.end_hour_str = hour_str
        self.end_hour = hour

    def set_weekday(self, days) :
        self.weekdays = days

    def set_runningstatus(self, status) :
        self.runningstatus = status

    def set_status(self, status) :
        self.status = status
    def set_flag(self, flag) :
        self.flag = flag
        self.flags[flag] = True
    def reset_all_flags(self) :
        for i in range(len(self.flags)) :
            self.flags[i] = False
    def to_string(self) :
        string = str(self.name)
        string = string + str(self.dest) + str(self.router)
        string = string + str(self.req)
        return string

    def sched_to_string(self) :
        if self.status == SCHED and self.scheduleType == TIME:
            string = self.start_hour_str + self.end_hour_str
            string = string + str(self.weekdays)
            return string

    def bw_to_string(self) :
        if self.status == SCHED and self.scheduleType == BAND :
            string = self.from_R + self.to_R + str(self.bw_perc)
            string = string + str(self.weekdays)
            return string

    def set_newRequirement(self, newRequirement) :
        self.newRequirement = newRequirement



# LOG config
import logging
# Warnings are orange
logging.addLevelName(logging.WARNING, "\033[1;43m%s\033[1;0m" %
                                      logging.getLevelName(logging.WARNING))
# Errors are red
logging.addLevelName(logging.ERROR, "\033[1;41m%s\033[1;0m" %
                                    logging.getLevelName(logging.ERROR))
# Debug is green
logging.addLevelName(logging.DEBUG, "\033[1;42m%s\033[1;0m" %
                                    logging.getLevelName(logging.DEBUG))
# Information messages are blue
logging.addLevelName(logging.INFO, "\033[1;44m%s\033[1;0m" %
                                   logging.getLevelName(logging.INFO))
# Critical messages are violet
logging.addLevelName(logging.CRITICAL, "\033[1;45m%s\033[1;0m" %
                                       logging.getLevelName(logging.CRITICAL))

LOG = logging.getLogger(__name__)
fmt = logging.Formatter('%(asctime)s [%(levelname)20s] %(funcName)s: %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(fmt)
LOG.addHandler(handler)
