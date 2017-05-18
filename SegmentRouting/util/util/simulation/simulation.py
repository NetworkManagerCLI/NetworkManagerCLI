from util.CLI.networkmanager import *
from util.simulation import *
from util import *
import json
class SimulationCLI(NetworkManagerCLI) :
    """
        Extends the NetworkManagerCLI to add some
        functionalities for simulation
    """

    def __init__(self, BW, TIME, checker=False, autoBW=True) :
        assert len(BW) == len(TIME), "BW and TIME must have the same length"
        super(SimulationCLI, self).__init__(checker=checker)
        self.autoBW = autoBW
        self.BW = BW
        self.TIME =TIME
        self.Timestamp = 0

    def netconf_th(self, path) :
        """
            send netconf update of configuration
        """
        NETCONFPATH = '%s/../confd/bin/netconf-console %s' % (SRDir, path)
        runOS(NETCONFPATH)


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
        if self.autoBW :
            links = self.BW[self.Timestamp].get('links')
            for link in links :
                if from_R == link.get('from') and to_R==link.get('to'):
                    return link.get('bw')

            return False
        else :
            return super(SimulationCLI, self).check_bw_snmp(from_R, to_R, bw_perc)

    def do_next_timestamp(self, line) :
        """
            increase the Timestamp
        """
        #global Timestamp
        if self.Timestamp +1 < len(self.TIME) :
            self.Timestamp += 1
            LOG.info('Current time : %s' % str(self.get_time()))
        else :
            LOG.error('No more Timestamp available')

    def load_requirement(self, filename) :
        try :
            with open(filename, 'r') as f:
                data = json.load(f)
            if self.running :
                if  not checkRequirementConfig(self.data, data) :
                    LOG.info('SUCCESS : configurations pass check')
                    self.isrequirement = True
                    self.requirements = data

        except Exception as e :
            LOG.critical('Error : %s' % str(e))
