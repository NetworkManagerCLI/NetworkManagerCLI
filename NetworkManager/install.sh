#!/bin/bash
echo 'Installing ConfDAgent service...'
cd /Thesis/NetworkManager/res
echo 'Installing daemon package...'
sudo dpkg -i daemon_0.6.4-2_amd64.deb

# go to correct directory
cd /Thesis/NetworkManager

# compile the mininetdaemon
echo 'Installing compiling confdagent...'
make compile

cp res/confdagent /etc/init.d/
chmod +x /etc/init.d/confdagent



echo 'Coping the default.cgf from Fibbing...'
cp /root/fibbingnode/fibbingnode/res/default.cfg res/template.cgf

echo 'Installing Autotopo framework...'
cd /Thesis/NetworkManager/autotopo/
sudo pip install -e .


echo 'It may require to restart the VM to work properly'
