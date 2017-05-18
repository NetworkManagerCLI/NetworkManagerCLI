import os
import subprocess
from subprocess import Popen, PIPE
import time
import sys
import json

def run_process(cmd):
    """
        run the cmd
    """
    p = Popen(cmd, shell=True, stdout=PIPE)
    p.wait()
    return p.stdout.read()

def runOS(cmd) :
    """
        run a os.system(cmd)
    """
    os.system(cmd)

# Commands
CONFDAGENT_START = 'service confdagent start'
CONFDAGENT_STOP = 'service confdagent stop'

MAKE_CLEAR = 'make clear'
MAKE_COMPILE = 'make compile'

BUILD = 'python simulation/%s/data/build.py'
RMDEBUGFILE = 'rm simulation/%s/out/debug.log'
CREATELOG = 'touch simulation/%s/out/debug.log'

START_SIM = 'python simulation/%s/measurement.py %s'


def restore() :
    print '*** restore ***'
    runOS(CONFDAGENT_STOP)
    run_process(MAKE_CLEAR)
    run_process(MAKE_COMPILE)
    runOS(CONFDAGENT_START)
    time.sleep(10)


def build_topo(scenario):
    print '*** build_topo ***'
    runOS(BUILD %  scenario)
    runOS(RMDEBUGFILE % scenario)
    runOS(CREATELOG % scenario)
    time.sleep(10)


if __name__ == '__main__':

    if len(sys.argv) == 2:
        scenarios = sys.argv[1].split(',')


        for scenario in scenarios :
            restore()
            build_topo(scenario)
            runOS(START_SIM % (scenario, '-c'))


    else :
        print '*** Arg Error ***'
        print 'Need a list of scenario :'
        print '  example: $ python run_automated_simulation.py scenario1,scenario2,scenario4'
        print '          where <scenario1> is a directory name in simulation'
