#!/usr/bin/env python3
"""
Debug script để kiểm tra dependencies và system libraries
Debug script to check dependencies and system libraries
"""

import sys
import os
import subprocess
import importlib


def print_section(title):
    print(f"\n{'='*50}")
    print(f"🔍 {title}")
    print(f"{'='*50}")


def check_system_info():
    """Kiểm tra thông tin hệ thống"""
    print_section("SYSTEM INFORMATION")

    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"Platform: {sys.platform}")

    try:
        import platform

        print(f"OS: {platform.system()} {platform.release()}")
        print(f"Architecture: {platform.machine()}")
    except:
        pass


def check_libcrypt():
    """Kiểm tra thư viện libcrypt"""
    print_section("LIBCRYPT CHECK")

    # Find libcrypt files
    try:
        result = subprocess.run(
            ["find", "/usr/lib", "/lib", "-name", "libcrypt*", "-type", "f"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.stdout:
            print("Found libcrypt files:")
            for line in result.stdout.strip().split("\n"):
                if line:
                    print(f"  📁 {line}")
        else:
            print("❌ No libcrypt files found!")
    except Exception as e:
        print(f"⚠️ Could not check libcrypt files: {e}")

    # Check ldconfig
    try:
        result = subprocess.run(
            ["ldconfig", "-p"], capture_output=True, text=True, timeout=10
        )
        libcrypt_lines = [
            line for line in result.stdout.split("\n") if "libcrypt" in line
        ]
        if libcrypt_lines:
            print("\nldconfig shows:")
            for line in libcrypt_lines:
                print(f"  📋 {line.strip()}")
        else:
            print("\n❌ ldconfig doesn't show libcrypt!")
    except Exception as e:
        print(f"⚠️ Could not run ldconfig: {e}")


def check_python_imports():
    """Kiểm tra các imports quan trọng"""
    print_section("PYTHON IMPORTS CHECK")

    critical_packages = [
        "fastapi",
        "uvicorn",
        "qdrant_client",
        "openai",
        "sentence_transformers",
        "redis",
        "pymongo",
        "aiofiles",
    ]

    for package in critical_packages:
        try:
            module = importlib.import_module(package)
            version = getattr(module, "__version__", "Unknown")
            print(f"✅ {package}: {version}")
        except ImportError as e:
            print(f"❌ {package}: Import failed - {e}")
        except Exception as e:
            print(f"⚠️ {package}: Error - {e}")


def check_pymupdf():
    """
    ⚠️ DEPRECATED: PyMuPDF checking removed - now using Gemini AI for PDF extraction
    """
    print_section("PYMUPDF DETAILED CHECK")
    print("❌ PyMuPDF has been removed from this project")
    print("✅ PDF extraction now uses Gemini AI instead")
    print("ℹ️ This check is deprecated and will be removed")
    
    # OLD CODE - REMOVED PyMuPDF checking:
    # try:
    #     import fitz
    #     print(f"✅ PyMuPDF imported successfully")
    #     print(f"� Version: {fitz.version[0]}")
    #     ... [PyMuPDF checking code removed] ...
    # except ImportError as e:
    #     print(f"❌ PyMuPDF import failed: {e}")
    #     ... [Error handling code removed] ...


def check_environment():
    """Kiểm tra environment variables"""
    print_section("ENVIRONMENT VARIABLES")

    important_vars = [
        "PYTHONPATH",
        "LD_LIBRARY_PATH",
        "ENV",
        "DEEPSEEK_API_KEY",
        "CHATGPT_API_KEY",
        "QDRANT_URL",
    ]

    for var in important_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if "KEY" in var or "TOKEN" in var:
                masked_value = value[:8] + "***" if len(value) > 8 else "***"
                print(f"🔑 {var}: {masked_value}")
            else:
                print(f"📋 {var}: {value}")
        else:
            print(f"⚪ {var}: Not set")


def main():
    print("🚀 AI Chatbot Dependencies Debug Script")
    print("=====================================")

    check_system_info()
    check_environment()
    check_libcrypt()
    check_python_imports()
    check_pymupdf()

    print_section("DEBUG COMPLETED")
    print("🎉 Debug script finished!")
    print("\nIf PyMuPDF failed to import, check the libcrypt section above.")
    print("You may need to install additional system packages.")


if __name__ == "__main__":
    main()
