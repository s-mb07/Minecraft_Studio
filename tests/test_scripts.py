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


# ---------------- v0.2 mod tooling ----------------
import gzip  # noqa: E402
import shutil  # noqa: E402

import _png  # noqa: E402
import bbmodel_check  # noqa: E402
import jar_inspect  # noqa: E402
import mod_check  # noqa: E402
import mod_new  # noqa: E402
import texture  # noqa: E402
from _common import Report  # noqa: E402


def make_fake_mod(root: Path, with_assets: bool):
    j = root / "src/main/java/com/x/demo"
    j.mkdir(parents=True)
    (j / "Demo.java").write_text('public class Demo { public static final String MOD_ID = "demo"; }')
    (j / "ModItems.java").write_text(
        'import net.minecraft.core.registries.BuiltInRegistries;\n'
        'public class ModItems {\n'
        '  public static final Item GEM = register("gem", new Item(new Item.Properties()));\n'
        '  static Item register(String n, Item i) { return Registry.register(BuiltInRegistries.ITEM, Demo.id(n), i); }\n}\n')
    res = root / "src/main/resources"
    res.mkdir(parents=True)
    (res / "fabric.mod.json").write_text('{"id": "demo"}')
    if with_assets:
        m = res / "assets/demo/models/item"
        m.mkdir(parents=True)
        (m / "gem.json").write_text('{"parent": "minecraft:item/generated", "textures": {"layer0": "demo:item/gem"}}')
        texture.gen("gem", (200, 40, 60)).save(res / "assets/demo/textures/item/gem.png")


class TestModTools(unittest.TestCase):
    def test_png_roundtrip_and_gen(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "g.png"
            texture.gen("ore", (60, 200, 90), 16, 3).save(p)
            img = _png.load(p)
            self.assertEqual((img.w, img.h), (16, 16))
            self.assertEqual(img.get(0, 0)[3], 255)
            texture.preview(img, 4).save(Path(tmp) / "x4.png")
            self.assertEqual(_png.load(Path(tmp) / "x4.png").w, 64)

    def test_mod_check_missing_assets_then_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_fake_mod(Path(tmp), with_assets=False)
            r = mod_check.check(Path(tmp), fix=False)
            msgs = " ".join(m for l, w, m in r.items if l == "FAIL")
            self.assertIn("models/item/gem.json", msgs)
            self.assertIn("item.demo.gem", msgs)
        with tempfile.TemporaryDirectory() as tmp:
            make_fake_mod(Path(tmp), with_assets=True)
            r = mod_check.check(Path(tmp), fix=True)  # --fix adds the lang key
            self.assertNotIn("FAIL", [i[0] for i in r.items], r.items)
            lang = json.loads((Path(tmp) / "src/main/resources/assets/demo/lang/en_us.json").read_text())
            self.assertEqual(lang["item.demo.gem"], "Gem")

    def test_mod_check_fixes_blockbench_texture_ref(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_fake_mod(Path(tmp), with_assets=True)
            mp = Path(tmp) / "src/main/resources/assets/demo/models/item/gem.json"
            mp.write_text('{"textures": {"0": "gem"}, "elements": []}')
            mod_check.check(Path(tmp), fix=True)
            self.assertEqual(json.loads(mp.read_text())["textures"]["0"], "demo:item/gem")

    def test_bbmodel_check_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "m.json"
            p.write_text(json.dumps({"textures": {"0": "x"}, "elements": [
                {"name": "big", "from": [0, 0, 0], "to": [40, 1, 1], "rotation": {"angle": 30, "axis": "y"},
                 "faces": {"north": {"texture": "#1"}}}]}))
            r = Report("t")
            bbmodel_check.check_json_model(p, "demo", r)
            msgs = " ".join(m for l, w, m in r.items if l == "FAIL")
            for s in ("outside -16..32", "rotation 30", "#1", "no namespace"):
                self.assertIn(s, msgs)

    def test_jar_inspect(self):
        with tempfile.TemporaryDirectory() as tmp:
            jar = Path(tmp) / "demo.jar"
            with zipfile.ZipFile(jar, "w") as z:
                z.writestr("fabric.mod.json", '{"id": "demo", "version": "1.0", "depends": {"fabric-api": "*"}}')
                z.writestr("assets/demo/lang/en_us.json", '{"item.demo.gem": "Gem", "block.demo.ore": "Ore"}')
                z.writestr("assets/demo/textures/item/gem.png", b"x")
            info = jar_inspect.inspect(jar)
            self.assertEqual(info["loader"], "fabric")
            self.assertEqual(info["ids"]["item"], ["demo:gem"])
            self.assertEqual(info["ids"]["block"], ["demo:ore"])

    def test_nbt_and_render(self):
        data = gzip.decompress(mod_new.nbt_empty_structure())
        self.assertEqual(data[0], 10)
        self.assertIn(b"DataVersion", data)
        subs = {"__PKG__": "a.b", "__MODID__": "demo", "__CLASS__": "Demo"}
        with_ex = mod_new.render("ModItems.java", "fabric", subs, True)
        without = mod_new.render("ModItems.java", "fabric", subs, False)
        self.assertIn("CRYSTAL_SHARD", with_ex)
        self.assertNotIn("CRYSTAL_SHARD", without)
        self.assertNotIn("__", without)
        self.assertEqual(mod_new.folder("recipe", "1.20.1"), "recipes")
        self.assertEqual(mod_new.folder("recipe", "1.21.1"), "recipe")
