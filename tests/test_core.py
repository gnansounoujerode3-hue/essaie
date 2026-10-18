from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from shortsforge.planner import build_plan, plan_durations, score_hook
from shortsforge.qa import analyze
from shortsforge.skills import load_all
from shortsforge.spec import Cta, Motion, ShortSpec


SCRIPT = (
    "3 erreurs qui tuent tes vues. "
    "Commence par la promesse, jamais par ta présentation. "
    "Coupe les plans morts toutes les deux secondes. "
    "Ajoute des sous-titres lisibles. "
    "Abonne-toi pour la suite."
)


class PlannerTests(unittest.TestCase):
    def test_build_plan_fills_timeline_and_cta(self) -> None:
        shots, captions, hook, meta = build_plan(
            SCRIPT,
            duration=28.0,
            cta="Abonne-toi",
            cta_duration=2.8,
            sources=["a.jpg", "b.jpg"],
        )
        self.assertEqual(shots[-1].id, "cta")
        self.assertAlmostEqual(sum(s.duration for s in shots), 28.0, places=3)
        self.assertEqual(hook.duration, 2.8)
        self.assertGreaterEqual(len(shots), 8)
        self.assertTrue(all(s.duration >= 1.4 for s in shots))
        self.assertTrue(all(s.duration <= 3.01 for s in shots))
        self.assertEqual(captions[-1].text, "Abonne-toi pour la suite.")
        self.assertAlmostEqual(meta["timeline"], 28.0, places=3)

    def test_plan_duration_conservation(self) -> None:
        for count, total in ((4, 10.0), (7, 21.0), (12, 25.2)):
            durations = plan_durations(["phrase courte"] * count, total, min_shot=1.4, max_shot=3.0)
            self.assertAlmostEqual(sum(durations), total, places=6)
            self.assertTrue(all(1.4 - 1e-8 <= d <= 3.0 + 1e-8 for d in durations))

    def test_requires_body_after_hook(self) -> None:
        with self.assertRaisesRegex(ValueError, "corps"):
            build_plan("Une accroche seule.", duration=24.0)

    def test_hook_score_is_bounded(self) -> None:
        self.assertGreaterEqual(score_hook("3 erreurs qui tuent tes vues"), 70)
        self.assertTrue(0 <= score_hook("Une phrase quelconque") <= 100)


class SpecTests(unittest.TestCase):
    def test_motion_dict_is_coerced(self) -> None:
        spec = ShortSpec.from_dict(
            {"duration": 2.0, "shots": [{"id": "one", "duration": 2.0, "motion": {"kind": "kenburns-out", "start_scale": 1.15, "end_scale": 1.0}}]}
        )
        self.assertIsInstance(spec.shots[0].motion, Motion)
        self.assertEqual(spec.shots[0].motion.kind, "kenburns-out")

    def test_yaml_round_trip_and_validation(self) -> None:
        shots, captions, hook, _ = build_plan(SCRIPT, duration=28.0, cta="Abonne-toi")
        spec = ShortSpec(
            title="Test",
            slug="test",
            duration=28.0,
            shots=shots,
            captions=captions,
            hook=hook,
            cta=Cta(text="ABONNE-TOI", at=25.2, duration=2.8),
        )
        with tempfile.TemporaryDirectory() as d:
            path = spec.save(Path(d) / "spec.yaml")
            loaded = ShortSpec.load(path)
        self.assertAlmostEqual(sum(s.duration for s in loaded.shots), loaded.duration, places=3)
        self.assertEqual(loaded.slug, "test")
        self.assertEqual(loaded.cta.text, "ABONNE-TOI")
        self.assertEqual(loaded.validate(), [])

    def test_qa_analyzes_method(self) -> None:
        shots, captions, hook, _ = build_plan(SCRIPT, duration=28.0, cta="Abonne-toi")
        spec = ShortSpec(
            title="Test QA", slug="test-qa", duration=28.0,
            shots=shots, captions=captions, hook=hook,
            cta=Cta(text="ABONNE-TOI", at=25.2, duration=2.8),
        )
        report = analyze(spec)
        self.assertGreaterEqual(report.score, 80)
        self.assertEqual(report.grade, "A" if report.score < 90 else "S")
        self.assertIn("Rythme de coupe", [c.name for c in report.checks])


class SkillLibraryTests(unittest.TestCase):
    def test_thirteen_skills_are_loadable(self) -> None:
        skills = load_all()
        self.assertEqual(len(skills), 13)
        ids = {s.id for s in skills}
        self.assertTrue({"hook-architect", "caption-artist", "qa-gatekeeper", "perf-analyst"}.issubset(ids))
        self.assertTrue(all(s.name and s.description and s.body for s in skills))


if __name__ == "__main__":
    unittest.main()
