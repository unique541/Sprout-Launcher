"""账户：离线账户与微软（Xbox Live）登录。

微软登录采用设备码（device code）流程，无需内嵌浏览器，也不会碰用户密码。
默认使用内置的公有客户端 ID（与常见第三方启动器一致），开箱即可登录；
用户也可以在设置里填入自己注册的 Azure 应用 ID 覆盖它。
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from .. import paths
from . import net

ACCOUNTS_FILE = "accounts.json"

DEVICE_CODE_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
XBL_URL = "https://user.auth.xboxlive.com/user/authenticate"
XSTS_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"
MC_LOGIN_URL = "https://api.minecraftservices.com/authentication/login_with_xbox"
MC_PROFILE_URL = "https://api.minecraftservices.com/minecraft/profile"
SCOPE = "XboxLive.signin offline_access"

# 内置公有客户端 ID：Azure 公有应用 + 允许公共客户端流，v2.0 设备码可直接使用。
# 想用自己的应用时，在「设置 - 微软登录应用 ID」里填写即可覆盖。
DEFAULT_CLIENT_ID = "a34860f1-8ed9-4d16-9dfe-28ef635b876b"


@dataclass
class Account:
    id: str
    name: str
    uuid: str
    type: str = "offline"          # offline / microsoft
    access_token: str = ""
    refresh_token: str = ""
    expires: float = 0.0
    skin: str = ""
    skin_model: str = "classic"    # classic / slim，上传皮肤时使用的模型

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_expired(self) -> bool:
        if self.type != "microsoft":
            return False
        return self.expires > 0 and time.time() > self.expires - 60


def offline_uuid(name: str) -> str:
    """离线模式 UUID：与 Java 版一致的 OfflinePlayer 名字派生。"""
    return str(uuid.uuid3(uuid.NAMESPACE_DNS, "OfflinePlayer:" + name))


def offline_account(name: str) -> Account:
    clean = (name or "Player").strip()[:16] or "Player"
    return Account(id="offline-" + clean.lower(), name=clean, uuid=offline_uuid(clean).replace("-", ""), type="offline")


class AccountStore:
    def __init__(self) -> None:
        self._file = paths.app_dir() / ACCOUNTS_FILE
        self.items: list[Account] = []
        self.active_id: str = ""
        self.load()

    def load(self) -> None:
        self.items = []
        if not self._file.exists():
            return
        try:
            raw = json.loads(self._file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for item in raw.get("accounts", []) if isinstance(raw, dict) else []:
            try:
                self.items.append(Account(**item))
            except TypeError:
                continue
        self.active_id = raw.get("active", "") if isinstance(raw, dict) else ""

    def save(self) -> None:
        try:
            self._file.write_text(
                json.dumps(
                    {"accounts": [a.to_dict() for a in self.items], "active": self.active_id},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    def active(self) -> Account:
        for a in self.items:
            if a.id == self.active_id:
                return a
        for a in self.items:
            return a
        return offline_account("Player")

    def upsert(self, account: Account) -> Account:
        for i, existing in enumerate(self.items):
            if existing.id == account.id:
                self.items[i] = account
                self.active_id = account.id
                self.save()
                return account
        self.items.append(account)
        self.active_id = account.id
        self.save()
        return account

    def set_active(self, account_id: str) -> bool:
        for a in self.items:
            if a.id == account_id:
                self.active_id = a.id
                self.save()
                return True
        return False

    def remove(self, account_id: str) -> None:
        self.items = [a for a in self.items if a.id != account_id]
        if self.active_id == account_id:
            self.active_id = self.items[0].id if self.items else ""
        self.save()


# --------------------------------------------------------------- 微软登录流程
def _post(url: str, payload: dict, timeout: float = 30.0, form: bool = False) -> dict:
    """form=True 走 application/x-www-form-urlencoded（微软 OAuth 端点强制要求），否则发 JSON。"""
    with net.client(timeout) as c:
        if form:
            r = c.post(
                url,
                data=payload,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
        else:
            r = c.post(url, json=payload, headers={"Accept": "application/json"})
        if r.status_code >= 400:
            try:
                data = r.json()
            except ValueError:
                data = {"error": r.text[:200]}
            host = url.split("//")[-1].split("/")[0]
            raise RuntimeError(f"[{host}] {data.get('error') or r.status_code}: {data.get('error_description') or data.get('error') or ''}".strip())
        return r.json()


def begin_device_login(client_id: str) -> dict:
    client_id = (client_id or "").strip() or DEFAULT_CLIENT_ID
    data = _post(DEVICE_CODE_URL, {"client_id": client_id, "scope": SCOPE}, form=True)
    return {
        "device_code": data.get("device_code", ""),
        "user_code": data.get("user_code", ""),
        "verification_uri": data.get("verification_uri") or data.get("verification_url") or "",
        "interval": int(data.get("interval") or 5),
        "expires_in": int(data.get("expires_in") or 900),
        "message": data.get("message", ""),
    }


def poll_device_login(
    client_id: str,
    device_code: str,
    interval: int = 5,
    expires_in: int = 900,
    on_wait: Callable[[int], None] | None = None,
) -> dict:
    """轮询到用户完成授权；返回 token 响应。"""
    deadline = time.time() + expires_in
    wait = max(2, interval)
    while time.time() < deadline:
        try:
            return _post(TOKEN_URL, {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": client_id,
                "device_code": device_code,
            }, form=True)
        except RuntimeError as exc:
            message = str(exc).lower()
            if "authorization_pending" in message:
                pass
            elif "slow_down" in message:
                wait += 3
            elif "expired" in message or "has expired" in message:
                raise RuntimeError("登录码已过期，请重新发起登录") from exc
            elif "declined" in message or "authorization_declined" in message:
                raise RuntimeError("用户取消了授权") from exc
            else:
                raise
        if on_wait:
            on_wait(int(max(0, deadline - time.time())))
        time.sleep(wait)
    raise RuntimeError("等待授权超时，请重试")


def microsoft_account(token_data: dict, store: AccountStore) -> Account:
    """把 OAuth token 换成 Minecraft 账户信息。"""
    access = token_data.get("access_token")
    if not access:
        raise RuntimeError("微软未返回访问令牌")
    refresh = token_data.get("refresh_token", "")
    expires_in = int(token_data.get("expires_in") or 3600)

    xbl = _post(XBL_URL, {
        "Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com", "RpsTicket": "d=" + access},
        "RelyingParty": "http://auth.xboxlive.com",
        "TokenType": "JWT",
    })
    xbl_token = xbl.get("Token", "")
    uhs = ((xbl.get("DisplayClaims") or {}).get("xui") or [{}])[0].get("uhs", "")
    if not xbl_token or not uhs:
        raise RuntimeError("Xbox Live 认证失败")

    xsts = _post(XSTS_URL, {
        "Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl_token]},
        "RelyingParty": "rp://api.minecraftservices.com/",
        "TokenType": "JWT",
    })
    xsts_token = xsts.get("Token", "")
    if not xsts_token:
        raise RuntimeError("XSTS 授权失败（该账户可能未开通 Xbox 档案）")

    mc = _post(MC_LOGIN_URL, {"identityToken": f"XBL3.0 x={uhs};{xsts_token}"})
    mc_token = mc.get("access_token", "")
    if not mc_token:
        raise RuntimeError("Minecraft 服务未返回令牌")

    profile = {}
    try:
        with net.client(30.0) as c:
            r = c.get(MC_PROFILE_URL, headers={"Authorization": "Bearer " + mc_token})
            if r.status_code == 200:
                profile = r.json()
    except Exception:
        profile = {}

    name = profile.get("name") or ""
    uid = (profile.get("id") or "").replace("-", "")
    if not uid:
        raise RuntimeError("该账户尚未拥有 Minecraft: Java 版")

    account = Account(
        id="ms-" + uid,
        name=name or "Player",
        uuid=uid,
        type="microsoft",
        access_token=mc_token,
        refresh_token=refresh,
        expires=time.time() + expires_in - 120,
        skin=((profile.get("skins") or [{}])[0].get("url") or "") if profile.get("skins") else "",
        skin_model=_skin_variant(profile),
    )
    return store.upsert(account)


def _skin_variant(profile: dict) -> str:
    """从账号资料里取当前皮肤的模型（classic / slim）。"""
    skins = profile.get("skins") or []
    if isinstance(skins, list) and skins:
        for s in skins:
            if isinstance(s, dict) and s.get("state") == "ACTIVE":
                return "slim" if str(s.get("variant")).lower() == "slim" else "classic"
        first = skins[0]
        if isinstance(first, dict):
            return "slim" if str(first.get("variant")).lower() == "slim" else "classic"
    return "classic"


def refresh_account(account: Account, client_id: str) -> Account:
    """用 refresh_token 续期；失败抛异常由上层引导重新登录。"""
    if account.type != "microsoft" or not account.refresh_token:
        return account
    client_id = (client_id or "").strip() or DEFAULT_CLIENT_ID
    data = _post(TOKEN_URL, {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": account.refresh_token,
        "scope": SCOPE,
    }, form=True)
    store = AccountStore()
    store.items = [a for a in store.items if a.id != account.id]
    fresh = microsoft_account(data, store)
    # 续期会重建 Account，把本地皮肤模型选择带过去
    if getattr(account, "skin_model", "") and account.skin_model != fresh.skin_model:
        fresh.skin_model = account.skin_model
        store.upsert(fresh)
    return fresh
