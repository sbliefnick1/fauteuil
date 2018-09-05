#!/usr/bin/env bash

set -e

no1="testbox1"
no2="testbox2"
no3="testbox3"

docker-machine restart ${no1}

docker-machine ssh ${no2} "docker swarm leave"
docker-machine ssh ${no3} "docker swarm leave"

docker node rm ${no2}
docker node rm ${no3}

token=$(docker swarm join-token -q worker)
managerip=$(docker-machine ip testbox1):2377

docker-machine ssh ${no2} "docker swarm join --token $token $managerip"
docker-machine ssh ${no3} "docker swarm join --token $token $managerip"

docker node update --label-add type=celred ${no2}
docker node update --label-add type=worker ${no3}
