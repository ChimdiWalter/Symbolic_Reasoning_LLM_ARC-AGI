"""Command line for the Step-B freeze pin. The logic lives in cora_tti/freeze_pin.py.

    python3 scripts/pin_stepB_freeze.py            create the pin, exactly once
    python3 scripts/pin_stepB_freeze.py --bind     after committing the pin: write the binding
    python3 scripts/pin_stepB_freeze.py --verify   verify the pin; fails closed
    python3 scripts/pin_stepB_freeze.py --verify --require-binding
                                                   also require the committed binding and anchor
    python3 scripts/pin_stepB_freeze.py --verify-modules   verify the committed G2 module pin
    python3 scripts/pin_stepB_freeze.py --dry-run  synthetic fixture trees only

Creating the pin requires the freeze marker, the final output hash file and no
live runner. Verification fails on a missing, changed or newly appeared file
inside any pinned scope, and on any change to the pin itself.

Artifact bytes are read transiently only for sha256 hashing and newline
counting. They are never parsed, deserialized, interpreted, retained, printed,
returned, or written into the pin.

The first line of output is always `OUTCOME <name>` and each outcome has a fixed
exit code, so no wrapper ever has to parse prose. A malformed command line is
reported as `OUTCOME CLI_USAGE_ERROR` with its own exit code, never as a bare
argparse message. `--allow-unfrozen` is a retired
alias of `--dry-run` and is refused on the live tree in the same way.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cora_tti import freeze_pin as FP   # noqa: E402


class UsageError(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def main(argv=None) -> int:
    parser = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify", action="store_true", help="verify the existing pin")
    mode.add_argument("--bind", action="store_true",
                      help="after the pin is committed, record its commit in a tracked binding file")
    mode.add_argument("--verify-modules", action="store_true",
                      help="verify the committed G2 module pin")
    mode.add_argument("--dry-run", action="store_true",
                      help="fixture trees only; refused on the live experiment tree")
    mode.add_argument("--allow-unfrozen", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--require-binding", action="store_true",
                        help="with --verify, or alone: also require the committed binding and anchor")
    try:
        args = parser.parse_args(argv)
        if args.require_binding and (args.bind or args.verify_modules or args.dry_run
                                     or args.allow_unfrozen):
            raise UsageError("--require-binding applies only to pin verification")
    except UsageError as error:
        result = {"outcome": FP.CLI_USAGE_ERROR, "error": str(error)}
        print(f"OUTCOME {result['outcome']}")
        print(json.dumps(result, indent=1, sort_keys=True))
        return FP.EXIT_CODES[FP.CLI_USAGE_ERROR]

    if args.verify or args.require_binding:
        result = FP.verify_pin(require_binding=args.require_binding).to_json()
    elif args.verify_modules:
        result = FP.verify_module_pin().to_json()
    elif args.bind:
        result = FP.bind_pin()
    elif args.dry_run or args.allow_unfrozen:
        result = FP.dry_run()
    else:
        result = FP.create_pin()

    outcome = result["outcome"]
    print(f"OUTCOME {outcome}")
    print(json.dumps(result, indent=1, sort_keys=True, default=str))
    return FP.EXIT_CODES[outcome]


if __name__ == "__main__":
    raise SystemExit(main())
