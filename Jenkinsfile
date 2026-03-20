pipeline {
    agent any

    options {
        timestamps()
        ansiColor('xterm')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '15'))
    }

    environment {
        COMPOSE_FILE = 'docker-compose.yml'
        COMPOSE_PROJECT_NAME = "mlopsia-${BUILD_NUMBER}"
        HEALTH_URL = 'http://localhost:5000/health'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Python Setup') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            set -e
                            python3 --version
                            python3 -m pip install --upgrade pip
                            python3 -m pip install -r requirements.txt
                        '''
                    } else {
                        bat '''
                            python --version
                            python -m pip install --upgrade pip
                            python -m pip install -r requirements.txt
                        '''
                    }
                }
            }
        }

        stage('Quick Validation') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            set -e
                            python3 -m compileall api backend database model
                        '''
                    } else {
                        bat '''
                            python -m compileall api backend database model
                        '''
                    }
                }
            }
        }

        stage('Build Images') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'docker compose -f ${COMPOSE_FILE} build --no-cache'
                    } else {
                        bat 'docker compose -f %COMPOSE_FILE% build --no-cache'
                    }
                }
            }
        }

        stage('Start Stack') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'docker compose -f ${COMPOSE_FILE} up -d db model backend frontend'
                    } else {
                        bat 'docker compose -f %COMPOSE_FILE% up -d db model backend frontend'
                    }
                }
            }
        }

        stage('Health Check') {
            steps {
                script {
                    if (isUnix()) {
                        sh '''
                            set -e
                            python3 - <<'PY'
import time
import urllib.request

url = 'http://localhost:5000/health'
max_attempts = 30
wait_seconds = 5

for attempt in range(1, max_attempts + 1):
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            body = response.read().decode('utf-8', errors='ignore')
            if response.status == 200:
                print(f'Health check passed on attempt {attempt}: {body}')
                raise SystemExit(0)
            print(f'Unexpected status {response.status} on attempt {attempt}')
    except Exception as exc:
        print(f'Attempt {attempt}/{max_attempts} failed: {exc}')
    time.sleep(wait_seconds)

raise SystemExit('Health check failed after retries')
PY
                        '''
                    } else {
                        bat '''
                            python -c "import time, urllib.request; url='http://localhost:5000/health'; ok=False\nfor i in range(30):\n    try:\n        r=urllib.request.urlopen(url, timeout=5); body=r.read().decode('utf-8', errors='ignore');\n        if r.status==200:\n            print('Health check passed on attempt %d: %s' % (i+1, body)); ok=True; break\n        print('Unexpected status %s on attempt %d' % (r.status, i+1))\n    except Exception as e:\n        print('Attempt %d/30 failed: %s' % (i+1, e))\n    time.sleep(5)\nimport sys; sys.exit(0 if ok else 1)"
                        '''
                    }
                }
            }
        }
    }

    post {
        always {
            script {
                if (isUnix()) {
                    sh 'docker compose -f ${COMPOSE_FILE} logs --no-color backend || true'
                    sh 'docker compose -f ${COMPOSE_FILE} down -v --remove-orphans || true'
                } else {
                    bat 'docker compose -f %COMPOSE_FILE% logs backend'
                    bat 'docker compose -f %COMPOSE_FILE% down -v --remove-orphans'
                }
            }
        }
    }
}
