pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        IMAGE_NAME = 'student-task-manager:local'
        K8S_NAMESPACE = 'devops-demo'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                sh '''
                    python3 -m venv .venv
                    .venv/bin/pip install --upgrade pip
                    .venv/bin/pip install -r requirements.txt
                '''
            }
        }

        stage('Unit Tests') {
            steps {
                sh '''
                    .venv/bin/python -m unittest discover -s tests -v
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                sh '''
                    docker build -t "$IMAGE_NAME" .
                '''
            }
        }

        stage('Load Image into Minikube') {
            steps {
                sh '''
                    minikube image load "$IMAGE_NAME"
                '''
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                sh '''
                    kubectl apply -f k8s/namespace.yaml
                    kubectl apply -f k8s/app.yaml
                    kubectl rollout status deployment/student-task-manager \
                        -n "$K8S_NAMESPACE" --timeout=120s
                '''
            }
        }

        stage('Verify Deployment') {
            steps {
                sh '''
                    kubectl get deployment,service -n "$K8S_NAMESPACE"
                    kubectl get pods -n "$K8S_NAMESPACE"
                '''
            }
        }
    }

    post {
        success {
            echo 'SUCCESS: Tests, Docker build and Kubernetes deployment completed.'
        }
        failure {
            echo 'FAILED: Inspect the stage logs to identify the problem.'
        }
    }
}
