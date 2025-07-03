#!/bin/bash

# Cài Docker
echo "👉 Cài đặt Docker..."
sudo apt-get update
sudo apt-get install -y docker.io
sudo apt install docker-compose 

# Cấp quyền chạy Docker không cần sudo
echo "👉 Cấp quyền Docker cho user hiện tại..."
sudo usermod -aG docker $USER

# Cài Jenkins bằng Docker
echo "👉 Cài đặt Jenkins container..."
sudo docker-compose -f docker-compose-jenkins.yml up

echo "✅ Tất cả hoàn tất. Nhớ logout/login để áp dụng group docker."
