# view_arc_grid.py
import json, numpy as np, matplotlib.pyplot as plt, sys

def show_grid(A, title=""):
    A = np.array(A, dtype=int)
    plt.figure()
    plt.imshow(A, interpolation='nearest')  # no explicit colors; default is fine
    plt.title(title)
    plt.axis('off')
    plt.show()

if __name__=="__main__":
    path = sys.argv[1]            # e.g., data/curveball/example01.json
    which = sys.argv[2]           # "train0_input" | "train0_output" | "test0_input"
    spec = json.load(open(path))
    if which=="train0_input":  show_grid(spec["train"][0]["input"], "train[0].input")
    if which=="train0_output": show_grid(spec["train"][0]["output"], "train[0].output")
    if which=="test0_input":   show_grid(spec["test"][0]["input"],  "test[0].input")

