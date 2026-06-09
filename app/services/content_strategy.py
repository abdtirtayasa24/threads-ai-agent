from app.db import SessionLocal
from app.models import AppConfig

WRITER_STYLE_V1 = "v1"
WRITER_STYLE_V2 = "v2"
MEDIA_MODE_CAROUSEL = "carousel"
MEDIA_MODE_TEXT_ONLY = "text_only"
MEDIA_MODE_SINGLE_IMAGE = "single_image"

DEFAULT_WRITER_STYLE = WRITER_STYLE_V1
DEFAULT_MEDIA_MODE = MEDIA_MODE_CAROUSEL


def get_config_value(key: str, default: str) -> str:
    db = SessionLocal()
    try:
        config = db.query(AppConfig).filter(AppConfig.key == key).first()
        return config.value if config else default
    finally:
        db.close()


def set_config_value(key: str, value: str):
    db = SessionLocal()
    try:
        config = db.query(AppConfig).filter(AppConfig.key == key).first()
        if config:
            config.value = value
        else:
            db.add(AppConfig(key=key, value=value))
        db.commit()
    finally:
        db.close()


def get_writer_style() -> str:
    value = get_config_value("writer_style", DEFAULT_WRITER_STYLE)
    return value if value in {WRITER_STYLE_V1, WRITER_STYLE_V2} else DEFAULT_WRITER_STYLE


def get_media_mode() -> str:
    value = get_config_value("media_mode", DEFAULT_MEDIA_MODE)
    return value if value in {MEDIA_MODE_CAROUSEL, MEDIA_MODE_TEXT_ONLY, MEDIA_MODE_SINGLE_IMAGE} else DEFAULT_MEDIA_MODE


def set_content_strategy(writer_style: str, media_mode: str):
    if writer_style not in {WRITER_STYLE_V1, WRITER_STYLE_V2}:
        raise ValueError("Invalid writer style")
    if media_mode not in {MEDIA_MODE_CAROUSEL, MEDIA_MODE_TEXT_ONLY, MEDIA_MODE_SINGLE_IMAGE}:
        raise ValueError("Invalid media mode")

    set_config_value("writer_style", writer_style)
    set_config_value("media_mode", media_mode)


def get_writer_prompt_filename() -> str:
    return "writer_system_v2.md" if get_writer_style() == WRITER_STYLE_V2 else "writer_system.md"


def describe_content_strategy() -> str:
    return f"writer_style={get_writer_style()}, media_mode={get_media_mode()}"
