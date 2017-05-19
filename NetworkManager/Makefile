######################################################################
# Makefile to control the confD daemon, the Mininet topology, etc
#
#
# See the README files for more information
######################################################################

usage:
	@echo "See README files for more instructions"
	@echo "-------------------------------------------"
	@echo "                INSTALL                    "
	@echo "-------------------------------------------"
	@echo " make install    to install the util package"
	@echo "							    This is required to use the"
	@echo "									project ! This should be "
	@echo "									done at VM provision"
	@echo "-------------------------------------------"
	@echo "            daemon related rules           "
	@echo ""
	@echo "make compile     Build the daemon objects"
	@echo "make clear   Remove all built and intermediary daemon files"
	@echo "make start-daemon   Start CONFD daemon "
	@echo "make stop-daemon    Stop any CONFD daemon and example agent"
	@echo "make cli     Start the CONFD Command Line Interface, J-style"


######################################################################
# daemon/ related rule
compile:
	make all -C daemon/

clear:
	make clean -C daemon/

start-daemon:
	make start -C daemon/

stop-daemon:
	make stop -C daemon/

cli:
	make cli -C daemon/
######################################################################
clean-config:
	rm configfiles/*

######################################################################
manager-CLI :
	python main.py -c

session:
	tmux new -s 'NetworkManager'

session-list:
	tmux ls

attach-session:
	tmux a
######################################################################
install:
	./install.sh

snmp-config:
	./install-snmp.sh

######################################################################
gen-Abilene:
	python netconf/AutoAbilene/build.py

load-abilene-network:
	../confd/bin/netconf-console netconf/AutoAbilene/netconf-topo.xml

load-abilene-requirement:
	../confd/bin/netconf-console netconf/AutoAbilene/requirement-0.xml
######################################################################
simulation-example: gen-example run-example
gen-example:
	python simulation/example/data/build.py

run-example:
	python simulation/example/measurement.py -c
