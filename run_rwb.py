#!/usr/bin/env python3
"""
Run script for the RWB application with proper macOS integration.
"""

import os
import sys
from localknowledge.ui.rwb_main import main

if __name__ == "__main__":
    # Set the Info.plist path for macOS
    if sys.platform == 'darwin':
        os.environ['PYOBJC_BUNDLE_INFO'] = os.path.abspath('Info.plist')
    
    # Run the main application
    main()
