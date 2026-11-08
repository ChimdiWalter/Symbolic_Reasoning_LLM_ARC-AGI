"""Kernel entry for generation (revision 2, development and source only): the packaged ARC training challenges file
replaces the Athe path in the harness allowlist, then fgc.generate runs one command.

    python -m fgc.kaggle_gen_main source_world W1
"""
import os
import sys

from fgc import common as C
from harness import paths as HP                                              # noqa: E402

DATA = os.path.join(C.REPO, "data_arc", "arc-agi_training_challenges.json")
HP.TRAIN_CHALLENGES = DATA
HP.ALLOW_FILES.add(os.path.realpath(DATA))

if __name__ == "__main__":
    from fgc import generate as G
    k = C.WORLDS.index(sys.argv[2])
    if sys.argv[1] == "source_world":
        G.save_rows(os.path.join(C.STUDY, "runs", "source", "parts", f"view_{sys.argv[2]}.json"),
                    G.source_view_rows(sys.argv[2], (k, len(C.WORLDS))))
    elif sys.argv[1] == "test_world":                  # after the GO: the salt comes from the local claim's GO
        G.save_rows(os.path.join(C.STUDY, "runs", "test_parts", f"test_{sys.argv[2]}.json"),
                    G.test_world_rows(sys.argv[2], sys.argv[3], (k, len(C.WORLDS))))
    print({"filtered": G.FILTERED}, flush=True)
