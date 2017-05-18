Fibbing
~~~~~~~~~~~~~~~~~~~~~~~~~~

The aim of this program is to configure a network and to use fibbing requirments.


ConfD Installation
~~~~~~~~~~~~~~~~~~

If ConfD isn't installed yet, you can install it either in your home
directory or in a central place accessible by a group of people. See
the README file in the ConfD installation directory for directions.

In the installation directory, there is a file called confdrc (and
confdrc.tcsh) which is meant to be sourced before you start using the
examples. This file contains some useful settings, it adds ConfD to
the PATH, MANPATH, PYTHONPATH and LD_LIBRARY_PATH. It points out the
ConfD installation directory to the examples by setting $CONFD_DIR. If
you wish, you can paste (or source) these settings into (from) your
shell setup file.


What are all the Files?
~~~~~~~~~~~~~~~~~~~~~~~

+ *-README*
    The README files are the instructions you are reading now.

+ Makefile
    The Makefile describes the commands necessary to build the
    executable and schema files from the source files.
    Additionally, it contains the commands necessary for starting and
    stopping ConfD. Go to the example directory and type 'make' with
    no arguments to see what make targets there are.

+ Makefile.inc
    Included by Makefile, contains some generic information (paths,
    compiler flags, etc) used by all the examples.

+ commands-c.cli commands-j.cli
    Command line interface (CLI) extension file. Defines two extra
    commands (ping, ssh) usable in the CLI. The -c file is for the
    Cisco IOS XR-style CLI, -j for the Juniper JunOS-style CLI.

+ configfiles
    This directory contains the Json configuration files needed by mininet and the fibbingcontroler.

+ netconf
    Contains xml files for the network topology and the fibbing requirements

+ util
    Contains python scripts used to pars, generate private ip's, ...

+ confd.conf
    This is the ConfD configuration file(!). ConfD itself needs some
    configuration in order to know what features should be enabled,
    what directories to look for compiled schema files in, what type
    of logging is desired, etc.

+ commands-c.ccl commands-j.ccl (Appears when building)
    Compiled form of commands-c.cli and commands-j.cli.

+ confd_candidate.db (Appears when running)
    The CDB candidate database.

+ *.log (Appears when running)
    ConfD's log files. Run 'tail -f confd.log' in a terminal window to
    see what ConfD is doing.


Building
~~~~~~~~~~~~~~~~~~~~~~~~~
To build, all you have to do is 'make all'.
