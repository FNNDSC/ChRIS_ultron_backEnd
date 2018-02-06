# ChRIS_ultron_backEnd
[![Build Status](https://travis-ci.org/FNNDSC/ChRIS_ultron_backEnd.svg?branch=master)](https://travis-ci.org/FNNDSC/ChRIS_ultron_backEnd)
[![Code Climate](https://codeclimate.com/github/FNNDSC/ChRIS_ultron_backEnd/badges/gpa.svg)](https://codeclimate.com/github/FNNDSC/ChRIS_ultron_backEnd)

Back end for ChRIS Ultron. This is a Django-MySQL project.

## ChRIS development and testing

### Abstract

This page describes how to quickly get the set of services comprising the backend up and running for development and how to run the automated tests.

### Preconditions

#### Currently tested platforms
* ``Docker 17.04.0+``
* ``Docker Compose 1.10.0+``
* ``Ubuntu (16.04/17.04/17.10) and MAC OS X 10.11+``

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
source .bashrc
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
pip install httpie
pip install django-storage-swift
pip install docker
```

You can also install some python libraries (not all of them) specified in the ``requirements/local.txt`` and 
``requirements/local.txt`` files within the source repo


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
cd ChRIS_ultron_backEnd
./docker-make-chris_dev.sh
```
All the steps performed by the above script are properly documented in the script itself. 

After running this script all the automated tests should have successfully run and a Django development server should be running in interactive mode in this terminal.

### Rerun automated tests after modifying source code

Open another terminal and run 
```bash
docker ps
```
Find out from the previous output the name of the container running the Django server in interactive mode (usually *chrisultronbackend_chris_dev_run_1*) and run the Unit tests and Integration tests within that container. For instance to run only the Unit tests:

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
http http://localhost:8000/api/v1/
```
A simple POST request:
```bash
http -a cube:cube1234 POST http://localhost:8000/api/v1/plugins/1/instances/ Content-Type:application/vnd.collection+json Accept:application/vnd.collection+json template:='{"data":[{"name":"dir","value":"./"}]}'
```

### Using swift client to list files in the users bucket
swift -A http://127.0.0.1:8080/auth/v1.0 -U chris:chris1234 -K testing list users


### REST API Documentation
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
