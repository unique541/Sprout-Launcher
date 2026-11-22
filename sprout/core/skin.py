"""账户皮肤：本地校验、上传到 Minecraft 皮肤服务、正面立绘预览。

Minecraft 官方皮肤接口：
    POST https://api.minecraftservices.com/minecraft/profile/skins
        表单：variant = classic | slim，file = PNG
        鉴权：Authorization: Bearer <Minecraft access token>
上传成功后游戏内皮肤立即生效（皮肤由服务端下发，与启动器本地文件无关），
本地只缓存一份皮肤贴图用于界面预览。
"""
from __future__ import annotations

import struct
import time
from pathlib import Path

from .. import paths
from . import accounts as account_core
from . import net

SKINS_API = "https://api.minecraftservices.com/minecraft/profile/skins"
PROFILE_API = "https://api.minecraftservices.com/minecraft/profile"

MODELS: tuple[str, ...] = ("classic", "slim")


class SkinError(RuntimeError):
    """皮肤相关错误，消息可直接展示给用户。"""


def normalize_model(value: str | None) -> str:
    v = (value or "").strip().lower()
    return v if v in MODELS else "classic"


def model_label(value: str | None) -> str:
    return "纤细 slim" if normalize_model(value) == "slim" else "经典 classic"


# ------------------------------------------------------------------ 本地文件
def skins_dir() -> Path:
    p = paths.cache_dir() / "skins"
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_png_size(path: str | Path) -> tuple[int, int]:
    """只读 PNG 头拿尺寸，不依赖 Pillow。"""
    try:
        with open(path, "rb") as fh:
            head = fh.read(33)
    except OSError as exc:
        raise SkinError(f"无法读取文件：{exc}") from exc
    if len(head) < 24 or not head.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SkinError("不是有效的 PNG 图片（皮肤必须是 PNG 格式）")
    if head[12:16] != b"IHDR":
        raise SkinError("PNG 结构异常，缺少 IHDR 头")
    width, height = struct.unpack(">II", head[16:24])
    return int(width), int(height)


