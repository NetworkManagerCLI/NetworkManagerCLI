from util.simulation.simulation import *
from util import LOG
import datetime
import logging
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

    TIME = [
        datetime.datetime(2017,4,27,10,0,0),
        datetime.datetime(2017,4,27,11,0,0),
        datetime.datetime(2017,4,27,11,30,0),
        datetime.datetime(2017,4,27,12,0,0)
    ]


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

    prompt = SimulationCLI(BW,TIME, checker=Check,autoBW=False)
    prompt.netconf_th('%s/data/netconf-topo.xml' % path)
    # time.sleep(5)
    prompt.do_start_network('Starting topo')
    prompt.netconf_th('%s/data/requirement-0.xml' % path)
    # time.sleep(5)
    prompt.do_apply_new_requirement('Apply Requirement')
    time.sleep(5)
    prompt.do_show_requirements('display')
    prompt.do_enable_auto_schedule('Start checking')
    time.sleep(30) # wait for the check is done
    prompt.do_halt_auto_schedule('stop checking')
    prompt.do_show_requirements('display')
    LOG.info('No requirement should be running')
    time.sleep(5)
    prompt.do_next_timestamp('11:00')
    prompt.do_show_requirements('display')
    time.sleep(5)
    prompt.do_enable_auto_schedule('Start checking')
    time.sleep(30) # wait for the check is done
    prompt.do_halt_auto_schedule('stop checking')
    prompt.do_show_requirements('display')
    LOG.info('bw requirement from A to B should not be running')
    


    prompt.start()


    prompt.netconf_th('%s/data/restore.xml' % path)
