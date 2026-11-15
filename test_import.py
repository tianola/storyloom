#!/usr/bin/env python3
import sys
print('Python executable:', sys.executable)
import sys
sys.path.insert(0, 'tools')
try:
    from narrate import synthesize, build_manifest
    print('Import successful')
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()