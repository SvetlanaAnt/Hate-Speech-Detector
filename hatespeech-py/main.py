import multiprocessing as mp
import os
import warnings

from src.main import main

# Silence noisy warnings from dependencies in CLI usage.
warnings.filterwarnings("ignore", category=FutureWarning)
# Reduce extra advisory logs from the Hugging Face hub.
os.environ["HF_HUB_DISABLE_ADVISORY_WARNINGS"] = "1"


if __name__ == "__main__":
    # Required for PyInstaller multiprocessing support on Windows.
    mp.freeze_support()
    main()
