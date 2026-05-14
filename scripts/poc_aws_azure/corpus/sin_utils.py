import random


def generate_valid_sin() -> str:
    """Generate a random 9-digit SIN that passes Luhn check.
    Use prefix 1-7 (not 0, 8, or 9 which are reserved)."""
    while True:
        # Generate 8 random digits with valid prefix
        prefix = random.randint(1, 7)
        digits = [prefix] + [random.randint(0, 9) for _ in range(7)]
        # Calculate Luhn check digit
        total = 0
        for i, d in enumerate(digits):
            if i % 2 == 1:  # Double every second digit (0-indexed)
                doubled = d * 2
                total += doubled - 9 if doubled > 9 else doubled
            else:
                total += d
        check = (10 - (total % 10)) % 10
        digits.append(check)
        return "".join(str(d) for d in digits)


def validate_sin(sin: str) -> bool:
    """Validate a SIN string (with or without separators) against Luhn."""
    # Strip common separators
    clean = sin.replace(" ", "").replace("-", "")
    if len(clean) != 9 or not clean.isdigit():
        return False
    digits = [int(d) for d in clean]
    total = 0
    for i, d in enumerate(digits):
        if i % 2 == 1:
            doubled = d * 2
            total += doubled - 9 if doubled > 9 else doubled
        else:
            total += d
    return total % 10 == 0
