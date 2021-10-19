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

## Run the Ansible automation to install the ChRIS system

```bash
cd /usr/local/src/ChRIS_ultron_backEnd
ansible-playbook -K /usr/local/src/ChRIS_ultron_backEnd/ansible/install_all.yml
```

# Troubleshooting

## Creating a PostgreSQL user with privileges for ChRIS in an existing local PostgreSQL instance

```bash
psql -h localhost -U $USER -W
create user chris password 'Chris1234';
alter user chris superuser;
alter user chris createdb;
```

