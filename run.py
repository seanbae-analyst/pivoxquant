"""
StockPilot 실행 파일
사용법: python run.py
"""
import os
from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print("\n" + "="*50)
    print("  StockPilot 퀀트 어드바이저 시작")
    print(f"  http://localhost:{port}")
    print("  AI API 비용: $0 (완전 알고리즘 기반)")
    print("="*50 + "\n")
    app.run(debug=False, port=port, host="0.0.0.0", use_reloader=False)
