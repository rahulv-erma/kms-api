#!/bin/bash

git pull origin develop &&
docker compose -f docker-compose.dev.yml build &&
docker compose -f docker-compose.dev.yml push &&
docker stack rm abc_api &&
sleep 5 &&
docker stack deploy -c docker-compose.dev.yml abc_api