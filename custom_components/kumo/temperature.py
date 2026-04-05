"""Mitsubishi-specific temperature conversion utilities.

Mitsubishi systems use 0.5C steps internally, but their F-to-C mapping
diverges from standard math at several points (64-66F, 69-72F). Using
these lookup tables ensures setpoints match the Comfort app and physical
thermostat exactly.
"""

import math

# Mitsubishi's proprietary Fahrenheit-to-Celsius setpoint mapping (61-80F)
F_TO_C: dict[int, float] = {
    61: 16.0, 62: 16.5, 63: 17.0, 64: 17.5, 65: 18.0, 66: 18.5,
    67: 19.5, 68: 20.0, 69: 21.0, 70: 21.5, 71: 22.0, 72: 22.5,
    73: 23.0, 74: 23.5, 75: 24.0, 76: 24.5, 77: 25.0, 78: 25.5,
    79: 26.0, 80: 26.5,
}

# Reverse mapping: Celsius to Fahrenheit for display
C_TO_F: dict[float, int] = {
    16.0: 61, 16.5: 62, 17.0: 63, 17.5: 64, 18.0: 65, 18.5: 66,
    19.0: 67, 19.5: 67, 20.0: 68, 20.5: 69,
    21.0: 69, 21.5: 70, 22.0: 71, 22.5: 72,
    23.0: 73, 23.5: 74, 24.0: 75, 24.5: 76, 25.0: 77, 25.5: 78,
    26.0: 79, 26.5: 80,
}


def c_to_f(celsius: float) -> float:
    """Convert Celsius to Fahrenheit using Mitsubishi lookup, with standard fallback."""
    if celsius is None:
        return None
    result = C_TO_F.get(celsius)
    if result is not None:
        return result
    return round(celsius * 9 / 5 + 32)


def f_to_c(fahrenheit: float) -> float:
    """Convert Fahrenheit to Celsius using Mitsubishi lookup, with fallback to nearest 0.5C."""
    if fahrenheit is None:
        return None
    result = F_TO_C.get(int(fahrenheit))
    if result is not None:
        return result
    # Fallback: standard conversion rounded to nearest 0.5C
    raw = (fahrenheit - 32) * 5 / 9
    return math.floor(raw * 2 + 0.5) / 2
