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

To create the development database, do

```
sudo mysql
```

Now create a local database on MySQL's shell:

````
CREATE DATABASE chris_dev CHARACTER SET utf8;
````

This ensures all tables and columns will use UTF-8 by default

Grant all privileges to user chris on the database:

````
GRANT ALL ON chris_dev.* TO 'chris'@'localhost' IDENTIFIED BY 'Chris1234';
````

### Check out the repo

Now, check out the repo:

```
git clone https://github.com/FNNDSC/ChRIS_ultron_backEnd.git
```

### Dependencies:
This project uses requirement files to install dependencies in chris_env through pip:

````
cd ChRIS_ultron_backEnd
pip install -r requirements/local.txt
````

To list installed dependencies in chris_env:

````
pip freeze --local
````

### Testing:
````
cd chris_backend
python manage.py migrate
python manage.py test
````
If errors are gotten because of user chris not having enough database privilages then
just give it all privilages in mysql:

````
GRANT ALL PRIVILEGES ON *.* TO 'chris'@'localhost';
````

### First steps

(See here for detailed instructions:

First, create two users (one called 'chris' and one called <yourusername>)

```
# for user 'chris'
python manage.py createsuperuser
```

and again:

```
# for user <yourusername>
python manage.py createsuperuser
```

Now you can start the backend server

```
python manage.py runserver
```

Perform a simple GET request:

```
http http://127.0.0.1:8000/api/v1/
```

#### Troubleshooting

You might experience some issues with localhost/actual IP depending on local setup and possibly if you have a proxy. In that case, start the server with an actual <IP>:<port> 

```
python manage.py runserver XXX.YYY.ZZZ.WWW:8000
```

and connect to it explicitly:

```
http http://XXX.YYY.ZZZ.WWW:8000/
```

### Testing the API over HTTPS

Run modwsgi Apache-based server:
```
python manage.py runmodwsgi --host 0.0.0.0 --port 8001 --https-port 8000 --ssl-certificate-file ../utils/ssl_cert/local.crt --ssl-certificate-key-file ../utils/ssl_cert/local.key --processes 8 --server-name localhost --https-only --reload-on-changes
```

Make requests over https with the self-signed SSL certificate:

```
http https://localhost:8000/api/v1/ --verify=../utils/ssl_cert/local.crt
```

Self-signed "localhost" certificates can be generated again if necessary:
```
openssl req -x509 -sha256 -nodes -newkey rsa:2048 -days 365 -keyout local.key -out local.crt  (server name should be set to "localhost" in the interactive questions)
```

### Documentation

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
