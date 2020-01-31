# ChRIS_ultron_backEnd
[![Build Status](https://travis-ci.org/FNNDSC/ChRIS_ultron_backEnd.svg?branch=master)](https://travis-ci.org/FNNDSC/ChRIS_ultron_backEnd)
![License][license-badge]
![Last Commit][last-commit-badge]

The core back end for the ChRIS system, also known by the anacronym "CUBE". Internally this is instantiated as Django-mysql project offering a collection+json REST API.

## ChRIS development and testing

## TL;DR

If you read nothing else on this page, and just want to get an instance of ChRIS CUBE up and running with no mess, no fuss (and assuming you have `docker` and friends as described elsewhere on this page):

```bash
git clone https://github.com/FNNDSC/ChRIS_ultron_backend
cd ChRIS_ultron_backend
# Run full CUBE instantiation with tests:
*destroy* ; sudo rm -fr FS; rm -fr FS; *make*

# Skip unit and integration tests and the intro:
*destroy* ; sudo rm -fr FS; rm -fr FS; *make* -U -I -s
```

### Abstract

This page describes how to quickly get the set of services comprising the backend up and running for development and how to run the automated tests.

### Preconditions

#### Install latest Docker and Docker Compose. Currently tested platforms
* ``Docker 17.04.0+``
* ``Docker Compose 1.10.0+``
* ``Ubuntu (16.04+) and MAC OS X 10.11+``

#### Make sure to add your computer user to the ``docker group`` in your machine

#### Install virtualenv
```bash
pip install virtualenv virtualenvwrapper
```

#### Setup your virtual environments
Create a directory for your virtual environments e.g.:
```bash
mkdir ~/Python_Envs
```

You might want to add to your .bashrc file these two lines:
```bash
export WORKON_HOME=~/Python_Envs
source /usr/local/bin/virtualenvwrapper.sh
```

Then you can source your ``.bashrc`` and create a new Python3 virtual environment:

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

#### Checkout the Github repo
```bash
git clone https://github.com/FNNDSC/ChRIS_ultron_backEnd.git
```

#### Install useful python tools in your virtual environment
```bash
cd ChRIS_ultron_backEnd
workon chris_env
pip install httpie
pip install python-swiftclient
pip install django-storage-swift
```

You can also install some python libraries (not all of them) specified in the ``requirements/base.txt`` and 
``requirements/local.txt`` files in the source repo


To list installed dependencies in chris_env:
```
pip freeze --local
```

#### Containerized data/processing services:

* ``pfcon``
* ``pfioh``
* ``pman``


### Instantiate CUBE

Start CUBE from the repository source directory by running the make bash script

```bash
./docker-make.sh
```
All the steps performed by the above script are properly documented in the script itself. 

After running this script all the automated tests should have successfully run and a Django development server should be running in interactive mode in this terminal.


### Rerun automated tests after modifying source code

Open another terminal and run 
```bash
docker ps
```
Find out from the previous output the name of the container running the Django server in interactive mode (usually *chrisultronbackend_chris_dev_run_1*) and run the Unit tests and Integration tests within that container. 

To run only the Unit tests:

```bash
docker exec -it chrisultronbackend_chris_dev_run_1 python manage.py test --exclude-tag integration
```

To run only the Integration tests:

```bash
docker exec -it chrisultronbackend_chris_dev_run_1 python manage.py test --tag integration
```

To run only the Integration tests if the environment has not been restarted in interactive mode (usual for debugging when the make script has been passed a ``-i``:

```bash
docker exec -it chrisultronbackend_chris_dev_1 python manage.py test --tag integration
```


To run all the tests:

```bash
docker exec -it chrisultronbackend_chris_dev_run_1 python manage.py test 
```

After running the Integration tests the ./FS/remote directory **must** be empty otherwise it means some error has occurred and you should manually empty it.


### Check code coverage of the automated tests
Make sure the **chris_backend/** dir is world writable. Then type:

```bash
docker exec -it chrisultronbackend_chris_dev_run_1 coverage run --source=feeds,plugins,uploadedfiles,users manage.py test
docker exec -it chrisultronbackend_chris_dev_run_1 coverage report
```


### Using httpie to play with the REST API 
A simple GET request:
```bash
http -a cube:cube1234 http://localhost:8000/api/v1/
```
A simple POST request:
```bash
http -a cube:cube1234 POST http://localhost:8000/api/v1/plugins/1/instances/ Content-Type:application/vnd.collection+json Accept:application/vnd.collection+json template:='{"data":[{"name":"dir","value":"./"}]}'
```


### Using swift client to list files in the users bucket
```bash
swift -A http://127.0.0.1:8080/auth/v1.0 -U chris:chris1234 -K testing list users
```


### Destroy CUBE

Stop and remove CUBE services and storage space by running the destroy bash script from the repository source directory

```bash
./docker-destroy.sh
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
