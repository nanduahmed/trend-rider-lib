"""
Pytest configuration for Trend Rider tests.
"""
import sys
from pathlib import Path

# Add parent directory to path so we can import trend_rider_lib
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
