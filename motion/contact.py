"""Hand contact: where an implement sits in the closed hand."""


def grip_point(P, side):
    """Handle centre across the palm at the knuckle line, and the knuckle-line direction
    (index -> little finger)."""
    k2, k5 = P.head(f"finger2-1.{side}"), P.head(f"finger5-1.{side}")
    w = P.head(f"wrist.{side}")
    k3 = P.head(f"finger3-1.{side}")
    n = P.palm_now(side)
    f = (k3 - w).normalized()
    return (k2 + k5) / 2 + n * 0.024 + f * 0.012, (k5 - k2).normalized()
