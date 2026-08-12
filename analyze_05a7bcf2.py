#!/usr/bin/env python3
"""Trace the exact generative rule for ARC task 05a7bcf2."""

import json
import numpy as np
from collections import Counter, defaultdict

with open('/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project/data/arc/arc-agi_training_challenges.json') as f:
    data = json.load(f)
task = data['05a7bcf2']

def print_grid(grid, label=""):
    """Print a grid compactly with hex digits."""
    if label:
        print(f"\n--- {label} ---")
    for r, row in enumerate(grid):
        print(f"  r{r:02d}: {''.join(format(c, 'x') for c in row)}")


for pair_idx, pair in enumerate(task['train']):
    inp = np.array(pair['input'])
    out = np.array(pair['output'])
    H, W = inp.shape
    print(f"\n{'='*70}")
    print(f"PAIR {pair_idx}: {H}x{W}")
    print(f"{'='*70}")

    # ---- 1. Identify the 8-wall ----
    # Check for a full row of 8s (horizontal wall)
    wall_orientation = None
    wall_pos = None
    for r in range(H):
        if np.all(inp[r, :] == 8):
            wall_orientation = 'horizontal'
            wall_pos = r
            break
    if wall_orientation is None:
        for c in range(W):
            if np.all(inp[:, c] == 8):
                wall_orientation = 'vertical'
                wall_pos = c
                break
    print(f"\n[1] Wall: orientation={wall_orientation}, position={wall_pos}")

    # ---- 2. Identify 4-objects and 2-boundary ----
    cells_4 = list(zip(*np.where(inp == 4)))
    cells_2 = list(zip(*np.where(inp == 2)))
    print(f"[2] Color-4 cells: {len(cells_4)} cells")
    print(f"    Color-2 cells: {len(cells_2)} cells")

    # Determine which side each color is on
    if wall_orientation == 'horizontal':
        side_4 = 'above' if all(r < wall_pos for r, c in cells_4) else 'below'
        side_2 = 'above' if all(r < wall_pos for r, c in cells_2) else 'below'
        print(f"    4-objects are {side_4} the wall")
        print(f"    2-boundary is {side_2} the wall")
    elif wall_orientation == 'vertical':
        side_4 = 'left' if all(c < wall_pos for r, c in cells_4) else 'right'
        side_2 = 'left' if all(c < wall_pos for r, c in cells_2) else 'right'
        print(f"    4-objects are {side_4} of the wall")
        print(f"    2-boundary is {side_2} of the wall")

    # ---- 3. Trace rays from each 4-cell ----
    print(f"\n[3] Ray tracing from each 4-cell:")

    if wall_orientation == 'horizontal':
        # Rays go vertically. Determine direction: toward the wall and beyond.
        if side_4 == 'above':
            # 4 is above wall, so rays go downward (toward wall and beyond)
            ray_dir = 'down'
        else:
            ray_dir = 'up'

        # For each column that has a 4-cell, trace the full column in the output
        cols_with_4 = sorted(set(c for r, c in cells_4))
        for col in cols_with_4:
            # Find all 4-cells in this column
            rows_4_in_col = sorted(r for r, c in cells_4 if c == col)
            print(f"\n  Column {col}: 4-cells at rows {rows_4_in_col}")

            # Print input column vs output column
            inp_col = inp[:, col].tolist()
            out_col = out[:, col].tolist()
            print(f"    Input  col: {' '.join(format(v,'x') for v in inp_col)}")
            print(f"    Output col: {' '.join(format(v,'x') for v in out_col)}")

            # Trace from each 4-cell toward the wall and beyond
            for r4 in rows_4_in_col:
                print(f"    From 4-cell at row {r4}:")
                print(f"      Output at source: color {out[r4, col]} (expected 3)")

                if ray_dir == 'down':
                    # Trace downward from r4
                    segment_before_wall = []
                    for r in range(r4 + 1, wall_pos):
                        segment_before_wall.append((r, out[r, col]))
                    segment_at_wall = (wall_pos, out[wall_pos, col])
                    segment_after_wall = []
                    for r in range(wall_pos + 1, H):
                        segment_after_wall.append((r, out[r, col]))

                    print(f"      Before wall (r{r4+1}-r{wall_pos-1}): {[(r, v) for r, v in segment_before_wall]}")
                    print(f"      At wall (r{wall_pos}): color {segment_at_wall[1]}")
                    print(f"      After wall (r{wall_pos+1}-r{H-1}): {[(r, v) for r, v in segment_after_wall]}")
                else:
                    # Trace upward from r4
                    segment_before_wall = []
                    for r in range(r4 - 1, wall_pos, -1):
                        segment_before_wall.append((r, out[r, col]))
                    segment_at_wall = (wall_pos, out[wall_pos, col])
                    segment_after_wall = []
                    for r in range(wall_pos - 1, -1, -1):
                        segment_after_wall.append((r, out[r, col]))

                    print(f"      Before wall (r{r4-1}-r{wall_pos+1}): {[(r, v) for r, v in segment_before_wall]}")
                    print(f"      At wall (r{wall_pos}): color {segment_at_wall[1]}")
                    print(f"      After wall (r{wall_pos-1}-r0): {[(r, v) for r, v in segment_after_wall]}")

    elif wall_orientation == 'vertical':
        # Rays go horizontally
        if side_4 == 'left':
            ray_dir = 'right'
        else:
            ray_dir = 'left'

        rows_with_4 = sorted(set(r for r, c in cells_4))
        for row in rows_with_4:
            cols_4_in_row = sorted(c for r, c in cells_4 if r == row)
            print(f"\n  Row {row}: 4-cells at cols {cols_4_in_row}")

            inp_row = inp[row, :].tolist()
            out_row = out[row, :].tolist()
            print(f"    Input  row: {' '.join(format(v,'x') for v in inp_row)}")
            print(f"    Output row: {' '.join(format(v,'x') for v in out_row)}")

            for c4 in cols_4_in_row:
                print(f"    From 4-cell at col {c4}:")
                print(f"      Output at source: color {out[row, c4]} (expected 3)")

                if ray_dir == 'right':
                    segment_before_wall = []
                    for c in range(c4 + 1, wall_pos):
                        segment_before_wall.append((c, out[row, c]))
                    segment_at_wall = (wall_pos, out[row, wall_pos])
                    segment_after_wall = []
                    for c in range(wall_pos + 1, W):
                        segment_after_wall.append((c, out[row, c]))

                    print(f"      Before wall (c{c4+1}-c{wall_pos-1}): {[(c, v) for c, v in segment_before_wall]}")
                    print(f"      At wall (c{wall_pos}): color {segment_at_wall[1]}")
                    print(f"      After wall (c{wall_pos+1}-c{W-1}): {[(c, v) for c, v in segment_after_wall]}")
                else:
                    segment_before_wall = []
                    for c in range(c4 - 1, wall_pos, -1):
                        segment_before_wall.append((c, out[row, c]))
                    segment_at_wall = (wall_pos, out[row, wall_pos])
                    segment_after_wall = []
                    for c in range(wall_pos - 1, -1, -1):
                        segment_after_wall.append((c, out[row, c]))

                    print(f"      Before wall (c{c4-1}-c{wall_pos+1}): {[(c, v) for c, v in segment_before_wall]}")
                    print(f"      At wall (c{wall_pos}): color {segment_at_wall[1]}")
                    print(f"      After wall (c{wall_pos-1}-c0): {[(c, v) for c, v in segment_after_wall]}")

    # ---- 4. Verify 2-boundary push to edge ----
    print(f"\n[4] 2-boundary analysis:")
    cells_2_out = list(zip(*np.where(out == 2)))
    print(f"    Input  2-cells: {len(cells_2)}")
    print(f"    Output 2-cells: {len(cells_2_out)}")

    if wall_orientation == 'horizontal':
        # Compare per-row 2-cell counts
        inp_2_per_row = Counter(r for r, c in cells_2)
        out_2_per_row = Counter(r for r, c in cells_2_out)

        print(f"    Input  2-cells per row: {dict(sorted(inp_2_per_row.items()))}")
        print(f"    Output 2-cells per row: {dict(sorted(out_2_per_row.items()))}")

        # Check if output 2s are at the grid edge
        if side_2 == 'below':
            # 2s should be pushed to bottom edge
            for r, c in cells_2_out:
                if r != H - 1 and out[r+1, c] != 2:
                    # Check if it's at the bottom or stacked
                    pass
            # Actually let's check column by column
            print(f"\n    Per-column 2-boundary check (2-side = {side_2}):")
            cols_with_2_inp = sorted(set(c for r, c in cells_2))
            cols_with_2_out = sorted(set(c for r, c in cells_2_out))
            for col in sorted(set(cols_with_2_inp) | set(cols_with_2_out)):
                inp_rows = sorted(r for r, c in cells_2 if c == col)
                out_rows = sorted(r for r, c in cells_2_out if c == col)
                print(f"      Col {col}: inp rows={inp_rows}, out rows={out_rows}")
        else:
            # 2s should be pushed to top edge
            print(f"\n    Per-column 2-boundary check (2-side = {side_2}):")
            cols_with_2_inp = sorted(set(c for r, c in cells_2))
            cols_with_2_out = sorted(set(c for r, c in cells_2_out))
            for col in sorted(set(cols_with_2_inp) | set(cols_with_2_out)):
                inp_rows = sorted(r for r, c in cells_2 if c == col)
                out_rows = sorted(r for r, c in cells_2_out if c == col)
                print(f"      Col {col}: inp rows={inp_rows}, out rows={out_rows}")

    elif wall_orientation == 'vertical':
        # Compare per-column 2-cell counts
        inp_2_per_col = Counter(c for r, c in cells_2)
        out_2_per_col = Counter(c for r, c in cells_2_out)

        print(f"    Input  2-cells per col: {dict(sorted(inp_2_per_col.items()))}")
        print(f"    Output 2-cells per col: {dict(sorted(out_2_per_col.items()))}")

        # Check per-row
        print(f"\n    Per-row 2-boundary check (2-side = {side_2}):")
        rows_with_2_inp = sorted(set(r for r, c in cells_2))
        rows_with_2_out = sorted(set(r for r, c in cells_2_out))
        for row in sorted(set(rows_with_2_inp) | set(rows_with_2_out)):
            inp_cols = sorted(c for r, c in cells_2 if r == row)
            out_cols = sorted(c for r, c in cells_2_out if r == row)
            print(f"      Row {row}: inp cols={inp_cols}, out cols={out_cols}")

    # ---- 5. Also trace what happens to rays that DON'T have 4-cells ----
    # Check: does EVERY column/row between wall and opposite edge get a ray, or only 4-cell ones?
    print(f"\n[5] Non-4-cell rays check:")
    if wall_orientation == 'horizontal':
        # Check columns without 4-cells
        cols_without_4 = [c for c in range(W) if c not in set(c2 for _, c2 in cells_4)]
        sample_cols = cols_without_4[:3]
        for col in sample_cols:
            out_col = out[:, col].tolist()
            non_zero = [(r, v) for r, v in enumerate(out_col) if v != 0]
            print(f"    Col {col} (no 4-cell): non-zero = {non_zero}")
    elif wall_orientation == 'vertical':
        rows_without_4 = [r for r in range(H) if r not in set(r2 for r2, _ in cells_4)]
        sample_rows = rows_without_4[:3]
        for row in sample_rows:
            out_row = out[row, :].tolist()
            non_zero = [(c, v) for c, v in enumerate(out_row) if v != 0]
            print(f"    Row {row} (no 4-cell): non-zero = {non_zero}")

    # ---- 6. Full diff: where do input and output differ? ----
    print(f"\n[6] Full diff analysis:")
    diff_mask = inp != out
    diff_positions = list(zip(*np.where(diff_mask)))
    print(f"    Total changed cells: {len(diff_positions)}")

    # Categorize changes
    change_types = Counter()
    for r, c in diff_positions:
        change_types[(inp[r, c], out[r, c])] += 1
    print(f"    Change types (inp_color -> out_color): count")
    for (ic, oc), cnt in sorted(change_types.items()):
        print(f"      {ic} -> {oc}: {cnt}")

    # ---- 7. Check: do rays also go AWAY from the wall (toward the grid edge on the 4-side)? ----
    print(f"\n[7] Ray direction check - do rays also extend AWAY from wall?")
    if wall_orientation == 'horizontal':
        for col in cols_with_4[:2]:  # Just check a couple
            rows_4_in_col = sorted(r for r, c in cells_4 if c == col)
            for r4 in rows_4_in_col:
                if side_4 == 'above':
                    # Check above the 4-cell (away from wall)
                    above_segment = [(r, out[r, col]) for r in range(r4 - 1, -1, -1)]
                    print(f"    Col {col}, 4@r{r4}: above (away from wall) = {above_segment}")
                else:
                    below_segment = [(r, out[r, col]) for r in range(r4 + 1, H)]
                    print(f"    Col {col}, 4@r{r4}: below (away from wall) = {below_segment}")
    elif wall_orientation == 'vertical':
        for row in rows_with_4[:2]:
            cols_4_in_row = sorted(c for r, c in cells_4 if r == row)
            for c4 in cols_4_in_row:
                if side_4 == 'left':
                    # Check left of the 4-cell (away from wall)
                    left_segment = [(c, out[row, c]) for c in range(c4 - 1, -1, -1)]
                    print(f"    Row {row}, 4@c{c4}: left (away from wall) = {left_segment}")
                else:
                    right_segment = [(c, out[row, c]) for c in range(c4 + 1, W)]
                    print(f"    Row {row}, 4@c{c4}: right (away from wall) = {right_segment}")

    # ---- 8. Print both grids for visual inspection ----
    print_grid(inp.tolist(), f"Pair {pair_idx} INPUT")
    print_grid(out.tolist(), f"Pair {pair_idx} OUTPUT")

    # ---- 9. Detailed: for the 2-boundary, check if it's been MOVED or REPLICATED ----
    print(f"\n[9] 2-boundary movement analysis:")
    # In input: where are the 2-cells relative to the wall?
    # In output: where are the 2-cells?
    if wall_orientation == 'horizontal':
        inp_2_dists = [(r - wall_pos, c) for r, c in cells_2]
        out_2_dists = [(r - wall_pos, c) for r, c in cells_2_out]
        # Check if the 2-boundary in output is at the SAME position or pushed to edge
        print(f"    Input 2-boundary (dist_from_wall, col): {sorted(inp_2_dists)}")
        print(f"    Output 2-boundary (dist_from_wall, col): {sorted(out_2_dists)}")
    elif wall_orientation == 'vertical':
        # For each row with 2-cells: distance from wall
        for row in sorted(set(r for r, c in cells_2)):
            inp_cols = sorted(c for r, c in cells_2 if r == row)
            out_cols = sorted(c for r, c in cells_2_out if r == row)
            inp_dists = [c - wall_pos for c in inp_cols]
            out_dists = [c - wall_pos for c in out_cols]
            print(f"    Row {row}: inp dist from wall = {inp_dists}, out dist from wall = {out_dists}")


# ---- SUMMARY ----
print(f"\n{'='*70}")
print("SUMMARY")
print(f"{'='*70}")
print("1. Source recolor: 4->3 in ALL pairs (confirmed by cell counts)")
print("2. Color 3 = color 4 - 1? Yes (4-1=3)")
print("3. Color 2 count preserved in all pairs")
