"""Offline tests for Minecraft Studio scripts. Run: python -m unittest discover -s tests -v"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plugins" / "minecraft-studio" / "scripts"
TEMPLATES = ROOT / "plugins" / "minecraft-studio" / "templates"
FIX = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import build_mrpack  # noqa: E402
import log_scan  # noqa: E402
import modrinth  # noqa: E402
import quests  # noqa: E402
import release_docs  # noqa: E402
import validate  # noqa: E402
from _common import java_for, load_json  # noqa: E402


def levels(report):
    return [i[0] for i in report.items]


class TestLogScan(unittest.TestCase):
    def test_fabric_missing_dep(self):
        r = log_scan.scan((FIX / "fabric-missing-dep.log").read_text())
        rules = {f["rule"] for f in r["findings"]}
        self.assertIn("fabric-incompatible", rules)
        self.assertIn("fabric-missing-dep", rules)
        self.assertIn("fabric-api", r["suspects"])

    def test_wrong_java(self):
        r = log_scan.scan((FIX / "crash-wrong-java.txt").read_text())
        self.assertEqual(r["findings"][0]["rule"], "wrong-java")
        self.assertEqual(r["description"], "Initializing game")

    def test_mixin_suspect(self):
        r = log_scan.scan((FIX / "crash-mixin.txt").read_text())
        self.assertIn("mixin-failure", {f["rule"] for f in r["findings"]})
        self.assertIn("coolmod", r["suspects"])

    def test_signature_stable(self):
        t = (FIX / "crash-mixin.txt").read_text()
        self.assertEqual(log_scan.scan(t)["signature"], log_scan.scan(t.replace("12:00", "13:37"))["signature"])


class TestAudit(unittest.TestCase):
    def test_audit_flags(self):
        rep = modrinth.audit(load_json(FIX / "lock.json"))
        text = "\n".join(f"{l} {w} {m}" for l, w, m in rep.items)
        self.assertEqual(rep.verdict, "FAIL")
        self.assertIn("MISSING1", text)          # missing required dependency
        self.assertIn("beta", text)              # beta version is LOOK
        self.assertIn("not measured", text)      # runtime always unverified

    def test_parse_list(self):
        got = modrinth.parse_list(["sodium", "rp:faithful-32x  # textures", "create@6.0.0", "", "# x"])
        self.assertEqual(got, [("sodium", None, None), ("faithful-32x", "resourcepack", None), ("create", None, "6.0.0")])


class TestValidate(unittest.TestCase):
    def test_bad_pack(self):
        rep = validate.run(FIX / "badpack", "1.21.1")
        fails = [w + " " + m for l, w, m in rep.items if l == "FAIL"]
        self.assertTrue(any("invalid JSON" in f for f in fails))
        self.assertTrue(any("expects 34" in f for f in fails))
        self.assertTrue(any("lowercase" in f for f in fails))

    def test_good_rp(self):
        rep = validate.run(FIX / "goodrp", "1.21.1")
        self.assertEqual(rep.verdict, "PASS", rep.items)

    def test_unknown_version_is_look(self):
        rep = validate.run(FIX / "goodrp", "9.99")
        self.assertIn("LOOK", levels(rep))
        self.assertNotIn("FAIL", levels(rep))


class TestQuests(unittest.TestCase):
    def test_example_design_builds_and_validates(self):
        d = load_json(TEMPLATES / "quest-design.example.json")
        self.assertEqual(quests.check(d), [])
        with tempfile.TemporaryDirectory() as tmp:
            quests.build(d, Path(tmp), "1.21")
            base = Path(tmp) / "config" / "ftbquests" / "quests"
            self.assertTrue((base / "lang" / "en_us.snbt").exists())
            chapters = list((base / "chapters").glob("*.snbt"))
            self.assertEqual(len(chapters), 1)
            self.assertRegex(chapters[0].stem, r"^[0-9A-F]{16}$")
            rep = validate.run(Path(tmp), None)
            self.assertNotIn("FAIL", levels(rep), rep.items)

    def test_ids_stable(self):
        self.assertEqual(quests.hex_id("quest", "a/b"), quests.hex_id("quest", "a/b"))

    def test_cycle_and_dangling(self):
        d = {"chapters": [{"key": "c", "quests": [
            {"key": "a", "deps": ["b"], "tasks": [{"type": "checkmark"}]},
            {"key": "b", "deps": ["a"], "tasks": [{"type": "checkmark"}]},
            {"key": "x", "deps": ["nope"], "tasks": [{"type": "checkmark"}]}]}]}
        errs = "\n".join(quests.check(d))
        self.assertIn("cycle", errs)
        self.assertIn("nope", errs)

    def test_format_120_inline(self):
        d = load_json(TEMPLATES / "quest-design.example.json")
        with tempfile.TemporaryDirectory() as tmp:
            quests.build(d, Path(tmp), "1.20")
            ch = next((Path(tmp) / "config/ftbquests/quests/chapters").glob("*.snbt")).read_text()
            self.assertIn('title: "Timber"', ch)
            self.assertIn('item: "minecraft:oak_log"', ch)


class TestBuild(unittest.TestCase):
    def test_mrpack(self):
        lock = load_json(FIX / "lock.json")
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp) / "pack"
            (pack_dir / "overrides" / "config").mkdir(parents=True)
            (pack_dir / "overrides" / "config" / "a.toml").write_text("x=1")
            out = build_mrpack.build_mrpack(lock, pack_dir, Path(tmp) / "dist", "1.0.0")
            with zipfile.ZipFile(out) as z:
                idx = json.loads(z.read("modrinth.index.json"))
                self.assertIn("overrides/config/a.toml", z.namelist())
            self.assertEqual(idx["dependencies"], {"minecraft": "1.21.1", "fabric-loader": "0.16.9"})
            self.assertEqual(len(idx["files"]), 3)
            self.assertEqual(idx["files"][1]["env"]["server"], "unsupported")


class TestDocs(unittest.TestCase):
    def test_credits_and_changelog(self):
        lock = load_json(FIX / "lock.json")
        self.assertIn("https://modrinth.com/mod/sodium", release_docs.credits(lock))
        new = json.loads(json.dumps(lock))
        new["entries"] = new["entries"][:2]
        new["entries"][0]["version_number"] = "0.117.0"
        cl = release_docs.changelog(lock, new, "1.1.0")
        self.assertIn("### Removed", cl)
        self.assertIn("0.116.0+1.21.1 → 0.117.0", cl)

    def test_java(self):
        self.assertEqual(java_for("1.21.1"), "21")
        self.assertEqual(java_for("1.20.1"), "17")


class TestRepoFiles(unittest.TestCase):
    def test_manifests_json(self):
        for p in [ROOT / ".claude-plugin" / "marketplace.json",
                  ROOT / "plugins" / "minecraft-studio" / ".claude-plugin" / "plugin.json",
                  ROOT / "plugins" / "minecraft-studio" / "third-party" / "registry.json"]:
            load_json(p)

    def test_skills_have_frontmatter(self):
        skills = list((ROOT / "plugins" / "minecraft-studio" / "skills").glob("*/SKILL.md"))
        self.assertGreaterEqual(len(skills), 12)
        for s in skills:
            text = s.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\nname: " + s.parent.name + "\n"), s)
            self.assertIn("description:", text.split("---")[1], s)


if __name__ == "__main__":
    unittest.main()
