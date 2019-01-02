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
  - `$ ssh-copy-id -i ~/.ssh/id_ecdsa.pub youruser@yourmachine`
  - Repeat for each additional node
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
```
- Configure the user you want to run Docker to have no-password sudo access
  - `$ sudo visudo`
  - `youruser   ALL=(ALL)   NOPASSWD: ALL`
  
### Docker configuration
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
- Add labels to the machine
  - `$ docker node update --label-add type=postgres yourmachine2`
  
### Deployment-Specific Configuration
- Prepare secrets files
```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" > secrets/test/fernet_key
  openssl rand -base64 24 | tr -d "+=/" > secrets/test/flask_secret_key
  openssl rand -base64 24 | tr -d "+=/" > secrets/test/pg_password
  echo airflow > secrets/pg_db
  echo airflow > secrets/pg_user
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
  docker secret create fernet_key secrets/test/fernet_key
  docker secret create flask_secret_key secrets/test/flask_secret_key
  docker secret create pg_password secrets/test/pg_password
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
yum install nfs-utils
mkdir /var/nfsshare
chmod -R 777 /var/nfsshare
chown nfsnobody:nfsnobody /var/nfsshare
systemctl enable rpcbind
systemctl enable nfs-server
systemctl enable nfs-lock
systemctl enable nfs-idmap
systemctl start rpcbind
systemctl start nfs-server
systemctl start nfs-lock
systemctl start nfs-idmap
```

  - Edit the exports file with `$ vim /etc/exports` and add an entry as follows
for each client machine you wish to be able to access the shared directory 
(change for your relevant IPs):
```bash
/var/nfsshare   192.168.0.101(rw,sync,no_root_squash,no_all_squash)
```

  - Start the NFS service
    - `$ systemctl restart nfs-server`

  - Allow firewall settings
```bash
firewall-cmd --permanent --zone=public --add-service=nfs
firewall-cmd --permanent --zone=public --add-service=mountd
firewall-cmd --permanent --zone=public --add-service=rpc-bind
firewall-cmd --reload
```

- On the client machines (worker nodes)
```bash
yum install nfs-utils
mkdir -p /var/nfsshare
mount -t nfs yournfsserver:/var/nfsshare /var/nfsshare
```
  - Permanently mount the directories by putting entries in your fstab
   with `$ vim /etc/fstab`:
```bash
yournfsserver:/var/nfsshare     /var/nfsshare   nfs defaults 0 0
```
  
### Double Check Before Deploying
- Alter configuration
  - If necessary, alter the ports to be exposed in `docker-compose.yml`
  - Look through `config/airflow.cfg` and make any necessary changes, e.g., 
`default_timezone` under `[core]`
  - Make sure that `/var/nfsshare/dags` exists to store the DAGs in as 
  specified in `config/airflow.cfg`
- Deploy
  - `$ docker stack deploy -c docker-compose.yml -c dev.yml airflow`
- Verify
  - `$ docker service ls`
  - Go to your server's IP address in a web browser and add `:9090` to see the 
  Docker visualizer show the status of your containers
- **Important** Be sure to check the node labels under `prod.yml` and 
   verify they reflect the prod environment node labels accurately before
   trying to deploy to production

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
