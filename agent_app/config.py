from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BOSS_AGENT_")

    data_dir: Path = Path("data")
    host: str = "127.0.0.1"
    port: int = 8765
    version: str = "0.1.0"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
