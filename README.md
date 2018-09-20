# fauteuil
Fauteuil is an integration of Docker and Apache Airflow, designed to be deployed
on a multi-node cluster. This has been used on nodes running CentOS 7.5. Aside
from a few OS-specific changes to set up details and replacing configurations 
and DAGs with your own, you should be able to deploy this repo with minimal
reworking. Fauteuil may work with other versions of Docker but I have developed
it using v18.06.1-ce on High Sierra 10.13.6. 

Fauteuil means *armchair* in
French, and I wanted a completely distinct word to refer to the project while
'getting comfortable' with Docker and Airflow.

## Getting Started with a Local (Test) Deployment

These instructions will get you a copy of the project up and running on your 
local machine for development and testing purposes. See deployment for notes on 
how to deploy the project on a live system.

### Prerequisites
- Git
- Docker
- Python >= 3.5 

### Deployment-Specific Configurations 
- `config/airflow.cfg`
- `config/odbcinst.ini`
- `secrets/{dev,prod,test}/fernet_key`
- `secrets/{dev,prod,test}/flask_secret_key`
- `secrets/{dev,prod,test}/pg_password`
- `secrets/freetds.conf`
- `secrets/odbc.ini`
- `docker-compose.yml`

### Installation and Setup
- Clone the repo
  - `$ git clone https://github.com/sbliefnick1/fauteuil.git`
- Create a 4MB RAM VM for your test environment using the virtualbox driver
  - `$ docker-machine create -d virtualbox --virtualbox-memory 4096 testbox1`
- Initialize the machine as a Swarm manager
  - `$ docker-machine ssh testbox1 "docker swarm init"`
- Set your environment to execute directly on the machine
  - `$ eval $(docker-machine env testbox1)`
- Verify your environment is set correctly
  - `$ docker-machine ls` should show an asterisk next to the machine name
  - `$ docker node ls` should not return an error
- Add labels to the machine
  - `$ docker node update --label-add class=celred testbox1`
  - `$ docker node update --label-add type=postgres testbox1`
  - `$ docker node update --label-add role=worker testbox1`
- Prepare secrets files
  - `python -c "from cryptography.fernet import Fernet; 
  print(Fernet.generate_key().decode())" > secrets/test/fernet_key`
  - `$ openssl rand -base64 24 | tr -d "+=/" > secrets/test/flask_secret_key`
  - `$ openssl rand -base64 24 | tr -d "+=/" > secrets/test/pg_password`
  - `$ echo airflow > secrets/pg_db`
  - `$ echo airflow > secrets/pg_user`
  - Optional if you want to use ODBC/DSN connections:
```bash
$ cat > secrets/freetds.conf << EOF
[db_alias]
host = yourservername
port = 1433
tds version = 7.0 
EOF
```
```bash
$ cat > secrets/odbc.ini << EOF
[dsn_name]
Driver=FreeTDS
Server=yourserver
Port=1433
Database=yourdb
TDS version=7.0
Trace=No
EOF
```
- Create secrets
  - `$ docker secret create fernet_key secrets/test/fernet_key`
  - `$ docker secret create flask_secret_key secrets/test/flask_secret_key`
  - `$ docker secret create pg_password secrets/test/pg_password`
  - `$ docker secret create pg_db secrets/pg_db`  
  - `$ docker secret create pg_user secrets/pg_user`
  - `$ docker secret create freetds.conf secrets/freetds.conf`
  - `$ docker secret create odbc.ini secrets/odbc.ini`
- Alter configuration
  - If necessary, alter the ports to be exposed in `docker-compose.yml`
  - Look through `config/airflow.cfg` and make any necessary changes, e.g., 
`default_timezone` under `[core]`
  - If you're running on a laptop, you might want to halve the `dag_concurrency`
and `parallelism`
  - Change out the DAGs in the `dags` directory 
- Deploy
  - `$ docker stack deploy -c docker-compose.yml -c test.yml airflow`
- Verify
  - `$ docker service ls`
  - Go to your VM's IP address in a web browser and add `:9090` to see the 
  Docker visualizer show the status of your containers.

## Multi-Node (Prod/Dev) Deployment
- Configure ssh access to the nodes which will be part of the Swarm
  - `$ ssh-keygen -t ecdsa -b 521`
  - Return twice (no password)
  - `$ ssh-copy-id -i ~/.ssh/id_ecdsa.pub youruser@yourmachine`
- Open ports on the nodes
  - `$ sudo firewall-cmd --zone=public --add-port=2377/tcp --permanent` 
  - Repeat for `2376/tcp`, `7946/tcp`, `7946/udp`, `4789/udp`
  - `$ sudo firewall-cmd --reload`
- Install Docker on all the nodes
  - `$ sudo yum install -y yum-utils device-mapper-persistent-data lvm2`
  - `$ sudo yum-config-manager --add-repo 
  https://download.docker.com/linux/centos/docker-ce.repo`
  - `$ sudo yum install docker-ce`
  - `$ sudo systemctl start docker`
  - `$ sudo systemctl enable docker` to maker Docker start on boot
- Configure the user you want to run Docker to have no-password sudo access
  - `$ sudo visudo`
  - `youruser   ALL=(ALL)   NOPASSWD: ALL`
- Configure your local Docker daemon to control the ones on the nodes
  - `$ docker-machine create --driver generic --generic-ip-address=XXX.XXX.XXX.XXX
  --generic-ssh-key .ssh/id_ecdsa --generic-ssh-user youruser yourmachine`
- Add any relevant users to Docker group 
  - `$ sudo usermod -aG docker youruser`
  - Log out and back in to take effect
  - Verify membership with `$ grep docker /etc/group`
- Initialize the Swarm manager
  - `$ eval $(docker-machine env yourmanager)`
  - `$ docker swarm init`
- Join workers to manager
  - `$ token=$(docker swarm join-token -q worker)`
  - `$ managerip=$(docker-machine ip yourmanager):2377`
  - `$ docker-machine ssh yourworker1 "docker swarm join --token $token 
  $managerip`
  - Repeat last command for all worker nodes
  - Verify status with `$ docker node ls`
- Continue with adding node labels as above under `Installation and Setup`, 
changing filepaths, etc., as needed to reflect the dev or prod environment
  - **Important** Be sure to check the node labels under `prod.yml` and 
   verify they reflect the prod environment node labels accurately

## Author

- **Soren Bliefnick**

## License

This project is licensed under the Apache License - see the [LICENSE](LICENSE)
 file for details

## Acknowledgments

- The [Apache Airflow](https://github.com/apache/incubator-airflow) project
- [Puckel](https://github.com/puckel/docker-airflow) on whose work this was
based
- [Devilrancy](https://github.com/devilrancy) whose pull request for adding
Swarm support on the above allowed me to finally understand how to configure
Swarm successfully
