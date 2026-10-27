import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from db.init_db import create_and_seed_database

    if __name__ == "__main__":
        create_and_seed_database()
except Exception as e:
    print(f"Warning: Sample db initialization during build step encountered: {e}")
