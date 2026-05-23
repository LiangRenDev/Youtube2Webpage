import unittest
from generate_magazine import vtt_ts_to_secs, parse_vtt_clean_entries

SAMPLE_VTT = """WEBVTT
Kind: captions
Language: en

00:00:02.399 --> 00:00:04.789 align:start position:0%

All<00:00:02.480><c> right.</c><00:00:02.879><c> Um</c>

00:00:04.789 --> 00:00:04.799 align:start position:0%
All right. Um I guess let's get started.


00:00:04.799 --> 00:00:07.030 align:start position:0%
All right. Um I guess let's get started.
Uh<00:00:05.040><c> my</c><00:00:05.200><c> name</c>

00:00:07.030 --> 00:00:07.040 align:start position:0%
Uh my name is Ashok. I lead the Tesla AI

"""

class TestVttParser(unittest.TestCase):
    def test_vtt_ts_to_secs(self):
        self.assertAlmostEqual(vtt_ts_to_secs("00:00:04.789"), 4.789)
        self.assertAlmostEqual(vtt_ts_to_secs("00:01:23.430"), 83.430)
        self.assertAlmostEqual(vtt_ts_to_secs("00:24:29.140"), 1469.140)

    def test_parse_vtt_clean_entries_count(self):
        entries = parse_vtt_clean_entries(SAMPLE_VTT)
        self.assertEqual(len(entries), 2)

    def test_parse_vtt_clean_entries_content(self):
        entries = parse_vtt_clean_entries(SAMPLE_VTT)
        self.assertAlmostEqual(entries[0]["secs"], 4.789)
        self.assertEqual(entries[0]["text"], "All right. Um I guess let's get started.")
        self.assertAlmostEqual(entries[1]["secs"], 7.030)
        self.assertEqual(entries[1]["text"], "Uh my name is Ashok. I lead the Tesla AI")

from generate_magazine import img_filename_to_secs, format_display_ts, assign_chapter

class TestHelpers(unittest.TestCase):
    def test_img_filename_to_secs(self):
        self.assertAlmostEqual(img_filename_to_secs("00-00-04.789.jpg"), 4.789)
        self.assertAlmostEqual(img_filename_to_secs("00-01-23.430.jpg"), 83.430)
        self.assertAlmostEqual(img_filename_to_secs("00-24-28.710.jpg"), 1468.710)

    def test_format_display_ts(self):
        self.assertEqual(format_display_ts(4.789),    "0:04")
        self.assertEqual(format_display_ts(83.430),   "1:23")
        self.assertEqual(format_display_ts(1469.14),  "24:29")

    def test_assign_chapter(self):
        self.assertEqual(assign_chapter(0)["slug"],    "intro")
        self.assertEqual(assign_chapter(200)["slug"],  "architecture")
        self.assertEqual(assign_chapter(600)["slug"],  "data")
        self.assertEqual(assign_chapter(960)["slug"],  "simulator")
        self.assertEqual(assign_chapter(1300)["slug"], "robots")

if __name__ == "__main__":
    unittest.main()
