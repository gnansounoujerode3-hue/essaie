"""Tests unitaires VESK (sans FFmpeg ni dépendance externe).

Exécution : python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

from vesk.analyze import build_clips, score_sentences  # noqa: E402
from vesk.captions import (build_events, generate, get_style,  # noqa: E402
                           parse_canvas)
from vesk.common import (SkillError, fmt_srt_time, fmt_timecode,  # noqa: E402
                         normalize_text, parse_time, sanitize_json, slugify,
                         write_json)
from vesk.hooks import build_hook_plan, generate_variants, load_library  # noqa: E402
from vesk.media import TimeMap, merge_ranges, render_cut, speech_ranges  # noqa: E402
from vesk.motion import build_motion, list_templates  # noqa: E402
from vesk.nle_premiere import (jsx_import_plan, normalize_plan, to_edl,  # noqa: E402
                               to_fcpxml, to_xmeml)
from vesk.retention import analyze_file, find_events  # noqa: E402
from vesk.retention import load_retention_csv, resample  # noqa: E402
from vesk.sfx import detect_cues  # noqa: E402
from vesk.transcript import (distribute_words, ensure_word_timings,  # noqa: E402
                             parse_srt, to_srt, trim_to_range)

SAMPLE_SRT = """1
00:00:00,500 --> 00:00:02,500
Regarde ce chiffre : 87 % de rétention.

