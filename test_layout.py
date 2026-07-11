import unittest

# Simulated coordinate metrics from clock.py (panel layout)
# Labels are short uppercase city names; worst cases from COMMON_ZONES
SHORT_LABELS = [
    'LOCAL',
    'MADRID',
    'RIYADH',
    'NEW YORK',
    'MEXICO CITY',
    'BUENOS AIRES',
    'JOHANNESBURG',
]

PAD = 16          # cell padding
LABEL_X = 39      # pad + flag width + gap (16 + 23)
GLYPH_W = 10      # day/night mark width at 9pt
STATUS_H = 24

class TestClockLayout(unittest.TestCase):
    def estimate_text_width(self, text, font_size=8, is_bold=True):
        char_width = (6.8 if is_bold else 5.8) * font_size / 9
        width = 0
        for char in text:
            if char.isupper():
                width += char_width * 1.3
            elif char in [' ', ',', '.', '+']:
                width += char_width * 0.6
            else:
                width += char_width
        return int(width)

    def cell_bounds(self, layout, show_seconds, i, N):
        if layout == 'horizontal':
            col_w = 190 if show_seconds else 180
            x1 = 10 + i * col_w
            x2 = x1 + col_w
        else:
            x1 = 10
            x2 = 190  # w=200, panel inset 10 each side
        return x1, x2

    def run_layout_check(self, layout, show_seconds, N=3):
        for i in range(N):
            x1, x2 = self.cell_bounds(layout, show_seconds, i, N)
            for label in SHORT_LABELS:
                # Head row: label must not reach the day/night mark
                label_right = x1 + LABEL_X + self.estimate_text_width(label, font_size=8, is_bold=True)
                glyph_left = x2 - PAD - GLYPH_W
                self.assertLess(
                    label_right,
                    glyph_left,
                    f"Label '{label}' overlaps day/night mark in {layout} layout "
                    f"(seconds={show_seconds}, N={N}): {label_right} >= {glyph_left}"
                )

            # Meta row: offset + gap + date must fit inside the cell
            offset_w = self.estimate_text_width("+10.5h", font_size=8, is_bold=True)
            date_w = self.estimate_text_width("Wed, Sep 30", font_size=8, is_bold=False)
            meta_right = x1 + PAD + offset_w + 6 + date_w
            self.assertLess(
                meta_right,
                x2 - PAD,
                f"Meta row overflows cell in {layout} layout "
                f"(seconds={show_seconds}, N={N}): {meta_right} >= {x2 - PAD}"
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
