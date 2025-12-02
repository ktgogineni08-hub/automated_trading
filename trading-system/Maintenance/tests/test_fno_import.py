import sys
import os
sys.path.append(os.getcwd())
print("Starting import test...")
try:
    from fno.terminal import FNOTerminal
    print("Import successful!")
except Exception as e:
    print(f"Import failed: {e}")
except SystemExit:
    print("SystemExit caught during import")
