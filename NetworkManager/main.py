import argparse
import time
import threading
import SocketServer
from util import TOPOLOGY_CONFIG, REQUIREMENT_CONFIG,\
                        OSPF_KEY,C1_cfg, TOPOlOGY_FILE,\
                        NETWORK_port, CONTROLLER_port,\
                        PACKETSIZE, ACK, LOCALHOST, NETLISTENER_port
from util import LOG
from util.CLI.networkmanager import NetworkManagerCLI


# --------------------------------------------------------
if __name__ == '__main__':
    import logging
    DEBUG = logging.INFO
    Check = True
    # global fib_cli
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-n', '--net',
                       help='Start the Mininet topology',
                       action='store_true',
                       default=True)
    parser.add_argument('-d', '--debug',
                        help='Set log levels to debug for Fibbing',
                        action='store_true',
                        default=False)
    parser.add_argument('-D', '--debugall',
                        help='Set log levels to debug for ManagerCLi',
                        action='store_true',
                        default=False)
    parser.add_argument('-c', '--checker',
                        help='Disable auto checker of requirement',
                        action='store_true',
                        default=False)
    args = parser.parse_args()
    if args.debug:
        _lib.DEBUG_FLAG = True
        from mininet.log import lg
        from fibbingnode import log
        import logging
        log.setLevel(logging.DEBUG)
        lg.setLogLevel('debug')
    if args.checker :
        Check = False
    if args.debugall:
        DEBUG = logging.DEBUG
    if args.net:
        import logging
        LOG.setLevel(DEBUG)


        # stating the CLI
        prompt = NetworkManagerCLI(checker=Check)
        prompt.start()
