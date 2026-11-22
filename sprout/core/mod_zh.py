"""模组中文译名表。

社区（MCBBS / 中文 Wiki / 各大整合包汉化）公认的译名，用于在模组列表里显示
中文名，英文原名仍作为副标题保留。

匹配方式：先把候选文本归一化（小写、去掉空格与标点、去掉常见后缀），
再做「精确匹配 → 前缀/包含匹配」两级查找，避免 Sodium Extra 被误判成 Sodium。
"""

from __future__ import annotations

import re

# (别名元组, 中文译名)；别名会做归一化比较
_ENTRIES: tuple[tuple[tuple[str, ...], str], ...] = (
    # ---------------------------------------------------- 性能 / 优化类
    (("sodium",), "钠优化"),
    (("sodiumextra",), "钠优化扩展"),
    (("lithium",), "锂优化"),
    (("phosphor",), "磷光优化"),
    (("starlight",), "星光优化"),
    (("krypton",), "氪网络优化"),
    (("ferritecore",), "铁氧核心（内存优化）"),
    (("indium",), "铟（渲染兼容）"),
    (("embeddium",), "内嵌优化（Embeddium）"),
    (("rubidium",), "铷优化"),
    (("modernfix", "modernfixmod"), "现代修复"),
    (("entityculling",), "实体剔除"),
    (("memoryleakfix",), "内存泄漏修复"),
    (("smoothboot", "smoothbootfabric"), "平滑启动"),
    (("lazydfu",), "懒加载 DFU"),
    (("c2me", "c2mefabric"), "C2ME 并发区块"),
    (("noisium",), "Noisium 噪声优化"),
    (("nvidium",), "Nvidium 渲染加速"),
    (("immediatelyfast",), "即时渲染加速"),
    (("fastload", "fastloadfabric"), "快速载入"),
    (("dynamicfps",), "动态帧率"),
    (("betterf3",), "更好的 F3 调试屏"),
    (("mousetweaks",), "鼠标调整"),
    (("notenoughanimations",), "更多动画"),
    (("lambdabettergrass",), "更好的草"),
    (("fallingleaves",), "落叶特效"),
    (("effective", "effectiveslides"), "环境特效"),
    (("presencefootsteps",), "真实脚步声"),
    (("soundphysicsremastered", "soundphysics"), "声音物理重制"),
    (("ambientsounds",), "环境音效"),
    # ---------------------------------------------------- 光影 / 渲染
    (("iris", "irisshaders"), "虹彩光影（Iris）"),
    (("oculus",), "Oculus 光影"),
    (("optifine",), "高清修复（OptiFine）"),
    (("shaders",), "光影"),
    # ---------------------------------------------------- 前置 / 基础库
    (("fabricapi",), "Fabric API 基础库"),
    (("quiltedfabricapi", "qsl", "quiltstandardlibraries"), "Quilt 标准库"),
    (("fabriclanguagekotlin",), "Fabric Kotlin 前置"),
    (("architectury", "architecturyapi"), "Architectury 前置库"),
    (("clothconfig", "clothconfigapi"), "布制配置库"),
    (("geckolib",), "GeckoLib 动画库"),
    (("balm",), "Balm 前置库"),
    (("placebo",), "Placebo 前置库"),
    (("puzzleslib",), "Puzzles 前置库"),
    (("kotlinforforge",), "Kotlin 前置库"),
    (("yungsapi", "yungsapi1"), "YUNG 前置库"),
    (("ftblibrary",), "FTB 前置库"),
    (("curios", "curiosapi"), "饰品栏（Curios）"),
    (("trinkets",), "饰品栏（Trinkets）"),
    (("patchouli",), "帕秋莉手册"),
    (("modmenu",), "模组菜单"),
    (("catalogue",), "模组目录"),
    (("configured",), "配置界面"),
    (("moonlight", "moonlightlib"), "Moonlight 前置库"),
    # ---------------------------------------------------- 物品 / 界面
    (("jei", "justenoughitems", "justenoughitemsjei"), "JEI 物品管理器"),
    (("rei", "roughlyenoughitems"), "REI 物品管理器"),
    (("emi",), "EMI 物品管理器"),
    (("wthit",), "WTHIT 方块信息"),
    (("hwyla",), "HWYLA 方块信息"),
    (("jade",), "Jade 方块信息"),
    (("theoneprobe",), "检测器（TOP）"),
    (("appleskin",), "苹果皮（饱食度信息）"),
    (("journeymap",), "旅行地图"),
    (("xaerosminimap",), "Xaero 小地图"),
    (("xaerosworldmap",), "Xaero 世界地图"),
    (("betteradvancements",), "更好的进度"),
    (("enchantmentdescriptions",), "附魔描述"),
    (("controlling",), "按键冲突查看"),
    # ---------------------------------------------------- 科技 / 工业
    (("create",), "机械动力"),
    (("createaddition",), "机械动力：附加"),
    (("createcraftsadditions",), "机械动力：合成附加"),
    (("ae2", "appliedenergistics2", "appliedenergistics"), "应用能源 2（AE2）"),
    (("mekanism",), "通用机械"),
    (("immersiveengineering",), "沉浸工程"),
    (("thermalexpansion",), "热力膨胀"),
    (("thermalfoundation",), "热力基础"),
    (("refinedstorage", "refinedstorage2"), "精致存储"),
    (("storagedrawers",), "抽屉（储物抽屉）"),
    (("tinkersconstruct",), "匠魂"),
    (("industrialcraft", "industrialcraft2", "ic2"), "工业时代 2"),
    (("buildcraft",), "建筑（BuildCraft）"),
    (("railcraft",), "铁路（RailCraft）"),
    (("forestry",), "林业"),
    (("enderio",), "末影接口"),
    (("projecte",), "等价交换（ProjectE）"),
    (("icbm",), "ICBM 导弹"),
    (("computercraft", "cc-tweaked", "cctweaked"), "电脑（ComputerCraft）"),
    (("opencomputers",), "开放式电脑"),
    (("nuclearcraft",), "核电工艺"),
    (("bigreactors", "extremereactors"), "大型反应堆"),
    (("galacticraft",), "星系（Galacticraft）"),
    (("ae2wtlib",), "AE2 无线终端"),
    (("pipez",), "管道（Pipez）"),
    (("mekanismgenerators",), "通用机械：发电机"),
    # ---------------------------------------------------- 魔法 / 冒险
    (("botania",), "植物魔法"),
    (("thaumcraft",), "神秘时代"),
    (("bloodmagic",), "血魔法"),
    (("arsnouveau",), "新生魔艺"),
    (("draconicevolution",), "龙之研究"),
    (("twilightforest", "twilightforestmod"), "暮色森林"),
    (("alexsmobs", "alexmobs"), "Alex 的生物"),
    (("iceandfire",), "冰火传说"),
    (("epicfight", "epicfightmod"), "史诗战斗"),
    (("apotheosis",), "神化"),
    (("mysticalagriculture",), "神秘农业"),
    (("pamharvestcraft", "harvestcraft"), "潘马斯农场"),
    (("waystones",), "传送石碑"),
    (("corpse",), "尸体（死亡物品保管）"),
    (("tombstone", "corailtombstone"), "墓碑"),
    (("comforts",), "舒适睡袋"),
    (("carryon",), "搬运（Carry On）"),
    (("sophisticatedbackpacks",), "精致背包"),
    (("travelersbackpack",), "旅行者背包"),
    (("ironchest", "ironchests"), "铁箱"),
    (("sereneseasons",), "静谧四季"),
    (("biomesoplenty",), "超多生物群系"),
    (("oh-the-biomes-youll-go", "biomesyougo", "byg"), "你将去的生物群系"),
    (("terralith",), "Terralith 地形"),
    (("tectonic",), "地形构造（Tectonic）"),
    (("yungsbetterdungeons",), "YUNG 更好的地牢"),
    (("lootr",), "战利品（Lootr）"),
    (("pehkui",), "体型调整（Pehkui）"),
    (("paraglider",), "滑翔伞"),
    (("farmersdelight",), "农夫乐事"),
    (("ftbquests",), "FTB 任务"),
    (("waypoint",), "路径点"),
)

