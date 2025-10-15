<!--
Copyright 2025, Amazon Web Services, Inc. or its affiliates. All rights reserved. Amazon Confidential and Trademark. This work is licensed under a Creative Commons Attribution 4.0 International License.
-->
# EC2 CPU stress
Instructions for deploying a simple web app to use with the ec2-cpu-stress demonstration experiment.

## How it works:
- Flask app is running on port 8080
- Browser connects to `http://{instance-public-IP}` on port 80
- Nginx receives request on port 80 and forwards to 127.0.0.1:8080
- Flask processes request on port 8080 and returns response
- Nginx returns response to browser

## Prerequisites
- An EC2 instance running AL2023. The experiment will load the CPU on the instance, so make sure it's not a critical instance.

## Nginx
- Install Nginx
```bash
sudo dnf install nginx -y
```
- Create proxy configuration in `/etc/nginx/conf.d/flask-proxy.conf`
```
server {
    listen 80;
    server_name _;

    location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    }
}
```
- Start the service
```bash
sudo systemctl start nginx
sudo systemctl enable nginx
```
- Update security group attached to the instance. Add port TCP port 80 from `0.0.0.0/0` (or more specific IP range)

## Configure environment
```bash
export AWS_DEFAULT_REGION={region}
export AWS_CA_BUNDLE=/etc/pki/{region}/certs/ca-bundle.pem
```

## Python
- Create a directory for the app and copy the script to it
```bash
mkdir ec2-cpu-stress
# Copy ec2-cpu-stress.py to the directory
```
- ISOLATED REGIONS ONLY: Configure for available PyPi repo
- Create and activate .venv
```bash
python3 -m venv .venv
source .venv/bin/activate
```
- Install requirements
```bash
pip install -r requirements.txt
```
- Run script
```bash
python3 ec2-cpu-stress.py
```
- Go to `http://{instance-public-IP}` in browser to see output

## Experiment
- Create an experiment template in FIS using the **EC2 Stress: CPU** example from the scenario library. Specify the instance where the web app is running as the target.
- Copy the example `ec2-cpu-stress.json` as input for the Chaos Machine. Update the `experimentTemplateId`.
- Start execution
