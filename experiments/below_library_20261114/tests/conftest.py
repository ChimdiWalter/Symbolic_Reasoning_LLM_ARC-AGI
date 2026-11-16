"""Test configuration of the below-library experiment: the experiment folder first on the path, a fixed hash seed.
Author: Chimdi Walter Ndubuisi
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("PYTHONHASHSEED", "0")
