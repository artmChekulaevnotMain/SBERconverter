


from config.app.config import AppSettings


class Secrets:
    app: AppSettings = AppSettings()

APP_CONFIG = Secrets()

__all__ = [
    "APP_CONFIG",
    "AppSettings",
    "Secrets",
]
