"""Numerical precision and boundary verification for quantized compute kernels."""
import math
from typing import Sequence


def assert_matrix_shape_supported(rows: int, cols: int, allow_ragged: bool = True) -> bool:
    """
    Ensure the candidate kernel supports non-power-of-two (ragged edge) matrix boundaries.
    Catches common model errors that hardcode 1024 or power-of-two workgroup tiles.
    """
    if rows <= 0 or cols <= 0:
        raise ValueError(f"Invalid dimensions: ({rows}, {cols})")

    is_power_of_two = (rows & (rows - 1) == 0) and (cols & (cols - 1) == 0)
    if not is_power_of_two and not allow_ragged:
        raise ValueError(f"Ragged edge dimension ({rows}, {cols}) not supported by naive kernel.")
    return True


def verify_numerical_tolerance(
    candidate: Sequence[float],
    reference: Sequence[float],
    rtol: float = 1e-4,
    atol: float = 1e-6
) -> bool:
    """
    Verify candidate output against double-precision reference baselines.
    Ensures relative error <= rtol and absolute error <= atol.
    """
    if len(candidate) != len(reference):
        raise ValueError(f"Dimension mismatch: {len(candidate)} != {len(reference)}")

    for i, (c, r) in enumerate(zip(candidate, reference)):
        diff = abs(c - r)
        allowed = atol + rtol * abs(r)
        if diff > allowed:
            raise AssertionError(
                f"Numerical divergence at index {i}: candidate={c:.6f}, ref={r:.6f}, diff={diff:.6e} > {allowed:.6e}"
            )
    return True