2
00:00:03,000 --> 00:00:05,000
Personne ne te dira ça, mais le montage compte.
"""


class CommonTests(unittest.TestCase):
    def test_parse_time(self):
        self.assertAlmostEqual(parse_time("83.4"), 83.4)
        self.assertAlmostEqual(parse_time("01:23.400"), 83.4)
        self.assertAlmostEqual(parse_time("1:02:03,000"), 3723.0)
        with self.assertRaises(SkillError):
            parse_time("abc")

    def test_timecodes(self):
        self.assertEqual(fmt_srt_time(0), "00:00:00,000")
        self.assertEqual(fmt_srt_time(3723.456), "01:02:03,456")
        self.assertEqual(fmt_timecode(1.5, 30), "00:00:01:15")
        self.assertEqual(fmt_timecode(1.0, 25), "00:00:01:00")

    def test_helpers(self):
        self.assertEqual(slugify("Sous-titres animés !"), "sous-titres-animes")
        self.assertEqual(normalize_text("Rétention, ÉNORME!"), "retention enorme")

    def test_sanitize_json(self):
        cleaned = sanitize_json({"a": float("nan"), "b": [1, float("inf")]})
        self.assertIsNone(cleaned["a"])
        self.assertEqual(cleaned["b"], [1, None])
        write_json(Path("/tmp/vesk-json-test.json"), cleaned)


class TranscriptTests(unittest.TestCase):
    def test_parse_srt(self):
        segments = parse_srt(SAMPLE_SRT)
        self.assertEqual(len(segments), 2)
        self.assertAlmostEqual(segments[0]["start"], 0.5)
        self.assertEqual(segments[0]["text"], "Regarde ce chiffre : 87 % de rétention.")
        self.assertEqual(segments[1]["id"], 2)

    def test_distribute_words(self):
        words = distribute_words(["un", "deux", "trois."], 0.0, 3.0)
        self.assertEqual(len(words), 3)
        self.assertAlmostEqual(words[0]["start"], 0.0)
        self.assertAlmostEqual(words[-1]["end"], 3.0)
        self.assertLessEqual(words[0]["end"], words[1]["start"])

    def test_word_timings_and_srt(self):
        transcript = {"segments": parse_srt(SAMPLE_SRT), "duration": 5.0}
        normalized = ensure_word_timings(transcript["segments"])
        self.assertTrue(all(segment["words"] for segment in normalized))
        srt = to_srt(normalized)
        self.assertIn("-->", srt)
        self.assertIn("Personne ne te dira", srt)

    def test_trim(self):
        transcript = {"segments": ensure_word_timings(parse_srt(SAMPLE_SRT)),
                      "duration": 5.0}
        trimmed = trim_to_range(transcript, 2.5, 5.0)
        self.assertAlmostEqual(trimmed["segments"][0]["start"], 0.5)
        self.assertLessEqual(trimmed["segments"][-1]["end"], 2.5)


class CaptionsTests(unittest.TestCase):
    def setUp(self):
        self.transcript = {"segments": ensure_word_timings(parse_srt(SAMPLE_SRT)),
                           "duration": 5.0, "language": "fr"}

    def test_styles_available(self):
        for name in ("hormozi", "ali", "karaoke-pop", "boxed-black", "neon", "clean"):
            style = get_style(name)
            self.assertIn("font_size", style)

    def test_canvas(self):
        self.assertEqual(parse_canvas("auto", {"width": 1920, "height": 1080}), (1920, 1080))
        self.assertEqual(parse_canvas("auto", {"width": 1080, "height": 1920}), (1080, 1920))
        self.assertEqual(parse_canvas("720x1280"), (720, 1280))
        with self.assertRaises(SkillError):
            parse_canvas("bad")

    def test_ass_output(self):
        result = generate(self.transcript, style_name="hormozi", canvas=(1080, 1920),
                          keywords=["rétention"])
        ass = result["ass"]
        self.assertIn("[Script Info]", ass)
        self.assertIn("PlayResY: 1920", ass)
        self.assertIn("Dialogue:", ass)
        self.assertTrue(result["events"])
        # le texte ne doit jamais dépasser 2 lignes
        for event in result["events"]:
            self.assertLessEqual(event["text"].count("\\N"), 1)

    def test_emoji_inserted(self):
        result = generate(self.transcript, style_name="ali", canvas=(1080, 1920),
                          emoji_map={"map": {"retention": "📉"}})
        self.assertIn("📉", result["ass"])

    def test_karaoke(self):
        result = generate(self.transcript, style_name="ali", canvas=(1080, 1920))
        self.assertIn("\\kf", result["ass"])


class HighlightTests(unittest.TestCase):
    def test_scores_and_clips(self):
        transcript = {"segments": ensure_word_timings(parse_srt(SAMPLE_SRT)),
                      "duration": 5.0}
        scored = score_sentences(transcript)
        self.assertEqual(len(scored), 2)
        self.assertGreater(max(s["score"] for s in scored), 0)
        self.assertTrue(all(0 <= s["score"] <= 100 for s in scored))
        clips = build_clips(scored, min_duration=2, max_duration=6, max_clips=2)
        self.assertTrue(clips)
        for clip in clips:
            self.assertGreater(clip["end"], clip["start"])


class MediaTests(unittest.TestCase):
    def test_merge_ranges(self):
        merged = merge_ranges([
            {"start": 0, "end": 2}, {"start": 1.5, "end": 3}, {"start": 4, "end": 5},
        ])
        self.assertEqual(len(merged), 2)
        self.assertAlmostEqual(merged[0]["end"], 3)

    def test_speech_ranges(self):
        ranges = speech_ranges(10.0, [{"start": 3.0, "end": 5.0}], pad=0.0)
        self.assertEqual(len(ranges), 2)
        self.assertAlmostEqual(ranges[0]["start"], 0.0)

    def test_time_map(self):
        time_map = TimeMap([{"start": 0, "end": 4, "speed": 1.0},
                            {"start": 6, "end": 10, "speed": 2.0}])
        self.assertAlmostEqual(time_map.duration, 6.0)
        self.assertAlmostEqual(time_map.to_source(0.0), 0.0)
        self.assertAlmostEqual(time_map.to_source(4.5), 7.0)
        mapped = time_map.map_segments([{"start": 0, "end": 2, "text": "a", "words": []}])
        self.assertAlmostEqual(mapped[0]["end"], 2.0)

    def test_render_cut_requires_ranges(self):
        with self.assertRaises(SkillError):
            render_cut("x.mp4", "y.mp4", [])


class NLETests(unittest.TestCase):
    def setUp(self):
        self.plan = normalize_plan({
            "name": "Test",
            "fps": 30,
            "width": 1080,
            "height": 1920,
            "clips": [
                {"source": "/tmp/a.mp4", "in": 0, "out": 2, "source_duration": 10,
                 "width": 1080, "height": 1920},
                {"source": "/tmp/b.mp4", "in": 1, "out": 3, "source_duration": 8,
                 "width": 1080, "height": 1920},
            ],
        })

    def test_fcpxml(self):
        xml = to_fcpxml(self.plan)
        self.assertIn("<fcpxml version=\"1.9\">", xml)
        ET.fromstring(xml.split("?>", 1)[1])

    def test_xmeml(self):
        xml = to_xmeml(self.plan)
        self.assertIn("<xmeml version=\"5\">", xml)
        self.assertIn("<pathurl>file://localhost/tmp/a.mp4</pathurl>", xml)
        ET.fromstring(xml.split("?>", 1)[1])

    def test_edl_and_jsx(self):
        edl = to_edl(self.plan)
        self.assertIn("TITLE: Test", edl)
        self.assertIn("FROM CLIP NAME: a.mp4", edl)
        jsx = jsx_import_plan(self.plan)
        self.assertIn("app.project", jsx)
        self.assertIn("createNewSequence", jsx)

    def test_plan_positions(self):
        self.assertAlmostEqual(self.plan["clips"][0]["start"], 0.0)
        self.assertAlmostEqual(self.plan["clips"][1]["start"], 2.0)
        self.assertAlmostEqual(self.plan["duration"], 4.0)


class RetentionTests(unittest.TestCase):
    def test_csv(self):
        sample = ROOT / "examples" / "retention.csv"
        points = load_retention_csv(sample)
        self.assertGreater(len(points), 5)
        self.assertEqual(points[0]["retention"], 100)
        resampled = resample(points, 5)
        self.assertGreater(len(resampled), 3)
        events = find_events(resampled, window=60, min_drop=5)
        self.assertIn("drops", events)
        analysis = analyze_file(sample, min_drop=5)
        self.assertGreater(analysis["duration"], 0)
        self.assertTrue(analysis["recommendations"])

    def test_bad_csv(self):
        with self.assertRaises(SkillError):
            load_retention_csv(ROOT / "skills" / "viral-hooks-library" / "hooks.json")


class HookTests(unittest.TestCase):
    def test_library_and_plan(self):
        library = load_library()
        self.assertGreaterEqual(len(library["templates"]), 20)
        variants = generate_variants("le montage vidéo", library, count=4)
        self.assertEqual(len(variants), 4)
        self.assertTrue(all(variant["hook"] for variant in variants))
        plan = build_hook_plan("le montage vidéo", library, count=4)
        self.assertIn("primary_hook", plan)
        self.assertTrue(0 <= plan["viral_score"]["score"] <= 100)
        self.assertEqual(len(plan["alternatives"]), 3)

    def test_fill(self):
        from vesk.hooks import fill
        text = fill("Personne ne te dira ça, mais {sujet}.", {"sujet": "le montage"})
        self.assertEqual(text, "Personne ne te dira ça, mais le montage.")


class MotionTests(unittest.TestCase):
    def test_templates(self):
        ids = {template["id"] for template in list_templates()}
        for name in ("title", "lower-third", "chapter", "quote", "counter",
                     "progress", "callout", "cta"):
            self.assertIn(name, ids)

    def test_build(self):
        ass = build_motion("title", text="Trois astuces", subtitle="de montage",
                           duration=3, canvas=(1080, 1920))
        self.assertIn("Dialogue:", ass)
        self.assertIn("TROIS ASTUCES", ass)
        counter = build_motion("counter", number=87, text="% de rétention",
                               duration=2, canvas=(1080, 1920))
        self.assertIn("Dialogue:", counter)
        with self.assertRaises(SkillError):
            build_motion("inconnu", text="x")


class SFXTests(unittest.TestCase):
    def test_detect_cues(self):
        transcript = {"segments": ensure_word_timings(parse_srt(SAMPLE_SRT)),
                      "duration": 5.0}
        cues = detect_cues(transcript, keywords=["rétention"])
        self.assertTrue(cues)
        self.assertEqual(cues[0]["time"], 0.0)
        self.assertTrue(all(cue["sfx"] for cue in cues))
        times = [cue["time"] for cue in cues]
        self.assertEqual(times, sorted(times))


class InstallTests(unittest.TestCase):
    def test_all_skills_documented(self):
        skills = sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir())
        self.assertEqual(len(skills), 19)
        for skill in skills:
            content = (skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---"), skill.name)
            self.assertIn("name:", content, skill.name)
            self.assertIn("description:", content, skill.name)
            self.assertTrue((skill / "scripts").is_dir(), skill.name)

    def test_json_assets(self):
        for path in ROOT.rglob("*.json"):
            if ".testdata" in path.parts or ".git" in path.parts:
                continue
            if any(part in {"node_modules", "__pycache__"} for part in path.parts):
                continue
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
