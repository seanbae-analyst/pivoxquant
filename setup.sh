#!/bin/bash
# PivoxQuant 설치 스크립트

echo "=============================="
echo "  PivoxQuant 환경 설치 중..."
echo "=============================="

# 가상환경 생성
python3 -m venv venv
source venv/bin/activate

# 패키지 설치
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "=============================="
echo "  설치 완료!"
echo "  실행: source venv/bin/activate && python run.py"
echo "  접속: http://localhost:5050"
echo "=============================="
