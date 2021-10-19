# Install the complete ChRIS system locally with Ansible and Podman

## Install dependencies on Linux

```bash
sudo yum install -y git python3 python3-pip python3-virtualenv python3-libselinux python3-libsemanage python3-policycoreutils
```

## Install dependencies on MacOSX

```bash
brew install git python gnu-tar podman
pip3 install virtualenv
```

## Install the latest Python and setup a new Python virtualenv

```bash
# This step might be virtualenv-3 for you. 
virtualenv ~/python

source ~/python/bin/activate
echo "source ~/python/bin/activate" | tee -a ~/.bash_profile
```

## Install the latest Ansible

```bash
pip install setuptools_rust wheel
pip install --upgrade pip
pip install ansible selinux setools
```

## Clone the ChRIS_ultron_backEnd repository

### Create a directory for the ChRIS_ultron_backEnd repository and clone it

```bash
install -d -o $USER /usr/local/src/ChRIS_ultron_backEnd
git clone git@github.com:team19hackathon2021/ChRIS_ultron_backEnd.git /usr/local/src/ChRIS_ultron_backEnd
```

## Determine the IP Address of your computer that will run the Podman TCP API

```
ip addr
...
2: enp1s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    link/ether e0:d5:5e:23:f7:68 brd ff:ff:ff:ff:ff:ff
    inet 192.168.1.13/24 brd 192.168.1.255 scope global noprefixroute dynamic enp1s0
```

Use the IP address you want to use (example: 192.168.1.13) for the PODMAN_IP_ADDRESS variable in the following ansible-playbook command. 

## Run the Ansible automation to install the ChRIS system

```bash
cd /usr/local/src/ChRIS_ultron_backEnd
ansible-playbook -K /usr/local/src/ChRIS_ultron_backEnd/ansible/install_all.yml -e PODMAN_IP_ADDRESS=192.168.1.13
```

# Troubleshooting

## Creating a PostgreSQL user with privileges for ChRIS in an existing local PostgreSQL instance

```bash
psql -h localhost -U $USER -W
create user chris password 'Chris1234';
alter user chris superuser;
alter user chris createdb;
```

## Failed to create ChRIS podman network on recent CentOS Stream 8 distro

If you get an error creating the Podman network named "ChRIS" on a very recent Linux distro running podman version 4.0.0, you may need to create the network manually: 

```bash
sudo podman network create ChRIS
```

This is because of a bug where podman inspect network doesn't show the network plugins anymore. 

