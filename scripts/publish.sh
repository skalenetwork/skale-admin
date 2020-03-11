#!/usr/bin/env bash
set -e

NAME=admin
REPO_NAME=skalenetwork/$NAME
IMAGE_NAME=$REPO_NAME:$VERSION
LATEST_IMAGE_NAME=$REPO_NAME:latest

: "${DOCKER_USERNAME?Need to set DOCKER_USERNAME}"
: "${DOCKER_PASSWORD?Need to set DOCKER_PASSWORD}"

echo "$DOCKER_PASSWORD" | docker login --username $DOCKER_USERNAME --password-stdin
docker push $IMAGE_NAME || exit $?
if [ "$RELEASE" = true ]
then
    docker push $LATEST_IMAGE_NAME || exit $?
fi