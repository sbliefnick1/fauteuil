# fauteuil
Fauteuil is an integration of [Docker](https://www.docker.com/) and 
[Apache Airflow](https://github.com/apache/airflow) (whose explanations are beyond the scope of this project), designed to be deployed
on a multi-node cluster. This has been used on nodes running CentOS 7.5. Aside
from a few OS-specific changes to set up details and replacing configurations 
and DAGs with your own, you should be able to deploy this repo with minimal
reworking. Fauteuil may work with other versions of Docker but I have developed
it using v18.09.1-ce on High Sierra 10.13.6. 

Fauteuil means *armchair* in
French, and I wanted a completely distinct word to refer to the project while
'getting comfortable' :sunglasses: with Docker and Airflow.

## Getting Started with a Multi-Node Development Deployment

These instructions will get you a copy of the project up and running on a 
multi-node cluster for development purposes. A production setup would be similar,
although likely with more nodes and different passwords.

### Prerequisites
- Git
- Docker
- Python >= 3.5 

### Deployment-Specific Configurations Within Fauteuil
- `config/airflow.cfg`
- `config/odbcinst.ini`
- `secrets/{dev,prod}/base_url`
- `secrets/{dev,prod}/fernet_key`
- `secrets/{dev,prod}/flask_secret_key`
- `secrets/{dev,prod}/pg_password`
- `secrets/freetds.conf`
- `secrets/odbc.ini`
- `docker-compose.yml`

## Installation and Setup
- Clone the repo
```bash
  git clone https://github.com/sbliefnick1/fauteuil.git
```

### Node configuration
- Configure ssh access to the nodes which will be part of the Swarm
  - `$ ssh-keygen -t ecdsa -b 521`
  - Return twice (no password)
  - You'll probably want to do this as yourself and the user you want to execute
  Docker commands on the nods
  - `$ ssh-copy-id -i ~/.ssh/id_ecdsa.pub youruser@yourmachine`
  - Repeat for each additional node
- Configure the user you want to run Docker to have no-password sudo access on 
the nodes
  - `$ sudo visudo`
  - `youruser   ALL=(ALL)   NOPASSWD: ALL`
- Open ports on the nodes
  - `$ sudo firewall-cmd --zone=public --add-port=2377/tcp --permanent` 
  - Repeat for `2376/tcp`, `7946/tcp`, `7946/udp`, `4789/udp`
  - `$ sudo firewall-cmd --reload`
- Install Docker on all the nodes
```bash
  sudo yum install -y yum-utils device-mapper-persistent-data lvm2
  sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
  sudo yum install docker-ce
  sudo systemctl start docker
  sudo systemctl enable docker  # to maker Docker start on boot
  sudo yum install git  # if you need it for the DAGs folder, for example
```
  
### Docker configuration
- Configure your local Docker daemon to control the ones on the nodes
  - Make sure you don't have an active SSH connection to the node you're trying
  to configure
  - Also make sure you've SSHed into each box as yourself and as the Docker user
  - `$ docker-machine create --driver generic --generic-ip-address=XXX.XXX.XXX.XXX
  --generic-ssh-key ~/.ssh/id_ecdsa --generic-ssh-user youruser yourmachine`
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
  $managerip"`
  - Repeat last command for all worker nodes
  - Verify status with `$ docker node ls`
- Add labels to the machine
  - `$ docker node update --label-add type=postgres yourmachine2`
  
### Deployment-Specific Configuration
- Prepare secrets files
```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > secrets/dev/fernet_key
  openssl rand -base64 24 | tr -d "+=/" > secrets/dev/flask_secret_key
  openssl rand -base64 24 | tr -d "+=/" > secrets/dev/pg_password
  echo airflow > secrets/pg_db
  echo airflow > secrets/pg_user
  echo "https://yourmachine" > base_url
```
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
- Create secrets (run this on a manager node)
```bash
  eval $(docker-machine env yourmanager1)
  docker secret create base_url secrets/dev/base_url
  docker secret create fernet_key secrets/dev/fernet_key
  docker secret create flask_secret_key secrets/dev/flask_secret_key
  docker secret create pg_password secrets/dev/pg_password
  docker secret create pg_db secrets/pg_db
  docker secret create pg_user secrets/pg_user
  docker secret create freetds.conf secrets/freetds.conf
  docker secret create odbc.ini secrets/odbc.ini
```
  
### NFS Configuration
We use an NFS shared directory to sync the DagBag across nodes easily, and
without having to rebuild the Docker image every time.

- On the server machine (manager or other designated DAG repo node)
```bash
sudo yum install nfs-utils
sudo mkdir /var/nfsshare
sudo chmod -R 777 /var/nfsshare
sudo chown nfsnobody:nfsnobody /var/nfsshare
sudo systemctl enable rpcbind
sudo systemctl enable nfs-server
sudo systemctl enable nfs-lock
sudo systemctl enable nfs-idmap
sudo systemctl start rpcbind
sudo systemctl start nfs-server
sudo systemctl start nfs-lock
sudo systemctl start nfs-idmap
```

  - Edit the exports file with `$ vi /etc/exports` and add an entry as follows
for each client machine you wish to be able to access the shared directory 
(change for your relevant IPs):
```bash
/var/nfsshare   192.168.0.101(rw,sync,no_root_squash,no_all_squash)
```

  - Start the NFS service
    - `$ systemctl restart nfs-server`

  - Allow firewall settings
```bash
sudo firewall-cmd --permanent --zone=public --add-service=nfs
sudo firewall-cmd --permanent --zone=public --add-service=mountd
sudo firewall-cmd --permanent --zone=public --add-service=rpc-bind
sudo firewall-cmd --reload
```

- On the client machines (worker nodes)
```bash
sudo yum install nfs-utils
sudo mkdir -p /var/nfsshare
sudo mount -t nfs yournfsserver:/var/nfsshare /var/nfsshare
```
  - Permanently mount the directories by putting entries in your fstab
   with `$ sudo vi /etc/fstab`:
```bash
yournfsserver:/var/nfsshare     /var/nfsshare   nfs defaults 0 0
```
  
### Double Check Before Deploying
- Alter configuration
  - If necessary, alter the ports to be exposed in 
  [`docker-compose.yml`](https://github.com/sbliefnick1/fauteuil/blob/v1-2/docker-compose.yml)
  - Look through [`config/airflow.cfg`](https://github.com/sbliefnick1/fauteuil/blob/v1-2/config/airflow.cfg)
   and make any necessary changes, e.g., `default_timezone` under `[core]`
  - Make sure that `/var/nfsshare/dags` exists to store the DAGs in as 
  specified in `config/airflow.cfg`
  - Check [`script/entrypoint.sh`](https://github.com/sbliefnick1/fauteuil/blob/v1-2/script/entrypoint.sh)
   because many of the `config/airflow.cfg` settings we override using environment variables
- Deploy
  - `$ docker stack deploy -c docker-compose.yml -c dev.yml airflow`
  - You can chain together `.yml` files when deploying in order to extend or 
  override settings in the previous file
- Verify
  - `$ docker service ls`
  - Go to your server's IP address in a web browser and add `:9090` to see the 
  Docker visualizer show the status of your containers
- **Important** Be sure to check the node labels under `prod.yml` and 
   verify they reflect the prod environment node labels accurately before
   trying to deploy to production
   
### Secure graphite and grafana
- Secure graphite Django admin
  - username: root
  - password: root
  - First log in at http://localhost:81/account/login
  - Then update the root user's profile at http://localhost:81/admin/auth/user/1/
- Secure grafana
  - username: admin
  - password: admin
  - If you pass an ldap.toml file you can log in as yourself and change the password or other attributes for admin, 
  or you can log in as admin and make changes as well
- Finally, create a new datasource in grafana pointing to graphite

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
