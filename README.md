# Text Sentiment Classifier

## Introduction

Project focuses on implementing an efficient text summarization system. I leverage machine learning techniques to distill essential information from lengthy documents, providing concise and meaningful summaries.

This system aims to improve information access efficiency and advance information extraction technology. Model is built using Python libraries like pandas, scikit-learn, and joblib.

## Overall System Architecture

![image alt text](<images/text-sentiment-classifier.png>)

# Table of Contents
[Overall System Architecture](#overall-system-architecture)
1. [Text Sentiment Classifier](#text-sentiment-classifier)  
   1.1 [Introduction](#introduction)  
   1.2 [Project Structure](#project-structure)  
2. [Local](#local)  
   2.1 [Demo](#demo)  
   2.2 [Running in Docker](#running-in-docker)  
3. [Cloud](#cloud)  
   3.1 [Deploying to GCP](#deploying-to-gcp)  
   3.2 [CICD with Jenkins for GCE](#cicd-with-jenkins-for-gce)  
   3.3 [Monitoring](#monitoring)  
 
## Project Structure
```txt
├── terraform                 - Directory for Terraform to build GKE
├── jenkins-node              - Directory for Jenkins setup
├── helm-charts               - Directory for Helm chart to deploy the application
├── app                       - Python script for the application
├── model                     - Directory for model files
├── tests                     - Pytest code 
├── notebooks                 - notebook to build model
├── data                      - data to build model
├── Jenkinsfile               - Jenkins pipeline script to describe the CI/CD process
├── docker-compose.yaml       - Docker Compose configuration file
├── Dockerfile                - Dockerfile for building the image
├── requirements.txt          - Python requirements file
├── images                    - Directory for image files
└── README.md                 - This README file
```

# LOCAL
## Demo 

## Running in docker-compose

```
docker-compose up --build
```
The service can be accessed via http://localhost:30001/docs


# CLOUD
## Deploying to GCP


### Install Terraform
https://computingforgeeks.com/how-to-install-terraform-on-ubuntu/
```
wget https://releases.hashicorp.com/terraform/1.5.6/terraform_1.5.6_linux_amd64.zip
unzip terraform_1.5.6_linux_amd64.zip
sudo mv terraform /usr/local/bin/
terraform -version
```
![image alt text](<images/terraform-install.png>)

### Install Google Cloud CLI
https://cloud.google.com/sdk/docs/install
```shell
curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-linux-x86_64.tar.gz
tar -xf google-cloud-cli-linux-x86_64.tar.gz
./google-cloud-sdk/install.sh
```
![image alt text](<images/google-cloud-cli-nstall.png>)

Authenticate with GCP
```shell
gcloud auth application-default login
gcloud auth login
```

### Edit variables.tf with config you need

### Provision a new cluster
```shell
cd terraform
terraform init
terraform plan
terraform apply
cd ..
```
### Deploy NGINX-ingress
![image alt text](<images/nginx-ingress-install.png>)
```shell
kubectl create ns nginx-system
kubens nginx-system
helm upgrade --install nginx-ingress ./helm-charts/nginx-ingress
```
### Update host
- Replace the External IP above in `spec/rules/host` in file `helm-charts/model-deployment/templates/nginx-ingress.yaml`
![image alt text](<images/nginx-ingress-external-ip.png>)
```shell
kubectl get svc
```
### Deploy Model
![image alt text](<images/nginx-update-config.png>)
```shell
helm upgrade --install tsc ./helm-charts/model-deployment/ --namespace model-serving
```
### Get IP of nginx ingress service
![image alt text](<images/get-ip-of-nginx-ingress-service.png>)

```
kubectl get svc -n nginx-system
```

The service can be accessed via `http://[INGRESS_IP_ADDRESS].nip.com/docs`
![image alt text](<images/service-can-be-access-over-nip-com.png>)



## CICD with Jenkins

### Copy jenkin-node folder to your instance which created by terraform in previous step   
```
scp -r ./jenkins-node external-ip-of-your-instance:~/   
```
### Ssh to your instance
```
ssh external-ip-of-your-instance 
```
### Install Jenskins with Docker Compose
```
cd jenkins-node
chmod +x setup-jenkins.sh
./setup-jenkins.sh
```
![image alt text](<images/jenkins-type-Y-to-install.png>)
![image alt text](<images/jenkins-password.png>)

### Copy passsword after Jenkins installed & login with it
![image alt text](<images/jenkins-login.png>)
### http://external-ip-of-your-instance:8081
![image alt text](<images/jenkins-install-suggested-plugins.png>)
![image alt text](<images/jenkins-install-suggested-plugins-wait.png>)
![image alt text](<images/jenkins-getting-started.png>)
![image alt text](<images/jenkins-url.png>)
![image alt text](<images/jenkins-is-ready.png>)
![image alt text](<images/jenkins-welcome.png>)

### Intall plugin for Jenkins
Plugin for Jenkins: Docker, Docker Pipeline, Kubernetes plugin
![image alt text](<images/jenkins-docker-plugin.png>)
### Config Jenkins connect to Git Hub
 https://github.com/settings/tokens
![image alt text](<images/github-generate-new-token.png>)
![image alt text](<images/github-generate-new-token-2.png>)
![image alt text](<images/github-generate-new-token-3.png>)

 http://external-ip-of-your-instance:8081/manage/credentials/store/system/domain/_/newCredentials
 ![image alt text](<images/jenkins-create-github-credentials.png>)
### Config Jenkins connect to Docker Hub
 https://app.docker.com/settings/personal-access-tokens
![image alt text](<images/docker-hub-generate-token.png>)
![image alt text](<images/jenkins-create-dockerhub-credentials.png>)
### Config Github Webhook to Jenkins
![image alt text](<images/github-webhook-seting.png>)  
 http://external-ip-of-your-instance:8081/github-webhook/

### Install kubectl CLI on your computer
![image alt text](<images/kubectx-kubens-install.png>)
```
curl -LO https://dl.k8s.io/release/v1.33.0/bin/linux/amd64/kubectl
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

sudo git clone https://github.com/ahmetb/kubectx /opt/kubectx
sudo ln -s /opt/kubectx/kubectx /usr/local/bin/kubectx
sudo ln -s /opt/kubectx/kubens /usr/local/bin/kubens
```
### Connect to GKE Cluster
![image alt text](<images/gke-cluster-commandline-access.png>)
![image alt text](<images/gke-cluster-commandline-access-2.png>)

### Get Kubernetes URL
kubectl cluster-info | grep 'Kubernetes control plane' | awk '{print $NF}'
### Get CA Certificate
kubectl get secret jenkins-sa-token -n jenkins -o jsonpath='{.data.ca\.crt}' 
### Get token
kubectl get secret jenkins-sa-token -n jenkins -o jsonpath='{.data.token}' | base64 -d
### Add new Cloud on Jenkins
![image alt text](<images/jenkins-cloud-item-gke-cluster.png>)
![image alt text](<images/jenkins-cloud-item-credential.png>)
![image alt text](<images/jenkins-cloud-item-save.png>)
### Add new Item on Jenkins
![image alt text](<images/jenkins-create-new-item.png>)
![image alt text](<images/jenkins-create-new-item-2.png>)
### Push a commit to Github
![image alt text](<images/github-push-a-commit.png>)
### View Build Executor Status on Jenkins
![image alt text](<images/jenkins-executor-builder-status.png>)
![image alt text](<images/jenkins-console-output.png>)
![image alt text](<images/jenkins-pipeline-overview.png>)


## Monitoring

**Monitoring with Prometheus and Grafana**

This setup guide provides the steps to deploy Prometheus and Grafana for monitoring CPU and node metrics on Google Kubernetes Engine (GKE). Follow the steps in sequence to ensure correct deployment within the monitoring namespace using Helm charts.

#### Create Monitoring Namespace

![image alt text](<images/monitoring-name-space.png>)

```
kubectl create ns monitoring
```
#### Edit host

![image alt text](<images/etc-host.png>)

```
sudo nano /etc/hosts
```
```
34.126.164.80 api.tsc.vn
34.126.164.80 grafana.tsc.vn
34.126.164.80 prometheus.tsc.vn
34.126.164.80 jaeger.tsc.vn
```

#### Prometheus

Deploy Prometheus Operator CRDs 

![image alt text](<images/prometheus-operator-crds.png>)

```
helm upgrade --install prometheus-crds ./helm-charts/prometheus-operator-crds -n monitoring
```

Deploy Prometheus  
![image alt text](<images/prometheus.png>)

```
helm upgrade --install prometheus ./helm-charts/prometheus -n monitoring
```

Prometheus Service can be accessed via `http://prometheus.tsc.vn`

![image alt text](<images/prometheus-web.png>)

#### Grafana

![image alt text](<images/grafana.png>)

```
helm upgrade --install grafana ./helm-charts/grafana -n monitoring
```

Grafana Service can be accessed via `http://grafana.tsc.vn`
with user admin and password is admin

![image alt text](<images/grafana-web.png>)

#### Jaeger

Install Jaeger

![image alt text](<images/jaeger-tracing-helm.png>)
```
kubectl create ns logging
cd ./helm-charts/jaeger
helm dependency build
cd ../..
helm upgrade --install jaeger-tracing ./helm-charts/jaeger-all-in-one -n logging
```

Jaeger query can be accessed via `http://jaeger.tsc.vn`

![image alt text](<images/jaeger-query-web.png>)









