### Setup ubuntu
* upgrade python to 3.10 - check this out: https://cloudbytes.dev/snippets/upgrade-python-to-latest-version-on-ubuntu-linux
* install docker
<pre>
$ curl -fsSL https://get.docker.com -o get-docker.sh
$ sudo sh ./get-docker.sh
</pre>
* docker post install
<pre>
$ sudo groupadd docker
$ sudo usermod -aG docker $USER
$ newgrp docker
</pre>

* check docker using ``$ docker run hello-world`` 
* retrieve network subnet from docker default bridge network: ``$ docker network inspect bridge`` e.g. "Subnet": "172.17.0.0/16"
* in windows using a powershell in admin mode run ``route print`` to see all network routes
* retrieve the ip of the ubuntu multipass instance (gateway) by ``multipass list``
* add a new route in windows to the docker network bridge (might need to adapt to the bridge settings): <br>
 ``route ADD bridge_subnet MASK bridge_subnet multipass_gateway`` e.g. ``route ADD 172.18.0.0 MASK 255.255.0.0 172.26.109.239``


* in ubuntu enable forwarding from Docker containers to the outside world (and vice versa):
<pre>
$ sudo sysctl net.ipv4.conf.all.forwarding=1
$ sudo iptables -P FORWARD ACCEPT
</pre>


#### Update Python
<pre>
$ sudo add-apt-repository ppa:deadsnakes/ppa
$ sudo apt update
$ apt list | grep python3.10

$ sudo apt install python3.10

$ sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.8 1
$ sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 2

$ sudo update-alternatives --config python3
-- select python3.10 manual mode--

$ sudo apt remove python3.8
$ sudo apt autoremove

$ sudo apt install python3.10-distutils

$ curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
$ python3.10 get-pip.py

$ sudo apt install python3.10-venv

$ sudo apt remove --purge python3-apt
$ sudo apt autoremove
 </pre>

Check if everything works correctly: ``python3.10 --version``
Relog (type ``exit`` and then in the PS ``multipass shell dw``) and try pip, should be for version 3.10: ``pip --version``:

#### Setup quick access commands for development
* Open the bashrc: ``nano ~/.bashrc`` 
* move down and add:
<pre>
alias setup='source setup.sh'
alias r='bash run.sh'
alias s='bash stop.sh'
</pre>
These commands only work in the droneworks base directory.
Relog to apply changes to shell.

