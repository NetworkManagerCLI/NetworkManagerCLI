# Network Manager for Fibbing solutions
## Starting the Application:
 * ```make manager-CLI```
 * or ```python main/main.py``` from the working directory
 * can use ```-D``` option for debugging and ```-c``` to disable the auto checker

## directory content:
 * autotopo/: The Autotopo framework (use in the context of simulation)
 * configfiles/: When debug mode of ConfD Agent is enable, Agent dumps the
                output config files in this directory
 * daemon/: The ConfD Agent code
 * doc/: Contains documentation relative to the Fibbing Solution
 * main/:  Contains the main.py to start the Application
 * res/: Contains some configurations files for the Application
 * simulation/: contains some simulation scenarios
 * util/: Contains the source code for the Fibbing Solution
 * Makefile: Contains make rules for the Application
 * install-snmp.sh: install script for SNMP
 * install.sh: installation script to setup the VM
 * run_automated_simulation.py: testbench for easily run the simulations
