pipeline {
  agent any

  environment {
    GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-artifact-key')
    GOOGLE_CLOUD_PROJECT           = credentials('gcp-project-id')
    GCR_REPO                       = "asia-southeast1-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/bnb-c2c-images"
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
            url: 'https://github.com/abcdefya/Sentiment-Classifier-ML-System-on-K8S.git',
            credentialsId: 'github-key'
      }
    }

    /* =====================================================
     * Batch Processing
     * ===================================================== */
    stage('Batch: Build & Deploy') {
      when {
        changeset "dockerfiles/batch-processing/**"
      }
      stages {

        stage('Build Batch Docker Image') {
          steps {
            sh 'docker build -f dockerfiles/batch-processing/Dockerfile -t batch-app:latest .'
          }
        }

        stage('Auth GCP & Docker (Batch)') {
          steps {
            withCredentials([file(credentialsId: 'gcp-artifact-key', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
              sh '''
                gcloud auth activate-service-account --key-file="$GOOGLE_APPLICATION_CREDENTIALS"
                gcloud config set project "$GOOGLE_CLOUD_PROJECT"
                gcloud auth configure-docker asia-southeast1-docker.pkg.dev
              '''
            }
          }
        }

        stage('Tag & Push Batch Image') {
          steps {
            sh '''
              docker tag batch-app:latest ${GCR_REPO}/batch-app:latest
              docker push ${GCR_REPO}/batch-app:latest
            '''
          }
        }
      }
    }

    /* =====================================================
     * Streaming Processing (TAG = GIT COMMIT)
     * ===================================================== */
    stage('Streaming: Build & Deploy') {
      when {
        changeset "dockerfiles/streaming-processing/**"
      }
      stages {

        stage('Build Streaming Docker Image') {
          steps {
            sh 'docker build -f dockerfiles/streaming-processing/Dockerfile -t stream-app:latest .'
          }
        }

        stage('Auth GCP & Docker (Streaming)') {
          steps {
            withCredentials([file(credentialsId: 'gcp-artifact-key', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
              sh '''
                gcloud auth activate-service-account --key-file="$GOOGLE_APPLICATION_CREDENTIALS"
                gcloud config set project "$GOOGLE_CLOUD_PROJECT"
                gcloud auth configure-docker asia-southeast1-docker.pkg.dev
              '''
            }
          }
        }

        stage('Tag & Push Streaming Image (git commit)') {
          steps {
            sh '''
              SHORT_COMMIT=$(echo "$GIT_COMMIT" | cut -c1-7)
              IMAGE_TAG=git-${SHORT_COMMIT}

              echo "🔖 Streaming image tag: ${IMAGE_TAG}"

              docker tag stream-app:latest ${GCR_REPO}/stream-app:${IMAGE_TAG}
              docker push ${GCR_REPO}/stream-app:${IMAGE_TAG}
            '''
          }
        }
      }
    }

    /* =====================================================
     * Ingestion Processing
     * ===================================================== */
    stage('Ingestion: Build & Deploy') {
      when {
        changeset "dockerfiles/ingestion/**"
      }
      stages {

        stage('Build Ingestion Docker Image') {
          steps {
            sh 'docker build -f dockerfiles/ingestion/Dockerfile -t ingestion-app:latest .'
          }
        }

        stage('Auth GCP & Docker (Ingestion)') {
          steps {
            withCredentials([file(credentialsId: 'gcp-artifact-key', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
              sh '''
                gcloud auth activate-service-account --key-file="$GOOGLE_APPLICATION_CREDENTIALS"
                gcloud config set project "$GOOGLE_CLOUD_PROJECT"
                gcloud auth configure-docker asia-southeast1-docker.pkg.dev
              '''
            }
          }
        }

        stage('Tag & Push Ingestion Image') {
          steps {
            sh '''
              docker tag ingestion-app:latest ${GCR_REPO}/ingestion-app:latest
              docker push ${GCR_REPO}/ingestion-app:latest
            '''
          }
        }
      }
    }

    /* =====================================================
     * No Docker Changes
     * ===================================================== */
    stage('No Docker Changes Detected') {
      when {
        allOf {
          not { changeset "dockerfiles/batch-processing/**" }
          not { changeset "dockerfiles/streaming-processing/**" }
          not { changeset "dockerfiles/ingestion/**" }
        }
      }
      steps {
        echo 'No changes in dockerfiles — skip Docker build/push.'
      }
    }
  }

  post {
    always {
      echo "Pipeline finished for commit ${env.GIT_COMMIT}"
    }
    success {
      echo "Build & push to Artifact Registry succeeded."
    }
    failure {
      echo "Build or push failed!"
    }
  }
}