def validate_skin(path: str | Path) -> tuple[int, int]:
    """校验皮肤尺寸：64x64（现代）/64x32（旧版）/整倍数高清皮肤。"""
    p = Path(path)
    if not p.exists():
        raise SkinError("皮肤文件不存在")
    if p.suffix.lower() != ".png":
        raise SkinError("皮肤必须是 .png 文件")
    if p.stat().st_size > 8 * 1024 * 1024:
        raise SkinError("皮肤文件过大（上限 8MB）")
    w, h = read_png_size(p)
    if w % 64 != 0 or w > 1024:
        raise SkinError(f"尺寸 {w}x{h} 不受支持：宽度需为 64 的整倍数且不超过 1024")
    if h not in (w, w // 2):
        raise SkinError(f"尺寸 {w}x{h} 不受支持：需为 {w}x{w} 或 {w}x{w // 2}")
    return w, h


def local_skin_path(account: account_core.Account | None) -> Path:
    if account is None:
        return Path()
    key = (account.uuid or account.id or "account").strip() or "account"
    return skins_dir() / f"{key}.png"


def cache_local_skin(account: account_core.Account, source: str | Path) -> Path:
    dest = local_skin_path(account)
    try:
        data = Path(source).read_bytes()
        dest.write_bytes(data)
    except OSError as exc:
        raise SkinError(f"缓存皮肤失败：{exc}") from exc
    return dest


# ------------------------------------------------------------------ 令牌与接口
def ensure_token(account: account_core.Account, client_id: str) -> account_core.Account:
    """皮肤接口需要有效的 Minecraft 令牌，过期则先续期。"""
    if account.type != "microsoft":
        raise SkinError("只有微软账户支持上传皮肤，离线账户皮肤由各自服务器决定")
    if not account.access_token:
        raise SkinError("该账户还没有 Minecraft 令牌，请重新登录微软账户")
    if not account.is_expired:
        return account
    try:
        return account_core.refresh_account(account, client_id)
    except Exception as exc:  # noqa: BLE001
        raise SkinError(f"登录状态已过期且续期失败，请重新登录微软账户（{exc}）") from exc


def fetch_profile(account: account_core.Account, client_id: str) -> dict:
    acc = ensure_token(account, client_id)
    try:
        with net.client(30.0) as c:
            r = c.get(PROFILE_API, headers={"Authorization": f"Bearer {acc.access_token}"})
    except Exception as exc:  # noqa: BLE001
        raise SkinError(f"无法连接 Minecraft 皮肤服务：{exc}") from exc
    if r.status_code == 401:
        raise SkinError("登录令牌已失效，请重新登录微软账户")
    if r.status_code >= 400:
        raise SkinError(f"读取账号资料失败（HTTP {r.status_code}）")
    try:
        return r.json() or {}
    except ValueError as exc:
        raise SkinError("皮肤服务返回内容无法解析") from exc


def _active_skin(profile: dict) -> tuple[str, str]:
    skins = profile.get("skins") or []
    if not isinstance(skins, list) or not skins:
        return "", "classic"
    cur = None
    for s in skins:
        if isinstance(s, dict) and s.get("state") == "ACTIVE":
            cur = s
            break
    cur = cur or (skins[0] if isinstance(skins[0], dict) else None)
    if not cur:
        return "", "classic"
    return str(cur.get("url") or ""), normalize_model(cur.get("variant"))


def upload_skin(
    account: account_core.Account,
    client_id: str,
    png_path: str | Path,
    model: str = "classic",
) -> dict:
    """上传皮肤并返回 {"url","model","local","profile"}。"""
    variant = normalize_model(model)
    validate_skin(png_path)
    acc = ensure_token(account, client_id)
    try:
        payload = Path(png_path).read_bytes()
    except OSError as exc:
        raise SkinError(f"读取皮肤文件失败：{exc}") from exc

    last_error = ""
    for attempt in (1, 2):
        headers = {"Authorization": f"Bearer {acc.access_token}"}
        files = {"file": (Path(png_path).name or "skin.png", payload, "image/png")}
        try:
            with net.client(60.0) as c:
                r = c.post(SKINS_API, headers=headers, files=files, data={"variant": variant})
        except Exception as exc:  # noqa: BLE001
            raise SkinError(f"上传失败，无法连接皮肤服务：{exc}") from exc

        if r.status_code in (200, 201, 204):
            break
        if r.status_code == 401 and attempt == 1:
            # 令牌失效：强制续期后重试一次
            try:
                account.expires = 0.0
                acc = account_core.refresh_account(account, client_id)
                continue
            except Exception as exc:  # noqa: BLE001
                raise SkinError(f"登录状态已失效，请重新登录微软账户（{exc}）") from exc
        if r.status_code == 400:
            detail = ""
            try:
                detail = str((r.json() or {}).get("errorMessage") or "")
            except ValueError:
                detail = ""
            raise SkinError("皮肤被服务端拒绝：" + (detail or "请确认是 64x64 的 PNG 皮肤文件"))
        if r.status_code == 401:
            raise SkinError("登录令牌已失效，请重新登录微软账户")
        if r.status_code == 403:
            raise SkinError("该账号无权修改皮肤（需拥有 Minecraft: Java 版）")
        if r.status_code == 429:
            raise SkinError("上传过于频繁，请稍后再试")
        last_error = f"HTTP {r.status_code}"
        raise SkinError(f"上传皮肤失败（{last_error}）")

    profile: dict = {}
    try:
        profile = r.json() or {}
    except ValueError:
        profile = {}
    url, remote_model = _active_skin(profile)
    local = cache_local_skin(account, png_path)
    return {
        "url": url,
        "model": remote_model or variant,
        "local": str(local),
        "profile": profile,
    }


def sync_from_service(account: account_core.Account, client_id: str) -> dict:
    """拉取账号当前皮肤：有 URL 则缓存到本地，返回 {"url","model","local"}。"""
    profile = fetch_profile(account, client_id)
    url, model = _active_skin(profile)
    if not url:
        return {"url": "", "model": model, "local": ""}
    dest = local_skin_path(account)
    if dest.exists() and dest.stat().st_size > 0 and dest.stat().st_mtime > time.time() - 600:
        return {"url": url, "model": model, "local": str(dest)}
    try:
        with net.client(30.0) as c:
            r = c.get(url)
            r.raise_for_status()
            data = r.content
    except Exception as exc:  # noqa: BLE001
        raise SkinError(f"下载皮肤贴图失败：{exc}") from exc
    try:
        dest.write_bytes(data)
    except OSError as exc:
        raise SkinError(f"缓存皮肤失败：{exc}") from exc
    return {"url": url, "model": model, "local": str(dest)}


# ------------------------------------------------------------------ 预览渲染
# 64x64 皮肤贴图各面的坐标（单位：皮肤像素格）
_HEAD_FRONT = (8, 8, 8, 8)
_HAT_FRONT = (40, 8, 8, 8)
_BODY_FRONT = (20, 20, 8, 12)
_JACKET_FRONT = (20, 36, 8, 12)
_ARM_R_FRONT = (44, 20, 4, 12)
_ARM_R_OVER = (44, 36, 4, 12)
_ARM_L_FRONT = (36, 52, 4, 12)
_ARM_L_OVER = (52, 52, 4, 12)
_LEG_R_FRONT = (4, 20, 4, 12)
_LEG_R_OVER = (4, 36, 4, 12)
_LEG_L_FRONT = (20, 52, 4, 12)
_LEG_L_OVER = (4, 52, 4, 12)


def preview_path(account: account_core.Account | None) -> Path:
    key = "none" if account is None else (account.uuid or account.id or "account")
    return skins_dir() / f"preview_{key}.png"


def render_preview(skin_png: str | Path, model: str = "classic", out_path: str | Path | None = None) -> str:
    """把皮肤贴图渲染成正视立绘（含外层叠加），返回图片路径。"""
    src = Path(skin_png)
    if not src.exists():
        return ""
    try:
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QColor, QImage, QPainter
    except Exception:  # noqa: BLE001
        return ""

    img = QImage(str(src))
    if img.isNull():
        return ""

    width, height = img.width(), img.height()
    if width < 64:
        return str(src)
    factor = max(1, width // 64)
    slim = normalize_model(model) == "slim"
    arm = 3 if slim else 4
    scale = 6

    canvas = QImage((2 * arm + 8) * scale, 32 * scale, QImage.Format_ARGB32)
    canvas.fill(QColor(0, 0, 0, 0))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
    painter.setRenderHint(QPainter.Antialiasing, False)

    def blit(rect_units, dx_units, dy_units, d_w=None, d_h=None) -> None:
        ux, uy, uw, uh = rect_units
        sx, sy = ux * factor, uy * factor
        sw, sh = uw * factor, uh * factor
        if sx < 0 or sy < 0 or sx + sw > width or sy + sh > height:
            return
        part = img.copy(QRect(sx, sy, sw, sh))
        if part.isNull():
            return
        painter.drawImage(
            QRect(dx_units * scale, dy_units * scale,
                  (d_w or uw) * scale, (d_h or uh) * scale),
            part,
        )

    # 腿 -> 身体 -> 手臂 -> 头 -> 外层
    blit(_LEG_R_FRONT, arm, 20)
    blit(_LEG_L_FRONT, arm + 4, 20)
    blit(_BODY_FRONT, arm, 8)
    blit(_ARM_R_FRONT, 0, 8, arm, 12)
    blit(_ARM_L_FRONT, arm + 8, 8, arm, 12)
    blit(_HEAD_FRONT, arm, 0)
    blit(_LEG_R_OVER, arm, 20)
    blit(_LEG_L_OVER, arm + 4, 20)
    blit(_JACKET_FRONT, arm, 8)
    blit(_ARM_R_OVER, 0, 8, arm, 12)
    blit(_ARM_L_OVER, arm + 8, 8, arm, 12)
    blit(_HAT_FRONT, arm, 0)
    painter.end()

    out = Path(out_path) if out_path else skins_dir() / f"preview_{src.stem}.png"
    if not canvas.save(str(out), "PNG"):
        # 极少数情况下 Qt 无图像后端，退回展示原始贴图
        return str(src)
    return str(out)


def preview_for_account(account: account_core.Account | None, model: str | None = None) -> str:
    """按账号缓存绘制预览图；没有本地皮肤时返回空串。"""
    if account is None:
        return ""
    src = local_skin_path(account)
    if not src.exists() or src.stat().st_size == 0:
        return ""
    variant = normalize_model(model if model is not None else getattr(account, "skin_model", "classic"))
    return render_preview(src, variant, preview_path(account))
