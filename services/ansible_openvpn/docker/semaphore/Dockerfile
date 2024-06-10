# syntax=docker/dockerfile:1.3-labs
FROM semaphoreui/semaphore:latest

ENV EASY_RSA_VERSION=3.2.0
ENV EASYRSA_PKI=/etc/openvpn/pki

USER root

RUN <<EOF
apk update && apk add openssl rsync py3-pip
wget -O- https://github.com/OpenVPN/easy-rsa/releases/download/v${EASY_RSA_VERSION}/EasyRSA-${EASY_RSA_VERSION}.tgz | tar -C /usr/local/bin -zx && mv /usr/local/bin/EasyRSA-${EASY_RSA_VERSION} /usr/local/bin/easyrsa && chown -R semaphore:root /usr/local/bin/easyrsa
mkdir /home/semaphore/data
chown -R semaphore:root /home/semaphore/
EOF

USER 1001

