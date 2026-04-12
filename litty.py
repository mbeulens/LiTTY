#!/usr/bin/env python3

import sys
from litty.app import LittyApplication


def main():
    app = LittyApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
