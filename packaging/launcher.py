"""Entry point of BoiDryTwin.exe (see packaging/BoiDryTwin.spec)."""

import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()  # must run first: the worker is a child of the exe
    from boidrytwin.webapp.desktop import main

    sys.exit(main())