# 归一化后 → 中文名
_INDEX: dict[str, str] = {}
# 归一化键长度（用于包含匹配时按长度降序，优先长键）
_KEYS: list[str] = []

_SUFFIXES = (
    "fabric", "forge", "neoforge", "quilt", "mod", "port", "unofficial",
    "reforged", "续作", "重制",
)


def normalize(text: str) -> str:
    """归一化：小写、只保留字母数字与中文，去掉常见平台后缀。"""
    raw = str(text or "").strip().lower()
    if not raw:
        return ""
    raw = re.sub(r"\.(jar|zip|litemod|disabled)$", "", raw)
    norm = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", raw)
    for suffix in _SUFFIXES:
        if len(norm) > len(suffix) + 3 and norm.endswith(suffix):
            norm = norm[: -len(suffix)]
            break
    return norm


def _build_index() -> None:
    if _INDEX:
        return
    for aliases, name in _ENTRIES:
        for alias in aliases:
            key = normalize(alias)
            if key:
                _INDEX.setdefault(key, name)
    _KEYS.extend(sorted(_INDEX.keys(), key=len, reverse=True))


def _word_bounded(key: str, cand: str) -> bool:
    """cand 是否以「词边界」形式出现在 key 中。

    边界 = 非英文字母（数字、中文、串首/串尾都算边界）。
    这样 "Sodium 0.9.3-beta" → "sodium093beta" 能命中 "sodium"，
    而 "Sodium Extra" → "sodiumextra" 不会把 "sodium" 当成独立词。
    """
    start = 0
    while True:
        pos = key.find(cand, start)
        if pos < 0:
            return False
        before = key[pos - 1] if pos > 0 else ""
        after = key[pos + len(cand)] if pos + len(cand) < len(key) else ""
        if not (before.isalpha() and before.isascii()):
            if not (after.isalpha() and after.isascii()):
                return True
        start = pos + 1


def lookup(text: str) -> str:
    """单个文本查译名；找不到返回空串。"""
    _build_index()
    key = normalize(text)
    if not key:
        return ""
    hit = _INDEX.get(key)
    if hit:
        return hit
    # 包含匹配兜底：按键长度降序（长键优先），并要求词边界，避免误判
    for cand in _KEYS:
        if len(cand) < 3:
            continue
        if cand in key and _word_bounded(key, cand):
            return _INDEX[cand]
    return ""


def zh_name(*candidates: str) -> str:
    """按优先级依次尝试多个候选（slug / 英文名 / 文件名），返回首个命中译名。"""
    for cand in candidates:
        if not cand:
            continue
        hit = lookup(cand)
        if hit:
            return hit
    return ""


def display_title(original: str, slug: str = "") -> tuple[str, str]:
    """返回 (主标题, 副标题)：有译名时主标题为中文、副标题为英文原名。"""
    original = str(original or "").strip()
    zh = zh_name(slug, original)
    if zh and zh != original:
        return zh, original
    return original, ""


__all__ = ["normalize", "lookup", "zh_name", "display_title"]
