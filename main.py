
import sys
from pathlib import Path

# Fix module path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

if __name__ == "__main__":
    try:
        from src.pipeline import main
        main()
    except ImportError as e:
        print(f"Error starting application: {e}")
        print("Please ensure the 'src' directory exists and contains 'pipeline.py'.")
        sys.exit(1)
