"""
StockPilot 실행 파일
사용법: python run.py
"""
from app import app

if __name__ == "__main__":
    print("\n" + "="*50)
    print("  StockPilot 퀀트 어드바이저 시작")
    print("  http://localhost:5050")
    print("  AI API 비용: $0 (완전 알고리즘 기반)")
    print("="*50 + "\n")
    app.run(debug=False, port=5050, host="0.0.0.0", use_reloader=False)
