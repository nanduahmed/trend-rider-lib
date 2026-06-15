"""Test script to verify app imports correctly."""
import app.app
print('app imported successfully')

# Test if ResultsTab is available
from app.views.results_tab import ResultsTab
print('ResultsTab imported successfully')