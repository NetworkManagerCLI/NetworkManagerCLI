#!/bin/bash
cd
progress() {
    echo "@@ $1"
}

clone() {
    progress "Cloning $2"
    if [[ -d "$1" ]]; then
        cd ${1}
        git pull
        cd ..
    else
        git clone --recursive "https://github.com/Fibbing/$1"
    fi
}

clone_fork() {
    progress "Cloning $2"
    if [[ -d "$1" ]]; then
        cd ${1}
        git pull
        cd ..
    else
        git clone --recursive "https://github.com/NetworkManagerCLI/$1"
    fi
}

progress "Setting up root ssh login"
mkdir -p /root/.ssh
cat /home/vagrant/.ssh/authorized_keys >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys

progress "Installing dependencies"
# We need non-free for snmp mibs
sed -i '/^deb /s/$/ non-free/' /etc/apt/sources.list
sudo apt-get -y -qq --force-yes update
sudo apt-get -y -qq --force-yes install git bridge-utils python bash \
                        python-dev python-pip gcc build-essential \
                        automake autoconf libtool gawk libreadline-dev \
                        texinfo tmux vim-nox xterm tcpdump emacs nano \
                        speedometer inetutils-inetd python-matplotlib \
                        snmpd snmp snmp-mibs-downloader vlc \
                        python-paramiko libxml2-utils

update-inetd --comment-chars '#' --enable discard
systemctl enable inetutils-inetd
downnload-mibs
# comment that line as we downloaded all mibs
sed -i '/^mibs :/s/^/# /' /etc/snmp/snmp.conf
# Create a 'super' community ... not to be used in production for obvious
# reasons ...
echo "rwcommunity __fibbing  0.0.0.0/0" >> /etc/snmpd.conf
# We don't need that in the root namespace anyway
update-rc.d -f snmpd remove

progress "Installing Mininet"
git clone https://github.com/mininet/mininet.git
./mininet/util/install.sh -n

clone_fork fibbingnode "the fibbing sources"
clone labs "the fibbing labs"

progress "Installing the fibbing controller"
cd fibbingnode
sudo bash ./install.sh

[[ $(type -P "ospfd") ]] || echo 'export PATH=/opt/fibbing/sbin:${PATH}' >> /etc/profile

progress "Installing the patched kernel"
dpkg -i /vagrant/kernel/*.deb

progress "Installing the other dependencies"
sudo apt-get -y -qq --force-yes install python-paramiko libxml2-utils ifstat python-termcolor\
                                paris-traceroute

progress "Installing the util package"
cd
# install util package
# go to util directory
cd /Thesis/NetworkManager/util
# install the python package
sudo pip install -e .

progress ""
progress ""
progress "If you plan to use features such as Virtual Box shared folders, ..."
progress "You will need to rebuild the guest-additions !"
progress "Insert the guest addition CD from the VirtualBox GUI, then mount it"
progress 'in the vm (`mount +exec /dev/cdrom /mnt`), and run the file'
progress '`VBoxLinuxAdditions.run`'
