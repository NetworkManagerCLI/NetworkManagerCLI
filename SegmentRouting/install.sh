#!/bin/bash
echo 'Installing ConfDAgent service...'
cd ../
echo 'Installing daemon package...'
sudo dpkg -i daemon_0.6.4-2_amd64.deb

# go to correct directory
cd SegmentRouting/

# compile the mininetdaemon
echo 'Installing compiling confdagent...'
make compile

cp res/confdagent /etc/init.d/
chmod +x /etc/init.d/confdagent

echo 'Installing Autotopo framework...'
cd autotopo/
sudo pip install -e .
echo 'It may require to restart the VM to work properly'
