# ![ChRIS logo](https://github.com/FNNDSC/ChRIS_ultron_backEnd/blob/master/docs/assets/logo_chris.png) ChRIS\_ultron\_backEnd

[![Build](https://github.com/FNNDSC/ChRIS_ultron_backEnd/actions/workflows/ci.yml/badge.svg)](https://github.com/FNNDSC/ChRIS_ultron_backEnd/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/fnndsc/ChRIS_ultron_backEnd.svg)](./LICENSE)

_ChRIS_ is an open-source platform for containerized medical compute.
The _ChRIS_ backend, a.k.a. _ChRIS Ultron Backend_ or _**CUBE**_ for short,
is a component of the _ChRIS_ system.

![Architecture Diagram](https://chrisproject.org/img/figures/ChRIS_architecture.svg#gh-light-mode-only)
![Architecture Diagram](https://chrisproject.org/img/figures/ChRIS_architecture_dark.svg#gh-dark-mode-only)

The core backend service for the ChRIS distributed software platform, also known by the anacronym _CUBE_. Internally the service is implemented as a Django-PostgreSQL project offering a [collection+json](http://amundsen.com/media-types/collection/) REST API. Important ancillary components include the ``pfcon`` and ``pman`` file transfer and remote process management microservices.


## ChRIS development, testing and deployment

### Abstract

_ChRIS Ultron Back End_ (sometimes also _ChRIS Underlying Back End_) or simply _CUBE_ is the main core of the ChRIS system. _CUBE_ provides the main REST API to the ChRIS system, as well as maintaining an internal database of users, files, pipelines, and plugins. Currently _CUBE_ has two separate compute paradigms depending on deployment context. In the case of _development_ all components of _CUBE_ use `docker` and `docker swarm` technologies. In the case of _production_ technologies such as `openshift` and `kubernetes` are also supported.

Consult this page for instructions on starting _CUBE_ in either _development_ or _production_ contexts. For documentation/overview/background, please see the [documention](https://github.com/FNNDSC/ChRIS_docs).


### Preconditions

#### Operating system support -- please read

##### Linux

Linux is the first class host platform for all things _CUBE_ related. Linux distributions used by various core developers include Ubuntu, Arch, and Fedora. The development team is happy to provide help to folks trying / struggling to run _CUBE_ on most any Linux distribution.

##### macOS

macOS is fully supported as a host platform for _CUBE_. Please note that you **must update/tweak some things first**. Most importantly, macOS is distributed with a deprecated version of the `bash` shell **that will not work with our Makefile**. If you want to host _CUBE_ on macOS, you **must** update `bash` to a current version. Instructions are out of scope of this document, but we recommend [homebrew](https://brew.sh) as your friend here.

##### Windows

In a word, **don't** (ok, that's technically two words). _CUBE_ is ideally meant to be deployed on Linux/*nix systems. **Windows is not officially supported nor recommended as the host environment**. If you insist on trying on Windows you can consult some unmaintained documentation on attempts to deploy _CUBE_ using the Windows Subsystem for Linux (WSL) [here](https://github.com/FNNDSC/CHRIS_docs/blob/master/workflows/ChRIS_on_WSL.asciidoc). This probably will break. Note that currently no one on the core development uses Windows in much of any capacity so interest or knowledge to help questions about Windows support is low. Nonetheless, we would welcome any brave soul though who has the time and inclination to fully investigate _CUBE_ on Windows deployment.

 
#### Install latest Docker and Docker Compose. 

Currently tested platforms:
* ``Docker 18.06.0+``
* ``Docker Compose 1.27.0+``
* ``Ubuntu 18.04+ and MAC OS X 10.14+``

#### On a Linux machine make sure to add your computer user to the ``docker`` group

Consult this page https://docs.docker.com/engine/install/linux-postinstall/

### TL;DR

#### If you read nothing else on this page, and just want to get an instance of the ChRIS backend services up and running with no mess, no fuss:

##### The real TL;DR

The all in one copy/paste line to drop into your terminal (assuming of course you are in the repo directory and have the preconditions met):

```bash
docker swarm leave --force && docker swarm init --advertise-addr 127.0.0.1 &&  \
./unmake.sh && sudo rm -fr CHRIS_REMOTE_FS && rm -fr CHRIS_REMOTE_FS &&        \
./make.sh -U -I -i
```

This will start a **bare bones** _CUBE_. This _CUBE_ will **NOT** have any plugins installed. To install a set of plugins, do

```bash
./postscript.sh
```

##### Slightly longer but still short TL;DR

Start a local Docker Swarm cluster if not already started:

```bash
docker swarm init --advertise-addr 127.0.0.1
```

Get the source code from CUBE repo: 

```bash
git clone https://github.com/FNNDSC/ChRIS_ultron_backend
cd ChRIS_ultron_backend
```

Run full CUBE instantiation with tests:
```bash
./unmake.sh ; sudo rm -fr CHRIS_REMOTE_FS; rm -fr CHRIS_REMOTE_FS; ./make.sh
```

Or skip unit and integration tests and the intro:
```bash
./unmake.sh ; sudo rm -fr CHRIS_REMOTE_FS; rm -fr CHRIS_REMOTE_FS; ./make.sh -U -I -s
```

Once the system is "up" you can add more compute plugins to the ecosystem:

```bash
./postscript.sh
```

The resulting CUBE instance uses the default Django development server and therefore is not suitable for production.


### Production deployments

Please refer to https://github.com/FNNDSC/khris-helm


### Development

#### Docker Swarm-based development environment:

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

#### Kubernetes-based development environment:

Install single-node Kubernetes cluster. 
On MAC OS Docker Desktop includes a standalone Kubernetes server and client. 
Consult this page https://docs.docker.com/desktop/kubernetes/.
On Linux there is a simple MicroK8s installation. Consult this page https://microk8s.io.
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
docker compose -f docker-compose_dev.yml exec chris_dev python manage.py test --exclude-tag integration
```

To run only the Integration tests:

```bash
docker compose -f docker-compose_dev.yml exec chris_dev python manage.py test --tag integration
```

To run all the tests:

```bash
docker compose -f docker-compose_dev.yml exec chris_dev python manage.py test 
```

After running the Integration tests the ``./CHRIS_REMOTE_FS`` directory **must** be empty otherwise it means some error has occurred and you should manually empty it.


#### Check code coverage of the automated tests
Make sure the ``chris_backend/`` dir is world writable. Then type:

```bash
docker compose -f docker-compose_dev.yml exec chris_dev coverage run --source=feeds,plugins,userfiles,users manage.py test
docker compose -f docker-compose_dev.yml exec chris_dev coverage report
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

### Learn More

If you are interested in contributing or joining us, Check [here](http://chrisproject.org/join-us).
