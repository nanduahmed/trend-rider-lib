
import importlib.util, traceback, sys

spec = importlib.util.spec_from_file_location('detail_window', 'app/views/detail_window.py')
module = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(module)
    print('Import succeeded')
except Exception:
    traceback.print_exc()
    sys.exit(1)
