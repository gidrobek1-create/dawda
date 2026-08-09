import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _get_int_list(name: str) -> list[int]:
    raw = os.getenv(name, "")
    result = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            result.append(int(part))
    return result


@dataclass
class Config:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    database_url: str = os.getenv("DATABASE_URL", "")

    webhook_mode: bool = _get_bool("WEBHOOK_MODE", False)
    webhook_base_url: str = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "change-me")
    port: int = int(os.getenv("PORT", "8080"))

    super_admin_ids: list[int] = field(default_factory=lambda: _get_int_list("SUPER_ADMIN_IDS"))

    @property
    def webhook_path(self) -> str:
        return f"/webhook/{self.webhook_secret}"

    @property
    def webhook_url(self) -> str:
        return f"{self.webhook_base_url}{self.webhook_path}"

    def validate(self) -> None:
        missing = []
        if not self.bot_token:
            missing.append("BOT_TOKEN")
        if not self.database_url:
            missing.append("DATABASE_URL")
        if self.webhook_mode and not self.webhook_base_url:
            missing.append("WEBHOOK_BASE_URL (WEBHOOK_MODE=true bo'lganda shart)")
        if missing:
            raise RuntimeError(
                "Quyidagi muhit o'zgaruvchilari yetishmayapti: " + ", ".join(missing)
            )


config = Config()
