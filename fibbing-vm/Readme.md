# Fibbing Virtual Machine from https://github.com/Fibbing

This is the virtual image definition to get a Fibbing controller installation.

Building it requires [Vagrant](vagrantup.com)

Using it requires [VirtualBox](virtualbox.org), although the Vagrantfile can be modified
to target other provider (see Vagrant Documentation).

# Building the VM

```bash
./install.sh
```

This will build a Debian virtual machine and add it to the list
of installed machines in VirtualBox. It will also install all required components
to run a Fibbing controller as well as use it in mininet experiments.

When the build is complete, the VM will be started.

# Installing the Network Manager in the VM
Once you are inside the VM (`vagrant ssh`), go into the main working directory
```bash
cd /Thesis/NetworkManager/
```
and run :
```bash
make install-all
```

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
