#!/usr/bin/env python3
"""Quick debug script to test crossing logic"""

# Simulate tracker positions from your video
line_y = 540
tol = 10

# Simulate a vehicle moving down (from above line to below)
test_cases = [
    # (id, prev_cy, cy, should_count)
    (1, 500, 520, False),  # Moving down but not crossing yet
    (1, 520, 545, True),   # Crossing from 520 to 545 (crosses 540)
    (2, 668, 695, False),  # Already below line, no crossing
    (3, 530, 550, True),   # Crossing from 530 to 550 (crosses 540)
]

print(f"Line at y={line_y}, tolerance={tol}")
print(f"Zone: {line_y - tol} to {line_y + tol}\n")

for id, prev_cy, cy, expected in test_cases:
    # Check if in zone
    in_zone = (line_y - tol <= cy <= line_y + tol)
    
    # Check crossing
    crossed_down = prev_cy < line_y and cy >= line_y
    crossed_up = prev_cy > line_y and cy <= line_y
    
    result = "✓ COUNTED" if (crossed_down or crossed_up) else "✗ not counted"
    match = "✓" if ((crossed_down or crossed_up) == expected) else "✗ MISMATCH"
    
    print(f"{match} id={id} prev_cy={prev_cy:3d} cy={cy:3d} | in_zone={in_zone} crossed_down={crossed_down} crossed_up={crossed_up} | {result}")
