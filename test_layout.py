import unittest

# Simulated coordinate metrics from clock.py
TIMEZONES = {
    'venezuela': 'Venezuela',
    'spain': 'Spain',
    'ksa': 'Saudi Arabia'
}

class TestClockLayout(unittest.TestCase):
    def estimate_text_width(self, text, font_size=9, is_bold=True):
        char_width = 6.8 if is_bold else 5.8
        width = 0
        for char in text:
            if char.isupper():
                width += char_width * 1.3
            elif char in [' ', ',']:
                width += char_width * 0.6
            else:
                width += char_width
        return int(width)

    def run_layout_check(self, layout, show_seconds, N=3):
        # 1. Define card dimensions
        if layout == 'horizontal':
            card_w = 180 if show_seconds else 170
            h = 125
            w = N * (card_w + 10) + 10
        else:
            w = 200
            card_w = w - 20 # 180
            card_h = 75 if show_seconds else 65
            h = N * (card_h + 10) + 40

        # Simulate list of cards of length N
        cards = []
        tz_list = list(TIMEZONES.items())
        for idx in range(N):
            cards.append(tz_list[idx % len(tz_list)])

        # 2. Verify overlap on each card
        for i, (card_id, name) in enumerate(cards):
            if layout == 'horizontal':
                x1 = 10 + i * (card_w + 10)
                x2 = x1 + card_w
            else:
                x1 = 10
                x2 = w - 10

            # Left position of flag and label
            flag_x = x1 + 10
            label_x = flag_x + 22 # x1 + 32
            
            # Label width (9pt bold Outfit)
            label_width = self.estimate_text_width(name, font_size=9, is_bold=True)
            label_right_edge = label_x + label_width

            # Offset indicator ("+10.5h" is longest possible offset)
            longest_offset = "+10.5h"
            offset_x = x2 - 10 # Right anchor
            offset_width = self.estimate_text_width(longest_offset, font_size=8, is_bold=True)
            offset_left_edge = offset_x - offset_width

            # Bounding box collision assertion
            overlap = label_right_edge - offset_left_edge
            self.assertLess(
                label_right_edge, 
                offset_left_edge, 
                f"Overlap detected on '{name}' card ({card_id}) in {layout} layout (seconds={show_seconds}, N={N}). "
                f"Label right edge ({label_right_edge}) overlaps offset left edge ({offset_left_edge}) by {overlap}px."
            )

    def test_horizontal_with_seconds(self):
        """Test horizontal layout with seconds visible for various clock counts"""
        for n in range(1, 6):
            self.run_layout_check('horizontal', True, N=n)

    def test_horizontal_no_seconds(self):
        """Test horizontal layout with seconds hidden for various clock counts"""
        for n in range(1, 6):
            self.run_layout_check('horizontal', False, N=n)

    def test_vertical_with_seconds(self):
        """Test vertical layout with seconds visible for various clock counts"""
        for n in range(1, 6):
            self.run_layout_check('vertical', True, N=n)

    def test_vertical_no_seconds(self):
        """Test vertical layout with seconds hidden for various clock counts"""
        for n in range(1, 6):
            self.run_layout_check('vertical', False, N=n)

if __name__ == '__main__':
    unittest.main()
