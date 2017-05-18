from util.Simulation.Simulation import *

from util import LOG,fmt
import datetime
import logging
import logging.handlers
import json
import os
import argparse

if __name__ == '__main__':
    Check = True
    DEBUG = logging.INFO
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    parser.add_argument('-D', '--debugall',
                        help='Set log levels to debug for ManagerCLi',
                        action='store_true',
                        default=False)
    parser.add_argument('-c', '--checker',
                        help='Disable auto checker of requirement',
                        action='store_true',
                        default=False)
    args = parser.parse_args()
    if args.debugall:
        DEBUG = logging.DEBUG
    if args.checker :
        Check = False


    path = os.path.dirname(os.path.realpath(__file__))
    LOG_FILENAME = '%s/out/debug.log' % path
    FileHdlr = logging.FileHandler(LOG_FILENAME)
    FileHdlr.setFormatter(fmt)
    LOG.addHandler(FileHdlr)
    LOG.setLevel(DEBUG)

    # specify different timestamp
    # mainly used with time based requirement
    TIME = [
        datetime.datetime(2017,4,27,10,0,0),
        datetime.datetime(2017,4,27,11,0,0),
        datetime.datetime(2017,4,27,11,30,0),
        datetime.datetime(2017,4,27,12,0,0)
    ]

    # used to simulate what is the bw status of the
    # specified links (from, to) at each timestamp
    BW = [
        {"links" : [

        ]},
        {"links" : [
            {"from" :"A", "to" : "B", "bw" : False},
        ]},
        {"links" : [
            {"from" :"A", "to" : "B", "bw" : True},
        ]},
        {"links" : [
            {"from" :"A", "to" : "B", "bw" : False},
        ]},
    ]


    #
    prompt = SimulationCLI(BW,TIME, checker=Check)

    LOG.info('sending topo config')
    prompt.netconf_th('%s/data/netconf-topo.xml' % path)
    # Starting the network
    prompt.do_start_network('Test')
    LOG.info('sending requirement-0 config')
    prompt.netconf_th('%s/data/requirement-0.xml' % path)
    # starting the controller with some requirements
    prompt.do_start_controller('Starting controller')
    time.sleep(5)

    # open manual CLI
    prompt.start()


    # # stopping the simulation
    # restoring the random restart
    prompt.netconf_th('%s/data/restore.xml' % path)
