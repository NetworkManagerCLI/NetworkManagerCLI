# Network Manager for Segment Routing solution
## Starting the Application:
  * ```make manager-CLI```
  * or ```python main.py``` from the working directory
  * can use ```-D``` option for debugging and ```-c``` to disable the auto checker

## directory content:
   * autotopo/: The Autotopo framework (use in the context of simulation)
   * daemon/: The ConfD Agent code
   * debug/: When debug mode of ConfD Agent is enable, Agent dumps the
                  output config files in this directory
   * doc/: Contains documentation relative to the Segment Routing Solution
   * nanonet/: Contains code of (modified) Nanonet framework
   * res/: Contains some configurations files for the Application
   * simulation/: contains some simulation scenarios
   * SRconfdagent/: Contains the code of the ConfD Agent that handles the
                    SR routes
   * util/: Contains the source code for the Segment Routing Solution
   * main.py: Main file to start the NetworkManagerCLI for the SR Solution
   * run_automated_simulation.py: testbench for easily run the simulations
