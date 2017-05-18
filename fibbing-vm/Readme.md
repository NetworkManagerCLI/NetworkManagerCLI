# Fibbing Virtual Machine

This is the virtual image definition to get a Fibbing controller installation.

Building it requires [Vagrant](vagrantup.com)

Using it requires [VirtualBox](virtualbox.org), although the Vagrantfile can be modified
to target other provider (see Vagrant Documentation).

# Building the VM

```bash
DEST=fibbing-vm
git clone https://github.com/Fibbing/virtual-machine.git ${DEST}
cd ${DEST}
./install.sh
```

This will build a Debian virtual machine and add it to the list
of installed machines in VirtualBox. It will also install all required components
to run a Fibbing controller as well as use it in mininet experiments.

When the build is complete, the VM will be started.

To verify that build succeeded:
1. You should be logged as root when connecting to the VM (prompt ending by #)
2. `ls /root` should list: `fibbingnode  labs  mininet`
3. `python -m fibbingnode` should successfully spawn a 'blank' controller instance.

# Accessing the VM

Start the VM if it is not yet running, using `vagrant up`, then open an ssh connection
using `vagrant ssh`.

You can also connect to it using the VirtualBox GUI, using vagrant/vagrant as login/password.

# Updating the VM

If you want to update the virtual machine, edit the Vagrantfile (or get the latest
one via `git pull`), then run `vagrant up --provision` to rebuild it.

# Stopping the VM

`vagrant halt` will stop the VM

`vagrant destroy` will stop it and destroy all files associated to it
beside the Vagrantfile

# Misc. Info

When running the fibbingnode controller (e.g. sudo python -m fibbignode), be careful
with what physical interface you specify to be captured by the controller.
Capturing eth0 (to directly connect to a physical router for example) will
break your ssh session (if any) and prevent the root network namespace (= where you
land when accessing the VM via ssh) from accessing the outside networks.

snmpd is available on the VM, and the community `__fibbing` as all access from
any source prefix.
