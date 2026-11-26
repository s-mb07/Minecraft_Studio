"""Offline tests for the reference-study scripts (mc-mod-study). No decompiler or network needed."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins" / "minecraft-studio" / "scripts"))

import _png  # noqa: E402
import _ref  # noqa: E402
import asset_study  # noqa: E402
import gui_study  # noqa: E402
import license_scan  # noqa: E402
import mechanic_trace  # noqa: E402
import mod_inventory  # noqa: E402
import mod_reference  # noqa: E402
import reuse_apply  # noqa: E402
import similarity_report  # noqa: E402

MACHINE = '''package com.ref.energy;
import net.minecraft.world.level.block.entity.BlockEntity;
public class CableBlockEntity extends BlockEntity {
    private int energyStored;
    private int capacity = 1000;
    public void tick() { pushEnergy(); }
    private void pushEnergy() { EnergyNetwork.get(this).transfer(energyStored); }
    protected void saveAdditional(CompoundTag tag) { tag.putInt("Energy", energyStored); }
}
'''
NETWORK = '''package com.ref.energy;
public class EnergyNetwork {
    public static EnergyNetwork get(Object o) { return new EnergyNetwork(); }
    public void transfer(int amount) { }
}
'''
SCREEN = '''package com.ref.gui;
public class SmelterScreen extends AbstractContainerScreen<SmelterMenu> {
    public SmelterScreen() { this.imageWidth = 176; this.imageHeight = 166; }
    protected void renderBg(GuiGraphics g) { g.blit(TEX, x + 79, y + 34, 176, 14, 24, 17); g.blit(TEX, x + 10, y + 10, 176, 31, 14, 42); }
    public boolean mouseClicked(double x, double y, int b) { return false; }
}
'''
MENU = '''package com.ref.gui;
public class SmelterMenu extends AbstractContainerMenu {
    void slots() {
        addSlot(new Slot(container, 0, 56, 17));
        addSlot(new Slot(container, 1, 56, 53));
        addSlot(new FurnaceResultSlot(player, container, 2, 116, 35));
        for (int i = 0; i < 9; ++i) addSlot(new Slot(inv, i, 8 + i * 18, 142));
    }
}
'''
MIT = "MIT License\n\nPermission is hereby granted, free of charge, to any person obtaining a copy..."


def png(path: Path, color=(200, 40, 40, 255)):
    img = _png.Image(16, 16)
    for y in range(16):
        for x in range(16):
            img.set(x, y, color if (x + y) % 3 else (color[0] // 2, color[1] // 2, color[2] // 2, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def make_jar(tmp: Path, licence_text: str | None = MIT, meta_licence: str = "MIT") -> Path:
    jar = tmp / "refmod-1.0.jar"
    tex = png(tmp / "_t.png")
    with zipfile.ZipFile(jar, "w") as z:
        z.writestr("fabric.mod.json", json.dumps({"id": "refmod", "version": "1.0", "license": meta_licence,
                                                   "depends": {"minecraft": "~1.21.1"},
                                                   "entrypoints": {"main": ["com.ref.RefMod"]}, "mixins": ["refmod.mixins.json"]}))
        if licence_text:
            z.writestr("LICENSE", licence_text)
        z.writestr("com/ref/energy/CableBlockEntity.class", b"\xca\xfe\xba\xbe")
        z.writestr("com/ref/RefMod.class", b"\xca\xfe\xba\xbe")
        z.writestr("assets/refmod/models/block/cable.json", json.dumps({"parent": "block/block", "textures": {"0": "refmod:block/cable"},
                   "elements": [{"from": [6, 6, 0], "to": [10, 10, 16], "faces": {"north": {"uv": [0, 0, 4, 4], "texture": "#0"}}}]}))
        z.write(tex, "assets/refmod/textures/block/cable.png")
        z.writestr("assets/refmod/lang/en_us.json", json.dumps({"block.refmod.cable": "Cable", "item.refmod.wrench": "Wrench"}))
        z.writestr("assets/refmod/sounds.json", json.dumps({"cable.hum": {"sounds": ["refmod:hum"]}}))
        z.writestr("data/refmod/recipe/cable.json", "{}")
        z.writestr("../evil.txt", "zip slip")
    return jar


def add(root: Path, src: Path, rid="ref"):
    class A:  # argparse stand-in
        source, id, loader, mc, no_decompile = str(src), rid, None, None, True
    A.root = str(root)
    with redirect_stdout(io.StringIO()) as out:
        mod_reference.add(A)
    return out.getvalue()


def fake_decompile(ref: Path):
    d = ref / "decompiled/java/com/ref"
    (d / "energy").mkdir(parents=True, exist_ok=True); (d / "gui").mkdir(parents=True, exist_ok=True)
    (d / "energy/CableBlockEntity.java").write_text(MACHINE)
    (d / "energy/EnergyNetwork.java").write_text(NETWORK)
    (d / "gui/SmelterScreen.java").write_text(SCREEN)
    (d / "gui/SmelterMenu.java").write_text(MENU)
    _ref.build_index(ref)


def make_target(root: Path):
    res = root / "src/main/resources"
    (res).mkdir(parents=True)
    (res / "fabric.mod.json").write_text(json.dumps({"id": "mymod"}))
    j = root / "src/main/java/com/me/mymod"; j.mkdir(parents=True)
    (j / "MyMod.java").write_text("package com.me.mymod;\npublic class MyMod {}\n")


class TestStudy(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "mymod"; make_target(self.root)
        out = add(self.root, make_jar(self.tmp))
        self.ref = _ref.ref_dir(self.root, "ref")
        self.assertIn("ADDED ref", out)

    def test_add_tree_and_zip_slip(self):
        for p in ("meta.json", "original.jar", "extracted/classes/com/ref/RefMod.class",
                  "extracted/assets/refmod/models/block/cable.json", "extracted/meta/fabric.mod.json", "licence.json"):
            self.assertTrue((self.ref / p).exists(), p)
        self.assertFalse((self.ref / "evil.txt").exists())
        self.assertFalse((self.ref.parent / "evil.txt").exists())

    def test_inventory(self):
        inv = mod_inventory.inventory(self.ref)
        self.assertEqual((inv["loader"], inv["modid"]), ("fabric", "refmod"))
        self.assertEqual(inv["registries"]["blocks"], 1)
        self.assertEqual(inv["assets"]["models"], 1)
        self.assertEqual(inv["data"]["recipe"], 1)
        self.assertIn("refmod.mixins.json", inv["mixin_configs"])

    def test_licence_variants(self):
        self.assertEqual(license_scan.scan(self.ref)["licence"], "MIT")
        for text, meta, want, status in [("Apache License\n Version 2.0, January 2004", "Apache-2.0", "Apache-2.0", "known"),
                                         ("CC0 1.0 Universal", "CC0-1.0", "CC0-1.0", "known"),
                                         (None, "${license}", "unknown", "unknown"),
                                         (MIT, "All Rights Reserved", None, "mixed")]:
            t = Path(tempfile.mkdtemp())
            r = make_target(t / "m") or t / "m"
            add(r, make_jar(t, text, meta), "x")
            res = license_scan.scan(_ref.ref_dir(r, "x"))
            self.assertEqual(res["status"], status, (text, meta, res))
            if want:
                self.assertEqual(res["licence"], want)

    def test_trace(self):
        fake_decompile(self.ref)
        r = mechanic_trace.trace(self.ref, "how does its energy cable work?")
        self.assertTrue(r["classes"][0].endswith("CableBlockEntity extends BlockEntity"))
        self.assertIn("CableBlockEntity.tick()", r["entry"])
        self.assertIn("CableBlockEntity -> EnergyNetwork", r["flow"])
        self.assertIn("Energy", r["persisted"])
        self.assertTrue(any("CableBlockEntity.java" in f for f in r["read"]))

    def test_asset_and_gui_study(self):
        m = asset_study.study(self.ref, "model")
        self.assertEqual(m["items"][0]["elements"], 1)
        t = asset_study.study(self.ref, "texture")
        self.assertEqual(t["items"][0]["size"], "16x16")
        self.assertEqual(asset_study.study(self.ref, "sound")["events"], 1)
        fake_decompile(self.ref)
        g = gui_study.study(self.ref, "SmelterScreen")
        self.assertEqual(g["size"], [176, 166])
        self.assertEqual(len(g["slots"]), 3)
        self.assertTrue(g["player_inventory"])
        self.assertTrue(any("horizontal" in x for x in g["regions"]))
        self.assertTrue(g["original_design"])

    def test_reuse_and_similarity(self):
        tgt = "src/main/resources/assets/mymod/textures/block/wire.png"
        e = reuse_apply.apply(self.root, "ref", "textures/block/cable.png", None, tgt, "recolour", color="#3080ff")
        self.assertEqual(e["licence"], "MIT")
        img = _png.load(self.root / tgt)
        self.assertGreater(img.get(1, 0)[2], img.get(1, 0)[0])  # now blue-ish
        reuse_apply.apply(self.root, "ref", "models/block/cable.json", None,
                          "src/main/resources/assets/mymod/models/block/wire.json", "edit_model")
        model = json.loads((self.root / "src/main/resources/assets/mymod/models/block/wire.json").read_text())
        self.assertEqual(model["textures"]["0"], "mymod:block/cable")
        # second write to the same target -> backup
        e2 = reuse_apply.apply(self.root, "ref", "textures/block/cable.png", None, tgt, "copy")
        self.assertTrue(e2["backup"] and (self.root / e2["backup"]).exists())
        fake_decompile(self.ref)
        reuse_apply.apply(self.root, "ref", None, "EnergyNetwork",
                          "src/main/java/com/me/mymod/PowerGrid.java", "adapt_code")
        code = (self.root / "src/main/java/com/me/mymod/PowerGrid.java").read_text()
        self.assertIn("package com.me.mymod;", code)
        self.assertIn("class PowerGrid", code)
        self.assertIn("licence: MIT", code)
        log = _ref.read_log(self.root / "studio/reuse-log.jsonl")
        self.assertEqual(len(log), 4)
        rep = similarity_report.report(self.root, "ref")
        self.assertIn(rep["similarity"], ("medium", "high"))
        self.assertEqual(rep["reused"], 4)
        self.assertTrue(rep["textures_recolour"] or rep["textures_identical"])
        self.assertEqual(rep["provenance"], "studio/reuse-log.jsonl")

    def test_bbmodel_convert(self):
        bb = {"meta": {"model_format": "java_block"}, "textures": [{"name": "gear.png"}],
              "elements": [{"type": "cube", "from": [0, 0, 0], "to": [16, 4, 16], "rotation": [0, 45, 0], "origin": [8, 8, 8],
                            "faces": {"up": {"uv": [0, 0, 16, 16], "texture": 0}}}]}
        j = reuse_apply.bbmodel_to_java(bb, "mymod", "gear")
        self.assertEqual(j["textures"]["0"], "mymod:block/gear")
        self.assertEqual(j["elements"][0]["rotation"], {"angle": 45, "axis": "y", "origin": [8, 8, 8]})
        self.assertEqual(j["elements"][0]["faces"]["up"]["texture"], "#0")


if __name__ == "__main__":
    unittest.main()
