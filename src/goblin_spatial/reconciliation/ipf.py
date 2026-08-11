"""Iterative proportional fitting for constraint-preserving matrices."""

from __future__ import annotations

import numpy as np


def ipf_reconcile(prior, row_targets, col_targets, tolerance: float = 1e-9, max_iterations: int = 20000):
    """Reconcile a non-negative prior matrix to row and column controls.

    Structural zeros in ``prior`` are preserved. Row and column grand totals
    must agree. Returns the reconciled matrix.
    """

    matrix = np.asarray(prior, dtype=float).copy()
    rows = np.asarray(row_targets, dtype=float)
    cols = np.asarray(col_targets, dtype=float)

    if (matrix < 0).any() or (rows < -tolerance).any() or (cols < -tolerance).any():
        raise ValueError("IPF inputs must be non-negative")
    if not np.isclose(rows.sum(), cols.sum(), atol=1e-6, rtol=0):
        raise ValueError("row and column grand totals differ")

    rows = np.where(np.abs(rows) < tolerance, 0.0, rows)
    cols = np.where(np.abs(cols) < tolerance, 0.0, cols)
    matrix[rows == 0, :] = 0.0
    matrix[:, cols == 0] = 0.0

    positive_rows = rows > 0
    positive_cols = cols > 0

    for i in np.where(positive_rows)[0]:
        if matrix[i, positive_cols].sum() <= 0:
            raise ValueError("positive row target has no structural support")
    for j in np.where(positive_cols)[0]:
        if matrix[positive_rows, j].sum() <= 0:
            raise ValueError("positive column target has no structural support")

    for _ in range(max_iterations):
        row_sums = matrix.sum(axis=1)
        row_scale = np.ones_like(rows)
        row_scale[positive_rows] = rows[positive_rows] / row_sums[positive_rows]
        matrix *= row_scale[:, None]

        col_sums = matrix.sum(axis=0)
        col_scale = np.ones_like(cols)
        col_scale[positive_cols] = cols[positive_cols] / col_sums[positive_cols]
        matrix *= col_scale[None, :]

        row_error = np.max(np.abs(matrix.sum(axis=1) - rows))
        col_error = np.max(np.abs(matrix.sum(axis=0) - cols))
        if max(row_error, col_error) <= tolerance:
            return matrix

    raise RuntimeError("IPF did not converge")
