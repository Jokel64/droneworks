# Droneworks
A distributed system approach for coordinating drones.

To generate the Docker images and setup the environment variables run
```source setup.sh```

Edit the exports in setup.sh to change the number of drones.

To start all drones run ```bash run.sh```

To start a single drone in dev mode (container is permanent) run ```bash dev.sh```

To stop all drones run ```bash stop.sh```

## Access and Control
Each drone hosts a webserver with basic information on port 3300. If the drone 
is the leader drone it also runs an advance dash (plotly) interface on port 8050.
To determine which node is the leader drone access one of the regular drones. 
The leader drone is given in the node list.
