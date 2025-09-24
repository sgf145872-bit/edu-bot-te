import os

# الدالة الأساسية لجلب المتغيرات من بيئة النظام
def _safe_get_env(key: str, default: str = None) -> str:
    """جلب متغير البيئة من os.environ."""
    return os.environ.get(key, default) or ""

# --- متغيرات البوت الأساسية ---

# يجب تعيين BOT_TOKEN كمتغير بيئة على Koyeb
BOT_TOKEN = _safe_get_env("BOT_TOKEN")

# مثال لجلب معرفات المسؤولين (يفترض أنها مفصولة بفاصلة في متغير البيئة)
admin_ids_str = _safe_get_env("ADMIN_IDS")
ADMIN_IDS = [int(i.strip()) for i in admin_ids_str.split(',') if i.strip().isdigit()]

# مثال لجلب القنوات المطلوبة (يفترض أنها مفصولة بفاصلة في متغير البيئة)
required_channels_str = _safe_get_env("REQUIRED_CHANNELS")
REQUIRED_CHANNELS = [i.strip() for i in required_channels_str.split(',') if i.strip()]

# متغيرات أخرى
BOT_ENABLED = _safe_get_env("BOT_ENABLED", "1") == "1"
