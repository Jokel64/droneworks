if [[ -z "${DRONEWORKS_DOCKER_IMAGE_NAME}" ]]; then
  echo "DRONEWORKS_DOCKER_IMAGE_NAME not defined. Please run setup.sh."
  exit 0
fi

if [[ -z "${DRONEWORKS_NUM_NODES}" ]]; then
  echo "DRONEWORKS_NUM_NODES not defined. Please run setup.sh."
  exit 0
fi


NAME=drone-node-dev
docker run -it -d --name $NAME $DRONEWORKS_DOCKER_IMAGE_NAME
echo "Started $NAME"

