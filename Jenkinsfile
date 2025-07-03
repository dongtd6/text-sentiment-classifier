pipeline {
    agent any

    options{
        // Max number of build logs to keep and days to keep
        buildDiscarder(logRotator(numToKeepStr: '5', daysToKeepStr: '5'))
        // Enable timestamp at each job in the pipeline
        timestamps()
    }

    environment{
        registry = 'dongtd6/text-sentiment-classifier' //Image id push to Docker Hub
        registryCredential = 'dockerhub'    //Credential on Jenkins to login Docker Hub  
    }

    stages {
        stage('Test') { //Use test_model_correctness.py
            agent {
                docker {
                    image 'python:3.8' // Use a Docker image with Python 3.8
                }
            }
            steps {
                echo 'Testing model correctness..'
                sh 'pip install -r requirements.txt && pytest'
            }
        }
        stage('Build') {
            steps {
                script {
                    echo 'Building image for deployment..'
                    dockerImage = docker.build registry + ":$BUILD_NUMBER" //Build images from Dockerfile
                    echo 'Pushing image to dockerhub..'
                    docker.withRegistry( '', registryCredential ) {  //Push to Docker Hub
                        dockerImage.push()
                        dockerImage.push('latest')
                    }
                }
            }
        }
        stage('Deploy') {
            agent {
                kubernetes {
                    containerTemplate {
                        name 'helm-container' // Name of the container to be used for helm upgrade
                        image 'quandvrobusto/jenkins:lts-jdk17' //  alpine/helm:3.14.0 The image containing helm
                        imagePullPolicy 'Always' // Always pull image in case of using the same tag
                    }
                }
            }
            steps {
                script {
                    echo 'Deploying models..'
                    container('helm-container') {
                        sh("helm upgrade --install tsc ./helm-charts/model-deployment/ --namespace model-serving")
                    }
                }
            }
        }
    }
}