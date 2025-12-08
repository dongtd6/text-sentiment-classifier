pipeline {
  agent any

  environment {
    GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-artifact-key')
    GOOGLE_CLOUD_PROJECT = credentials('gcp-project-id')
    GCR_REPO = "asia-southeast1-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/bnb-c2c-images"
  }

  stages {
    stage('Clean Workspace') {
      steps {
        cleanWs()
      }
    }

    stage('Git Checkout') {
      steps {
        git branch: 'airflow',
            url: 'https://github.com/abcdefya/Sentiment-Classifier-ML-System-on-K8S.git'
      }
    }

    stage('Batch: Build & Deploy') {
      when {
        changeset "dockerfiles/batch-processing/**"
      }
      stages {
        stage('Build Batch Docker Image') {
          steps {
            dir('dockerfiles/batch-processing') {
              sh "docker build -t batch-app:latest ."
            }
          }
        }
        stage('Authenticate with GCP') {
          steps {
            withCredentials([file(credentialsId: 'gcp-artifact-key', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
              sh "gcloud auth activate-service-account --key-file=${GOOGLE_APPLICATION_CREDENTIALS}"
              sh "gcloud config set project ${GOOGLE_CLOUD_PROJECT}"
              sh "gcloud auth configure-docker asia-southeast1-docker.pkg.dev"
            }
          }
        }
        stage('Tag & Push Batch Image') {
          steps {
            sh """
              docker tag batch-app:latest ${GCR_REPO}/batch-app:latest
              docker push ${GCR_REPO}/batch-app:latest
            """
          }
        }
        stage('Deploy Batch Container') {
          steps {
            sh """
              if [ \$(docker ps -q -f name=batch-app) ]; then
                  docker stop batch-app || true
                  docker rm batch-app || true
              fi
              docker run -d --name batch-app -p 5000:80 ${GCR_REPO}/batch-app:latest
            """
          }
        }
      }
    }

    stage('Streaming: Build & Deploy') {
      when {
        changeset "dockerfiles/streaming-processing/**"
      }
      stages {
        stage('Build Streaming Docker Image') {
          steps {
            dir('dockerfiles/streaming-processing') {
              sh "docker build -t stream-app:latest ."
            }
          }
        }
        stage('Authenticate with GCP') {
          steps {
            withCredentials([file(credentialsId: 'gcp-artifact-key', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
              sh "gcloud auth activate-service-account --key-file=${GOOGLE_APPLICATION_CREDENTIALS}"
              sh "gcloud config set project ${GOOGLE_CLOUD_PROJECT}"
              sh "gcloud auth configure-docker asia-southeast1-docker.pkg.dev"
            }
          }
        }
        stage('Tag & Push Streaming Image') {
          steps {
            sh """
              docker tag stream-app:latest ${GCR_REPO}/stream-app:latest
              docker push ${GCR_REPO}/stream-app:latest
            """
          }
        }
        stage('Deploy Streaming Container') {
          steps {
            sh """
              if [ \$(docker ps -q -f name=stream-app) ]; then
                  docker stop stream-app || true
                  docker rm stream-app || true
              fi
              docker run -d --name stream-app -p 5001:80 ${GCR_REPO}/stream-app:latest
            """
          }
        }
      }
    }

    stage('No Docker Changes Detected') {
      when {
        allOf {
          not { changeset "dockerfiles/batch-processing/**" }
          not { changeset "dockerfiles/streaming-processing/**" }
        }
      }
      steps {
        echo "No changes in dockerfiles subfolders — skip Docker build/push/deploy."
      }
    }
  }
}
