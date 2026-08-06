#!/usr/bin/env python
from aegis_aml.cli import main

if __name__ == "__main__":
    import sys

    sys.argv.insert(1, "graph-report")
    main()
