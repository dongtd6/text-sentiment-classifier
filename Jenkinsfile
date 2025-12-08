pipeline {
  agent any

  environment {
    GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-artifact-key')
    GOOGLE_CLOUD_PROJECT       = credentials('gcp-project-id')
    GCR_REPO                   = "asia-southeast1-docker.pkg.dev/${GOOGLE_CLOUD_PROJECT}/bnb-c2c-images"
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
            credentialsId: 'github-key'  // nếu repo private, dùng credentials
      }
    }

    // ========== Batch-processing ==========
    stage('Batch: Build & Deploy') {
      when {
        changeset "dockerfiles/batch-processing/**"
      }
      stages {
        stage('Build Batch Docker Image') {
          steps {
            dir('dockerfiles/batch-processing') {
              sh 'docker build -t batch-app:latest .'
            }
          }
        }
        stage('Authenticate with GCP & Configure Docker') {
          steps {
            withCredentials([file(credentialsId: 'gcp-artifact-key', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
              // Note: using single-quoted or slashy string to avoid interpolation issues
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
        stage('Cleanup old Batch Container & Run New') {
          steps {
            // Use dollar-slashy so that $ and $(...) are passed literally to shell
            sh $/
              # Remove old container if exists (running or exited)
              if [ "$(docker ps -a -q -f name=batch-app)" ]; then
                docker rm -f batch-app || true
              fi
              # Run new container
              docker run -d --name batch-app -p 5000:80 ${GCR_REPO}/batch-app:latest
            /$
          }
        }
      }
    }

    // ========== Streaming-processing ==========
    stage('Streaming: Build & Deploy') {
      when {
        changeset "dockerfiles/streaming-processing/**"
      }
      stages {
        stage('Build Streaming Docker Image') {
          steps {
            dir('dockerfiles/streaming-processing') {
              sh 'docker build -t stream-app:latest .'
            }
          }
        }
        stage('Authenticate with GCP & Configure Docker') {
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
        stage('Tag & Push Streaming Image') {
          steps {
            sh '''
              docker tag stream-app:latest ${GCR_REPO}/stream-app:latest
              docker push ${GCR_REPO}/stream-app:latest
            '''
          }
        }
        stage('Cleanup old Streaming Container & Run New') {
          steps {
            sh $/
              if [ "$(docker ps -a -q -f name=stream-app)" ]; then
                docker rm -f stream-app || true
              fi
              docker run -d --name stream-app -p 5001:80 ${GCR_REPO}/stream-app:latest
            /$
          }
        }
      }
    }

    // Nếu không có thay đổi nào trong dockerfiles/ → skip build/push/deploy
    stage('No Docker Changes Detected') {
      when {
        allOf {
          not { changeset "dockerfiles/batch-processing/**" }
          not { changeset "dockerfiles/streaming-processing/**" }
        }
      }
      steps {
        echo 'No changes in dockerfiles — skip Docker build/push/deploy.'
      }
    }
  }

  post {
    always {
      echo "Pipeline finished for commit ${env.GIT_COMMIT}"
    }
    success {
      echo "Build & deploy succeeded."
    }
    failure {
      echo "Build or deploy failed!"
    }
  }
}
