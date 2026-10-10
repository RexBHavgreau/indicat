"""Entry point for the GUI (and for PyInstaller)."""
import sys

from scripture_index.gui import main

if __name__ == "__main__":
    sys.exit(main())
