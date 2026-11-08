"""One copy of study A's speed benchmark (ngrow/bench.py), written to OUT_JSON; several copies run at once in
ngb/phase2.py so that the factor is measured under the stage's concurrency.

    python -I run.py bench_probe OUT_JSON
"""
import sys

from ngb import env as E
from ngrow import bench as BN


def main(out_path):
    E.dump(out_path, BN.run())


if __name__ == "__main__":
    main(*sys.argv[1:])
