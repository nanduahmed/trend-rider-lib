import importlib.util, traceback, sys
spec = importlib.util.spec_from_file_location('detail_window', 'app/views/detail_window.py')
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
    print('Import succeeded')
    # List public attributes
    attrs = [name for name in dir(mod) if not name.startswith('_')]
    print('Public attributes:', attrs)
except Exception:
    traceback.print_exc()
    sys.exit(1)
