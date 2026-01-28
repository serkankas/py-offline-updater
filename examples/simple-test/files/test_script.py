#!/usr/bin/env python3
"""
Test script - file_copy ve command action'larını test eder.
Bu dosya /tmp/update_test/ altına kopyalanır ve çalıştırılır.
"""

import os
from datetime import datetime
from pathlib import Path

# Çıktı dizinini oluştur
output_dir = Path("/tmp/update_test")
output_dir.mkdir(parents=True, exist_ok=True)

# Test çıktısı yaz
output_file = output_dir / "test_output.txt"
with open(output_file, "w") as f:
    f.write("=" * 50 + "\n")
    f.write("UPDATE ENGINE TEST RESULTS\n")
    f.write("=" * 50 + "\n")
    f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"Calisma dizini: {os.getcwd()}\n")
    f.write(f"Script konumu: {__file__}\n")
    f.write("\n")
    f.write("[OK] file_copy: Python dosyasi basariyla kopyalandi\n")
    f.write("[OK] command: Python scripti basariyla calistirildi\n")
    f.write("=" * 50 + "\n")

print("Test script executed successfully!")
print(f"Output written to: {output_file}")
