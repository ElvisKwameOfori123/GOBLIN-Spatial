"""Exact integer reconciliation utilities used across GOBLIN-Spatial."""

from __future__ import annotations

import numpy as np


def integer_transport(row_totals, column_targets) -> np.ndarray:
    """Allocate integer column totals across integer row totals exactly.

    The fractional starting matrix is the proportional outer product. Cells
    are then rounded by deterministic largest remainder while preserving both
    margins exactly.
    """

    rows = np.asarray(row_totals, dtype=np.int64)
    cols = np.asarray(column_targets, dtype=np.int64)

    if (rows < 0).any() or (cols < 0).any():
        raise ValueError("integer transport margins must be non-negative")
    if int(rows.sum()) != int(cols.sum()):
        raise ValueError("row and column totals have different grand totals")

    n_rows = len(rows)
    n_cols = len(cols)
    grand_total = int(rows.sum())

    if grand_total == 0:
        return np.zeros((n_rows, n_cols), dtype=np.int64)

    quota = rows[:, None].astype(float) * cols[None, :].astype(float) / grand_total
    allocation = np.floor(quota + 1e-12).astype(np.int64)
    row_need = rows - allocation.sum(axis=1)
    col_need = cols - allocation.sum(axis=0)
    remainder = quota - allocation

    if (row_need < 0).any() or (col_need < 0).any():
        raise AssertionError("negative residual in integer transport")

    for flat in np.argsort(-remainder.ravel(), kind="stable"):
        if int(row_need.sum()) == 0:
            break
        i, j = divmod(int(flat), n_cols)
        if row_need[i] > 0 and col_need[j] > 0:
            allocation[i, j] += 1
            row_need[i] -= 1
            col_need[j] -= 1

    if int(row_need.sum()) > 0:
        for i in range(n_rows):
            while row_need[i] > 0:
                eligible = np.where(col_need > 0)[0]
                if len(eligible) == 0:
                    raise RuntimeError("integer transport became infeasible")
                j = int(eligible[np.argmax(remainder[i, eligible])])
                allocation[i, j] += 1
                row_need[i] -= 1
                col_need[j] -= 1

    if not np.array_equal(allocation.sum(axis=1), rows):
        raise AssertionError("integer transport row closure failed")
    if not np.array_equal(allocation.sum(axis=0), cols):
        raise AssertionError("integer transport column closure failed")

    return allocation


def integerise_matrix(fractional_matrix, row_targets, col_targets) -> np.ndarray:
    """Integerise an already reconciled matrix without changing its margins."""

    matrix = np.asarray(fractional_matrix, dtype=float)
    rows = np.asarray(row_targets, dtype=np.int64)
    cols = np.asarray(col_targets, dtype=np.int64)

    allocation = np.floor(matrix).astype(np.int64)
    row_need = rows - allocation.sum(axis=1)
    col_need = cols - allocation.sum(axis=0)

    if (row_need < 0).any() or (col_need < 0).any():
        raise AssertionError("negative residual during matrix integerisation")
    if int(row_need.sum()) != int(col_need.sum()):
        raise AssertionError("integerisation residual margins differ")

    fractional = matrix - np.floor(matrix)

    while int(row_need.sum()) > 0:
        eligible = (row_need > 0)[:, None] & (col_need > 0)[None, :]
        if not eligible.any():
            raise RuntimeError("no feasible residual cell remains")

        score = np.where(eligible, fractional, -1.0)
        i, j = np.unravel_index(int(np.argmax(score)), score.shape)
        allocation[i, j] += 1
        row_need[i] -= 1
        col_need[j] -= 1

    if not np.array_equal(allocation.sum(axis=1), rows):
        raise AssertionError("integerisation row closure failed")
    if not np.array_equal(allocation.sum(axis=0), cols):
        raise AssertionError("integerisation column closure failed")
    if (allocation < 0).any():
        raise AssertionError("integerisation produced negative values")

    return allocation
