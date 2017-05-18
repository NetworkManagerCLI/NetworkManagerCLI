# Source Code of Network Manager for Segment Routing Solution

## directory content:
 * checker/: Contains exception.py that checker the configurations received
             via the ConfD Agent
 * CLI/: Contains networkmanager.py that is the contains the source code
         for both NetworkManagerCore and NetworkManagerCLI
 * helper/: Contains some helper functions and the SouthboundManager
 * simulation/: Contains the modified NetworkManagerCLI to support simulation
 * __init__: gathers some global variables

### helper/:
 * __init__: gathers some global variables and functions
 * Dijkstra.py: Simple framework that will perform the path expansion,
                when there is a requirement with the * symbol
 * DijkstraDag.py: framework that contains the Simplifier that computes the
                   minimum label stack
 * Quagga.py: Extension to Nanonet to represent a Quagga routers, will
              generate the config files and start the Quagga daemons
 * southboundmanager.py: The Southbound Interface for the SR solution
 * topo.py:  The network topology filled with the configurations and used by Nanonet
