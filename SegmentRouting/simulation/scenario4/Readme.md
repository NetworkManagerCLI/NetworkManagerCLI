# event:
Manual testing of bandwidth requirement with link overload

# topology : see build.py file


# simulation manipulation :
unlike the scenario3 where the bandwidth overload is specified by
the user for the simulation, here traffic will be generated with Iperf
## manipulation :
when you arrive in a terminal prompt, run
* ''xterm A''
* ''xterm C''
* ''xterm Dst''
* ''xterm Ctrl''

on C and Dst (inside Xterm):
* iperf -V -s -i 1

on Ctrl (inside Xterm) :
* iperf -V -t 300 -c <IPv6 loopack of C>

on A (inside Xterm) :
* iperf -V -t 300 -c <IPv6 loopack of Dst>
