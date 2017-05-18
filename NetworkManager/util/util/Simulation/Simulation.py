import socket
import sys
import json


# package un util/util
from util import TOPOLOGY_CONFIG, REQUIREMENT_CONFIG,\
                        OSPF_KEY,C1_cfg, TOPOlOGY_FILE,\
                        NETWORK_port, CONTROLLER_port,\
                        PACKETSIZE, ACK, LOCALHOST, NETLISTENER_port


from util import LOG


import time
import threading
import SocketServer
import datetime
from cmd import Cmd
import sys
import time
import subprocess
from ipaddress import ip_interface
import threading
import SocketServer
import random

from termcolor import colored
# Global variables
d_req = None
d = None
newconfig = False
firstconfig = False
has_req = False
new_req = False

E = threading.Event()

from util.CLI.networkmanager import NetworkManagerCLI
from util import LOG
# from util.Simulation import *

colors = {'ERROR' : 'red', 'SUCCESS' : 'green'}
Errors = 0



class SimulationCLI(NetworkManagerCLI) :
    """
        Simulation framework that extend the
        NetworkManagerCLI with functions that
        allow to simulation Time, and bandwidth
        plus a function that allow to simulation
        link failures
    """

    def __init__(self, BW, TIME, checker=False) :
        assert len(BW) == len(TIME), "BW and TIME must have the same length"
        super(SimulationCLI, self).__init__(checker=checker)
        self.BW = BW
        self.TIME =TIME
        self.Timestamp = 0

    def do_tcpdump_router(self, router) :
        """
            Run a tcpdump on the router
        """
        if router not in self.network.keys() :
            LOG.error('Router %s does not exists' % router)
        else :
            tcpdump = threading.Thread(target=self.tcpdump_router_th, args=(router,))
            tcpdump.start()

    def do_dump_database_router(self, router) :
        """
            Run a tcpdump on the router
        """
        if router not in self.network.keys() :
            LOG.error('Router %s does not exists' % router)
        else :
            Router = self.network[router]
            File = 'database_dump_%s.txt' % router
            Router.cmd('python telnet.py > %s' %  File)


    def tcpdump_router_th(self, router) :
        Router = self.network[router]
        pcapFile = 'tcpdump_%s.pcap' % router
        Router.cmd('tcpdump -c %d -w %s' % (1000, pcapFile))
        LOG.info('tcpdump finish ')

    def netconf_th(self, path) :
        """
            send netconf update of configuration
        """
        NETCONFPATH = '/Thesis/confd/bin/netconf-console'
        # comdline =['xterm', '-e', NETCONFPATH, path]
        comdline =[NETCONFPATH, path]
        subprocess.call(comdline)


    def netconf_config(self,path):
        """

        """
        netconf = threading.Thread(target=self.netconf_th, args=(path,))
        netconf.start()

    def get_time(self) :
        """
            OVERRIDE
            return the time value
            NB: for simulation override this function to
                fast forward in time
        """
        # global Timestamp
        if self.Timestamp<=len(self.TIME):
            return self.TIME[self.Timestamp]
        else :
            LOG.error('TIME out of bound')
            return 0

    def check_bw_snmp(self,from_R,to_R,bw_perc) :
        """
            NB: OVERRIDE
            check that the bandwidth for the link
            from_R -> to_R does not exceed bw_perc
            return False if bw does not exceed bw_perc
            return True if bw exceeds bw_perc
        """
        links = self.BW[self.Timestamp].get('links')
        for link in links :
            if from_R == link.get('from') and to_R==link.get('to'):
                return link.get('bw')

        return False

    def do_next_timestamp(self, line) :
        """
            increase the Timestamp
        """
        # global Timestamp
        if self.Timestamp +1 < len(self.TIME) :
            self.Timestamp += 1
        else :
            LOG.error('No more Timestamp available')

    def do_link( self, line ):
        """ NB Function from Mininet CLI
            Bring link(s) between two nodes up or down.
            Usage: link node1 node2 [up/down]"""
        args = line.split()
        if len(args) != 3:
            LOG.error( 'invalid number of args: link end1 end2 [up down]\n' )
        elif args[ 2 ] not in [ 'up', 'down' ]:
            LOG.error( 'invalid type: link end1 end2 [up down]\n' )
        else:
            if self.running :
                self.network.configLinkStatus( *args )
            else :
                LOG.error('Network must be running')

    def do_traceroute(self, line):
        args = line.split()
        if len(args) != 2:
            LOG.error( 'invalid number of args: traceroute source dest\n' )
        else:
            if self.running :
                if args[0] in self.network and args[1] in self.network:
                    node1=self.network[args[0]]
                    node2=self.network[args[1]]
                    Route= node1.cmd('traceroute -n '+node2.IP())

                    LOG.info(str(Route))

            else :
                LOG.error('Network must be running')


    def grace_full_shutdown(self) :
        """
            Shutdown the App, by first closing
            the controller and then closing the Network
        """

        if self.controllerrunning :
            self.do_stop_controller("Stopping controller...")
            time.sleep(5) # waiting for shapeshifter

        if self.running :
            self.do_stop_network('Stopping Network...')

        # shutdown the daemon thread
        self.shutdown()
        LOG.info('Stopping the App...')
