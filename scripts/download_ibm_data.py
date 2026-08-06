#!/usr/bin/env python
"""Download the IBM AML dataset through the Kaggle CLI.

Requires Kaggle credentials. This script deliberately does not redistribute the dataset.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/raw/ibm")
    args = parser.parse_args()
    destination = Path(args.output)
    destination.mkdir(parents=True, exist_ok=True)
    command = [
        "kaggle",
        "datasets",
        "download",
        "-d",
        "ealtman2019/ibm-transactions-for-anti-money-laundering-aml",
        "--unzip",
        "-p",
        str(destination),
    ]
    subprocess.run(command, check=True)
    transaction_files = sorted(destination.rglob("*Trans*.csv"))
    print("Downloaded. Candidate transaction files:")
    for path in transaction_files:
        print(f"  {path}")


if __name__ == "__main__":
    main()
