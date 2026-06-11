"""
PivoxQuant 실행 파일
사용법: python run.py
"""
import os
import sys

# WeasyPrint native libs (macOS dev only): brew dylibs are off the default
# dlopen path, so local PDF rendering (artifact downloads) raised OSError on
# libgobject. cffi's find_library reads this env at call time — set it before
# any weasyprint import. Prod (Railway/Linux) resolves via ldconfig — no-op.
if sys.platform == "darwin" and "DYLD_FALLBACK_LIBRARY_PATH" not in os.environ:
    for _brew_lib in ("/opt/homebrew/lib", "/usr/local/lib"):
        if os.path.isdir(_brew_lib):
            os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = _brew_lib
            break

from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print("\n" + "="*50)
    print("  PivoxQuant Quant Research Tool")
    print(f"  http://localhost:{port}")
    print("="*50 + "\n")
    app.run(debug=False, port=port, host="0.0.0.0", use_reloader=False)
