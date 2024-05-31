# Docker platform of NoiseSensor

This platform aim to deploy sensors on raspberry pi over an OpenVPN private network.

All RPI are driven by an Ansible Semaphore software.


# OpenVPN

* Initialize the configuration files and certificates

```bash
docker compose run --rm openvpn ovpn_genconfig -u udp://VPN.SERVERNAME.COM
docker compose run --rm openvpn ovpn_initpki
```

* Fix ownership (depending on how to handle your backups, this may not be needed)

```bash
sudo chown -R $(whoami): ./openvpn-data
```

* Change settings to expose openvpn management console

Edit the file `openvpn-data/conf/openvpn.conf`, add the following line

```ini
duplicate-cn
management 0.0.0.0 5555 telnetpwd
```

duplicate-cn because RPI key files are cloned into the SD card, but you could also not add this and push one key for each RPI, so you could revoke a key if a raspberry-pi has been stolen.

Push your own password for openvpn control management into the file

```shell
sudo echo "YOUR_OPENVPN_MANAGEMENT_CONSOLE_PASSWORD" > openvpn-data/conf/telnetpwd
sudo chmod 600 openvpn-data/conf/telnetpwd
```

* Start OpenVPN server process

```bash
docker compose up -d openvpn
```

* You can access the container logs with

```bash
docker compose logs -f
```

* Generate a client certificate

```bash
export CLIENTNAME="rpi"
# with a passphrase (recommended)
sudo docker compose run --rm openvpn easyrsa build-client-full $CLIENTNAME
# without a passphrase (not recommended)
sudo docker compose run --rm openvpn easyrsa build-client-full $CLIENTNAME nopass
```

* Retrieve the client configuration with embedded certificates

```bash
sudo docker compose run --rm openvpn ovpn_getclient $CLIENTNAME > $CLIENTNAME.ovpn
```

* Revoke a client certificate

```bash
# Keep the corresponding crt, key and req files.
docker compose run --rm openvpn ovpn_revokeclient $CLIENTNAME
# Remove the corresponding crt, key and req files.
docker compose run --rm openvpn ovpn_revokeclient $CLIENTNAME remove
```

## Debugging Tips

* Create an environment variable with the name DEBUG and value of 1 to enable debug output (using "docker -e").

```bash
docker compose run -e DEBUG=1 -p 1194:1194/udp openvpn
```

# Ansible Semaphore and Elastic Stack


Create a file named .env in this folder with your own generated credentials for the docker compose:

```shell
MYSQL_PASSWORD=DATABASE_PASSWORD
SEMAPHORE_ADMIN_PASSWORD=YOUR_ADMIN_PASSWORD
SEMAPHORE_ACCESS_KEY_ENCRYPTION="YOUR_RANDOM_KEY"
# Password for the 'elastic' user (at least 6 characters)
ELASTIC_PASSWORD=myElasticPassword

# Password for the 'kibana_system' user (at least 6 characters)
KIBANA_PASSWORD=myKibanaPassword

# Version of Elastic products
STACK_VERSION=8.6.2

# Set the cluster name
CLUSTER_NAME=docker-cluster

# Set to 'basic' or 'trial' to automatically start the 30-day trial
LICENSE=basic
#LICENSE=trial

# Port to expose Elasticsearch HTTP API to the host
ES_PORT=9200
#ES_PORT=127.0.0.1:9200

# Port to expose Kibana to the host
KIBANA_PORT=5601
#KIBANA_PORT=80

# Increase or decrease based on the available host memory (in bytes)
MEM_LIMIT=28073741824

# If you publish kibana on internet, you should declare it with this parameter
KIBANA_URL=https://kibana.mydomain.org

OPENVPN_MANAGEMENT_PASSWORD=YOUR_OPENVPN_MANAGEMENT_CONSOLE_PASSWORD
```

SEMAPHORE_ACCESS_KEY_ENCRYPTION value is generated with (you can generate other password with this tool too)

```shell
head -c32 /dev/urandom | base64
```

# Create dynamic raspberry-pi ansible inventory using OpenVPN management console

- Create project
- Create empty key (for https)
- Declare raspberry-pi ssh key
- Declare https git repository (https://github.com/Universite-Gustave-Eiffel/Rail4Earth.git main)
- Declare localhost inventory
- Create empty environment
- Declare the following playbook that will create a file in that will contain all RPI connected in OpenVPN:

```services/ansible_openvpn/playbooks/fetch_openvpn_hosts.yml```

- Connect to dashboard and retrieve the automated created elastic search api key in /home/dashboard/certs/api.json
This playbook use the following environment variable, it has to be set in environment in semaphore web gui:

```json
{ 
  "MANAGEMENT_OPENVPN_PORT": "5555",
  "MANAGEMENT_OPENVPN_PASSWORD": "YOUR_OPENVPN_MANAGEMENT_CONSOLE_PASSWORD",
  "ELASTIC_SEARCH_API_KEY_ID": "id",
  "ELASTIC_SEARCH_API_KEY": "api_key"
}
```
- Run the playbook and declare the following file inventory `/home/semaphore/hosts.json`



# OpenVPN management

You can run commands in the openVPN machine with this command

```sh
sudo docker exec -ti openvpn /bin/bash
```

