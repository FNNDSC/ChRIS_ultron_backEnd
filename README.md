# ![ChRIS logo](https://github.com/FNNDSC/ChRIS_ultron_backEnd/blob/master/docs/assets/logo_chris.png) ChRIS_ultron_backEnd

[![Build](https://github.com/FNNDSC/ChRIS_ultron_backEnd/actions/workflows/ci.yml/badge.svg)](https://github.com/FNNDSC/ChRIS_ultron_backEnd/actions/workflows/ci.yml)![License][license-badge]
![Last Commit][last-commit-badge]

The core backend service for the ChRIS distributed software platform, also known by the anacronym "CUBE". Internally the service is implemented as a Django-MySQL project offering a [collection+json](http://amundsen.com/media-types/collection/) REST API. Important ancillary components include the ``pfcon`` and ``pman`` file transfer and remote process management microservices.


## ChRIS development, testing and deployment

### Abstract

This page describes how to quickly get the set of services comprising the ChRIS backend up and running for CUBE development and how to run the automated tests. A production deployment of the ChRIS backend services is also explained.

### Preconditions

#### Install latest Docker and Docker Compose. 

Currently tested platforms:
* ``Docker 18.06.0+``
* ``Docker Compose 1.27.0+``
* ``Ubuntu 18.04+ and MAC OS X 10.14+``

#### On a Linux machine make sure to add your computer user to the ``docker`` group

Consult this page https://docs.docker.com/engine/install/linux-postinstall/

### TL;DR

#### If you read nothing else on this page, and just want to get an instance of the ChRIS backend services up and running with no mess, no fuss:

Start a local Docker Swarm cluster if not already started:

```bash
docker swarm init --advertise-addr 127.0.0.1
```

Start CUBE backend containers:

```bash
git clone https://github.com/FNNDSC/ChRIS_ultron_backend
cd ChRIS_ultron_backend
# Run full CUBE instantiation with tests:
./unmake.sh ; sudo rm -fr FS; rm -fr FS; ./make.sh

# Skip unit and integration tests and the intro:
./unmake.sh ; sudo rm -fr FS; rm -fr FS; ./make.sh -U -I -s
```

Once the system is "up", you can add more compute plugins to the ecosystem:

```bash
./postscript.sh
```

The resulting CUBE instance uses the default Django development server and therefore is not suitable for production.


### Production deployment

#### To get the production system up:

Note: Currently this deployment is based on a Swarm cluster that is able to schedule services on manager nodes (as declared in the compose file `pman` ancillary service is required to be scheduled on a manager node).

Start a local Docker Swarm cluster if not already started:

```bash
docker swarm init --advertise-addr 127.0.0.1
```

Fetch source code:

```bash
git clone https://github.com/FNNDSC/ChRIS_ultron_backend
cd ChRIS_ultron_backend
mkdir secrets
```

Now copy all the required secret configuration files into the secrets directory, please take a look at 
[this](https://github.com/FNNDSC/ChRIS_ultron_backEnd/wiki/ChRIS-backend-production-services-secret-configuration-files) 
wiki page to learn more about these files 

Deploy CUBE backend containers:

```bash
./deploy.sh up
```

#### To tear down:

Remove CUBE backend containers:

```bash
cd ChRIS_ultron_backend
./deploy.sh down
```

Remove the local Docker Swarm cluster if desired:

```bash
docker swarm leave --force
```

### Development

#### Optionally setup a virtual environment

Install ``virtualenv`` and ``virtualenvwrapper``:

```bash
pip install virtualenv virtualenvwrapper
```

Create a directory for your virtual environments e.g.:
```bash
mkdir ~/Python_Envs
```

You might want to add the following two lines to your ``.bashrc`` file:
```bash
export WORKON_HOME=~/Python_Envs
source /usr/local/bin/virtualenvwrapper.sh
```

Then source your ``.bashrc`` and create a new Python3 virtual environment:

```bash
mkvirtualenv --python=python3 chris_env
```

To activate chris_env:
```bash
workon chris_env
```

To deactivate chris_env:
```bash
deactivate
```

Install useful python tools in your virtual environment:
```bash
workon chris_env
pip install httpie
pip install python-swiftclient
pip install django-storage-swift
```

Note: You can also install some python libraries (not all of them) specified in the ``requirements/base.txt`` and 
``requirements/local.txt`` files in the repository source.

To list installed dependencies in chris_env:
```
pip freeze --local
````

#### Docker Swarm-based development environment

Start a local Docker Swarm cluster if not already started:

```bash
docker swarm init --advertise-addr 127.0.0.1
```

Start CUBE from the repository source directory by running the make bash script

```bash
git clone https://github.com/FNNDSC/ChRIS_ultron_backEnd.git
cd ChRIS_ultron_backEnd
./make.sh
```
All the steps performed by the above script are properly documented in the script itself. 
After running this script all the automated tests should have successfully run and a Django development server should be running in interactive mode in this terminal.

Later you can stop and remove CUBE services and storage space by running the following bash script from the repository source directory:

```bash
./unmake.sh
```

Then remove the local Docker Swarm cluster if desired:

```bash
docker swarm leave --force
```

#### Kubernetes-based development environment

Install single-node Kubernetes cluster. 
On MAC OS Docker Desktop includes a standalone Kubernetes server and client. 
Consult this page https://docs.docker.com/desktop/kubernetes/
On Linux there is a simple MicroK8s installation. Consult this page https://microk8s.io
Then create the required alias:

```bash
snap alias microk8s.kubectl kubectl
microk8s.kubectl config view --raw > $HOME/.kube/config
```

Start the Kubernetes cluster:

```bash
microk8s start
```

Start CUBE from the repository source directory by running the make bash script

```bash
git clone https://github.com/FNNDSC/ChRIS_ultron_backEnd.git
cd ChRIS_ultron_backEnd
export HOSTIP=<IP address of this machine>
./make.sh -O kubernetes
```

Later you can stop and remove CUBE services and storage space by running the following bash script from the repository source directory:

```bash
./unmake.sh -O kubernetes
```

Stop the Kubernetes cluster if desired:

```bash
microk8s stop
```

#### Rerun automated tests after modifying source code

Open another terminal and run the Unit and Integration tests within the container running the Django server:

To run only the Unit tests:

```bash
cd ChRIS_ultron_backEnd
docker-compose -f docker-compose_dev.yml exec chris_dev python manage.py test --exclude-tag integration
```

To run only the Integration tests:

```bash
docker-compose -f docker-compose_dev.yml exec chris_dev python manage.py test --tag integration
```

To run all the tests:

```bash
docker-compose -f docker-compose_dev.yml exec chris_dev python manage.py test 
```

After running the Integration tests the ``./FS/remote`` directory **must** be empty otherwise it means some error has occurred and you should manually empty it.


#### Check code coverage of the automated tests
Make sure the ``chris_backend/`` dir is world writable. Then type:

```bash
docker-compose -f docker-compose_dev.yml exec chris_dev coverage run --source=feeds,plugins,uploadedfiles,users manage.py test
docker-compose -f docker-compose_dev.yml exec chris_dev coverage report
```

#### Using [HTTPie](https://httpie.org/) client to play with the REST API 
A simple GET request to retrieve the user-specific list of feeds:
```bash
http -a cube:cube1234 http://localhost:8000/api/v1/
```
A simple POST request to run the plugin with id 1:
```bash
http -a cube:cube1234 POST http://localhost:8000/api/v1/plugins/1/instances/ Content-Type:application/vnd.collection+json Accept:application/vnd.collection+json template:='{"data":[{"name":"dir","value":"cube/"}]}'
```
Then keep making the following GET request until the ``"status"`` descriptor in the response becomes ``"finishedSuccessfully"``:
```bash
http -a cube:cube1234 http://localhost:8000/api/v1/plugins/instances/1/
```

#### Using swift client to list files in the users bucket
```bash
swift -A http://127.0.0.1:8080/auth/v1.0 -U chris:chris1234 -K testing list users
```


### Documentation

#### REST API reference

Available [here](https://fnndsc.github.io/ChRIS_ultron_backEnd).

Install Sphinx and the http extension (useful to document the REST API)
```
pip install Sphinx
pip install sphinxcontrib-httpdomain
```

Build the html documentation
```
cd docs/
make html
```

#### ChRIS REST API design.

Available [here](https://github.com/FNNDSC/ChRIS_ultron_backEnd/wiki/ChRIS-REST-API-design).

#### ChRIS backend database design.

Available [here](https://github.com/FNNDSC/ChRIS_ultron_backEnd/wiki/ChRIS-backend-database-design).

#### Wiki.

Available [here](https://github.com/FNNDSC/ChRIS_ultron_backEnd/wiki).

[license-badge]: https://img.shields.io/github/license/fnndsc/ChRIS_ultron_backEnd.svg
[last-commit-badge]: https://img.shields.io/github/last-commit/fnndsc/ChRIS_ultron_backEnd.svg

### Learn More

If you are interested in contributing or joining us, Check [here](http://chrisproject.org/join-us).
