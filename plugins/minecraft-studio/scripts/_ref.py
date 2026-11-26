"""Shared helpers for reference study (mc-mod-study): paths, meta, provenance log, Java index.

A reference lives in <root>/studio/references/<id>/ :
  meta.json  original.jar  extracted/{classes,assets,data,meta}  source/  decompiled/java/
  analysis/{index.json,inventory.json}  licence.json  reuse-log.jsonl
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

from _common import load_json, save_json

STOP = set("the a an of to in on for and or is it its how does do this that with what when which why from my mod".split())


def ref_dir(root: Path, ref_id: str) -> Path:
    return Path(root) / "studio" / "references" / ref_id


def now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def meta(ref: Path) -> dict:
    p = ref / "meta.json"
    return load_json(p) if p.exists() else {}


def save_meta(ref: Path, data: dict):
    save_json(ref / "meta.json", data)


def need(root: Path, ref_id: str) -> Path:
    ref = ref_dir(root, ref_id)
    if not (ref / "meta.json").exists():
        raise SystemExit(f"error: no reference '{ref_id}' in {ref.parent} (run mod_reference.py add first)")
    return ref


def res_roots(ref: Path) -> list[Path]:
    """Folders that contain assets/ and/or data/ (jar extraction or every src/*/resources of a source tree)."""
    out = []
    if (ref / "extracted").exists():
        out.append(ref / "extracted")
    src = ref / "source"
    if src.exists():
        for p in src.rglob("resources"):
            if p.is_dir() and ((p / "assets").exists() or (p / "data").exists()) and "build" not in p.parts:
                out.append(p)
    return out


def java_files(ref: Path) -> list[Path]:
    files = []
    if (ref / "decompiled/java").exists():
        files += sorted((ref / "decompiled/java").rglob("*.java"))
    if (ref / "source").exists():
        files += sorted(p for p in (ref / "source").rglob("*.java") if "build" not in p.parts)
    return files


def meta_files(ref: Path) -> list[Path]:
    """fabric.mod.json, (neo)forge mods.toml, mixin configs, licence files."""
    out = []
    for base in [ref / "extracted/meta"] + res_roots(ref) + [ref / "source"]:
        if not base.exists():
            continue
        depth = base.glob("*") if base.name == "source" else base.rglob("*")
        for p in depth:
            if p.is_file() and (p.name in ("fabric.mod.json", "mods.toml", "neoforge.mods.toml", "quilt.mod.json")
                                or p.name.endswith(".mixins.json") or re.match(r"(LICEN[CS]E|COPYING|NOTICE)", p.name, re.I)):
                out.append(p)
        if base.name == "source":  # one level down for archive roots like repo-main/
            for d in base.iterdir():
                if d.is_dir():
                    out += [p for p in d.iterdir() if p.is_file() and re.match(r"(LICEN[CS]E|COPYING|NOTICE)", p.name, re.I)]
    return out


def log_reuse(root: Path, ref_id: str, entry: dict):
    entry = {"reference": ref_id, **entry, "timestamp": now()}
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    for p in (ref_dir(root, ref_id) / "reuse-log.jsonl", Path(root) / "studio" / "reuse-log.jsonl"):
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8", newline="\n") as f:
            f.write(line)


def read_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def words(text: str) -> list[str]:
    """camelCase / snake / spaces -> lowercase tokens."""
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return [w for w in re.split(r"[^a-zA-Z0-9]+", text.lower()) if w]


# ---------------------------------------------------------------- Java index (regex, no parser)
RX_PKG = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.M)
RX_CLASS = re.compile(r"\b(class|interface|enum|record)\s+(\w+)(?:<[^{]*?>)?(?:\([^)]*\))?"
                      r"(?:\s+extends\s+([\w.<>, ?]+?))?(?:\s+implements\s+([\w.<>, ?]+?))?\s*\{")
RX_METHOD = re.compile(r"^[ \t]*(?:@\w+(?:\([^)]*\))?\s+)*(?:(?:public|protected|private|static|final|synchronized|abstract|default)\s+)*"
                       r"(?:<[^>]+>\s+)?[\w<>\[\], .?]+?\s+(\w+)\s*\([^;{)]*\)\s*(?:throws [\w., ]+)?\s*\{", re.M)
RX_FIELD = re.compile(r"^[ \t]*(?:(?:public|protected|private|static|final|volatile|transient)\s+)+[\w<>\[\], .?]+?\s+(\w+)\s*(?:=|;)", re.M)
RX_STR = re.compile(r'"([a-z0-9_.:/-]{3,64})"')
RX_NBT = re.compile(r'\.(?:put|get|contains)(?:Int|Long|Float|Double|Boolean|String|Byte|Short|Compound|List|UUID|IntArray)?\(\s*"(\w+)"'
                    r'|fieldOf\(\s*"(\w+)"')
RX_MIXIN = re.compile(r"@Mixin\(\s*(?:value\s*=\s*)?\{?\s*([\w.]+)\.class")
RX_SUB = re.compile(r"@SubscribeEvent[\s\S]{0,200}?\(\s*(?:final\s+)?([\w.]+)\s+\w+\s*\)")
RX_FEV = re.compile(r"\b(\w+Events?(?:\.\w+)?)\.register\(")
RX_CAP = re.compile(r"\b[A-Z]\w+\b")
# Stable Fabric intermediary names of common Minecraft classes (production Fabric jars use these).
INTERMEDIARY = {"class_2248": "Block", "class_1792": "Item", "class_1747": "BlockItem", "class_2586": "BlockEntity",
                "class_1297": "Entity", "class_1299": "EntityType", "class_2487": "NbtCompound", "class_2960": "Identifier",
                "class_2378": "Registry", "class_7923": "Registries", "class_1937": "World", "class_1657": "PlayerEntity",
                "class_2338": "BlockPos", "class_2680": "BlockState", "class_437": "Screen", "class_465": "HandledScreen",
                "class_1703": "ScreenHandler", "class_3414": "SoundEvent", "class_2396": "ParticleType",
                "class_1799": "ItemStack"}
KEYWORDS = {"if", "for", "while", "switch", "catch", "return", "new", "else", "synchronized", "try", "super", "this"}
SYSTEMS = {
    "items": r"extends\s+\w*Item\b|Registries\.ITEM|ITEMS\.register|DeferredRegister\.Items",
    "blocks": r"extends\s+\w*Block\b|Registries\.BLOCK|BLOCKS\.register|DeferredRegister\.Blocks",
    "block_entities": r"BlockEntity\b",
    "entities": r"extends\s+\w*(?:Entity|Mob|Monster|Animal)\b|EntityType\.Builder",
    "network": r"CustomPacketPayload|StreamCodec|PayloadRegistrar|ServerPlayNetworking|PacketByteBuf",
    "config": r"ModConfigSpec|ForgeConfigSpec|ConfigSpec|AutoConfig|@Config",
    "worldgen": r"\b(?:Feature|PlacedFeature|ConfiguredFeature|BiomeModifier|Structure)\b",
    "gui": r"extends\s+\w*(?:Screen|ContainerMenu|ScreenHandler)\b|AbstractContainerScreen",
    "render": r"\b(?:BlockEntityRenderer|EntityRenderer|PoseStack|MatrixStack|RenderType|VertexConsumer)\b",
    "energy": r"(?i)\benergy\b|IEnergyStorage|EnergyStorage",
    "recipes": r"\bRecipe(?:Type|Serializer)?\b",
    "sound": r"SoundEvent\b",
    "particles": r"ParticleType|addParticle|ParticleOptions",
}


def index_file(path: Path, base: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    inter = bool(re.search(r"\b(?:class|method|field)_\d{3,}\b", text))
    if inter:
        text = re.sub(r"\bclass_\d+\b", lambda x: INTERMEDIARY.get(x.group(0), x.group(0)), text)
    m = RX_CLASS.search(text)
    if not m:
        return None
    pkg = RX_PKG.search(text)
    methods = [x for x in dict.fromkeys(RX_METHOD.findall(text)) if x not in KEYWORDS]
    nbt = [a or b for a, b in RX_NBT.findall(text)]
    return {
        "name": m.group(2), "kind": m.group(1), "pkg": pkg.group(1) if pkg else "",
        "file": path.relative_to(base).as_posix(),
        "extends": (m.group(3) or "").strip(), "implements": (m.group(4) or "").strip(),
        "annotations": sorted(set(re.findall(r"@([A-Z]\w+)", text)))[:20],
        "methods": methods[:60], "fields": list(dict.fromkeys(RX_FIELD.findall(text)))[:40],
        "strings": list(dict.fromkeys(RX_STR.findall(text)))[:40],
        "nbt": list(dict.fromkeys(nbt))[:30],
        "mixin": RX_MIXIN.findall(text),
        "events": list(dict.fromkeys(RX_SUB.findall(text) + RX_FEV.findall(text)))[:20],
        "packet": bool(re.search(SYSTEMS["network"], text)),
        "systems": [k for k, rx in SYSTEMS.items() if re.search(rx, text)],
        "intermediary": inter,
        "_caps": set(RX_CAP.findall(text)),
        "lines": text.count("\n") + 1,
    }


def build_index(ref: Path) -> dict:
    classes = [c for c in (index_file(p, ref) for p in java_files(ref)) if c]
    names = {c["name"] for c in classes}
    for c in classes:
        c["refs"] = sorted((c.pop("_caps") & names) - {c["name"]})[:30]
    if not classes and (ref / "extracted/classes").exists():  # no decompiler: names only
        for p in (ref / "extracted/classes").rglob("*.class"):
            if "$" not in p.name:
                rel = p.relative_to(ref / "extracted/classes")
                classes.append({"name": p.stem, "kind": "class", "pkg": ".".join(rel.parts[:-1]),
                                "file": p.relative_to(ref).as_posix(), "bytecode_only": True,
                                "methods": [], "fields": [], "strings": [], "nbt": [], "mixin": [], "events": [],
                                "refs": [], "systems": [], "annotations": [], "packet": False, "intermediary": False})
    idx = {"generated": now(), "classes": classes,
           "systems": {k: sum(1 for c in classes if k in c["systems"]) for k in SYSTEMS},
           "decompiled": any(not c.get("bytecode_only") for c in classes)}
    save_json(ref / "analysis/index.json", idx)
    return idx


def load_index(ref: Path) -> dict:
    p = ref / "analysis/index.json"
    return load_json(p) if p.exists() else build_index(ref)
