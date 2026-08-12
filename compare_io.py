# compare_io.py
import json, numpy as np, matplotlib.pyplot as plt, sys

def imshow(A, title, fname):
    plt.figure()
    plt.imshow(np.array(A, int), interpolation='nearest')
    plt.title(title)
    plt.axis('off')
    plt.savefig(fname, dpi=300, bbox_inches='tight')
    plt.show()

if __name__=="__main__":
    task_json, pred_json, stem = sys.argv[1], sys.argv[2], sys.argv[3]
    task = json.load(open(task_json))
    pred = json.load(open(pred_json))[stem]

    imshow(task["test"][0]["input"],
           f"{stem} test input",
           f"{stem}_test_input.png")

    imshow(pred["test"][0]["output"],
           f"{stem} output (guess)",
           f"{stem}_output.png")


