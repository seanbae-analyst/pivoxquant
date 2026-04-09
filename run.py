"""
StockPilot 실행 파일
사용법: python run.py
"""
import os
from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print("\n" + "="*50)
    print("  StockPilot Quant Advisor")
    print(f"  http://localhost:{port}")
    print("="*50 + "\n")
    app.run(debug=False, port=port, host="0.0.0.0", use_reloader=False)
