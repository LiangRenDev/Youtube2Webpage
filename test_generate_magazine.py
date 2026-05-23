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

if __name__ == "__main__":
    unittest.main()
