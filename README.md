# ChRIS_ultron_backEnd
Back end for ChRIS Ultron.

## Development environment
This is a Django-MySQL project.

On ubuntu:
````
sudo apt-get update
sudo apt-get install git
sudo apt-get install mysql-server
sudo apt-get install python-pip python3-dev libmysqlclient-dev
sudo pip install virtualenv virtualenvwrapper
````

Create a directory for your virtual environments e.g.:

````
mkdir ~/Python_Envs
````

You might want to add to your .bashrc file these two lines:

````
export WORKON_HOME=~/Python_Envs
source /usr/local/bin/virtualenvwrapper.sh
````

Then you can source your .bashrc and create a new Python3 virtual environment:

````
source .bashrc
mkvirtualenv --python=python3 chris_env
````

To activate chris_env:

````
workon chris_env
````

To deactivate chris_env:

````
deactivate
````

### Development database:
When creating your local database on MySQL's shell use:

````
CREATE DATABASE chris_dev CHARACTER SET utf8;
````

This ensures all tables and columns will use UTF-8 by default

Grant all privileges to user chris on the database:

````
GRANT ALL ON chris_dev.* TO 'chris'@'localhost' IDENTIFIED BY 'Chris1234';
````

### Dependencies:
This project uses requirement files to install dependencies in chris_env through pip:

````
pip install -r requirements/local.txt
````

To list installed dependencies in chris_env:

````
pip freeze --local
````

### Testing:
````
python manage.py test
````
If errors are gotten because of user chris not having enough database privilages then
just give it all privilages in mysql:

````
GRANT ALL PRIVILEGES ON *.* TO 'chris'@'localhost';
````
