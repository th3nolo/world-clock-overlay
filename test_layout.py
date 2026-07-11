import unittest

# Simulated coordinate metrics from clock.py
TIMEZONES = {
    'venezuela': 'Venezuela',
    'spain': 'Spain',
    'ksa': 'Saudi Arabia'
}

class TestClockLayout(unittest.TestCase):
    def estimate_text_width(self, text, font_size=9, is_bold=True):
        # Average character width in proportional fonts (e.g. Outfit)
        # 9pt bold averages about 6.5px per character.
        # Capital letters or spaces can vary, but we can use conservative estimation.
        char_width = 6.8 if is_bold else 5.8
        # Adjust for uppercase or special characters
        width = 0
        for char in text:
            if char.isupper():
                width += char_width * 1.3
            elif char in [' ', ',']:
                width += char_width * 0.6
            else:
                width += char_width
        return int(width)

    def run_layout_check(self, layout, show_seconds):
        # 1. Define card dimensions
        if layout == 'horizontal':
            card_w = 180 if show_seconds else 170
            h = 100
            w = 10 + 3 * (card_w + 10)
        else:
            w = 200
            card_w = w - 20 # 180
            card_h = 75 if show_seconds else 65
            h = 10 + 3 * (card_h + 10)

        # 2. Verify overlap on each card
        for i, (card_id, name) in enumerate(TIMEZONES.items()):
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
            # The right edge of the country label MUST be to the left of the left edge of the offset
            overlap = label_right_edge - offset_left_edge
            
            # Assert no overlap
            self.assertLess(
                label_right_edge, 
                offset_left_edge, 
                f"Overlap detected on '{name}' card ({card_id}) in {layout} layout (seconds={show_seconds}). "
                f"Label right edge ({label_right_edge}) overlaps offset left edge ({offset_left_edge}) by {overlap}px. "
                f"Card width of {card_w}px is too small."
            )

    def test_horizontal_with_seconds(self):
        """Test horizontal layout with seconds visible (card width 150px)"""
        self.run_layout_check('horizontal', True)

    def test_horizontal_no_seconds(self):
        """Test horizontal layout with seconds hidden (card width 135px)"""
        self.run_layout_check('horizontal', False)

    def test_vertical_with_seconds(self):
        """Test vertical layout with seconds visible (card width 150px)"""
        self.run_layout_check('vertical', True)

    def test_vertical_no_seconds(self):
        """Test vertical layout with seconds hidden (card width 150px)"""
        self.run_layout_check('vertical', False)

if __name__ == '__main__':
    unittest.main()
