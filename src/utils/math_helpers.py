def safe_cagr(start_val: float, end_val: float, years: int | float) -> float:
    if years <= 0 or start_val <= 0 or end_val <= 0:
        return 0.0
    return (end_val / start_val) ** (1 / years) - 1
