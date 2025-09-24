# config.py
import os

def _safe_get_env(key: str, default: str = "") -> str:
    """يحصل على قيمة من بيئة التشغيل (يدعم Streamlit Secrets ومتغيرات النظام)."""
    try:
        # محاولة القراءة من Streamlit Secrets أولًا
        import streamlit as st
        return st.secrets.get(key, default)
    except (ImportError, AttributeError, KeyError, RuntimeError):
        # إذا فشل (مثل التشغيل المحلي)، نستخدم os.getenv
        return os.getenv(key, default)

# جلب القيم مع قيم افتراضية فارغة
BOT_TOKEN = _safe_get_env("BOT_TOKEN", "").strip()
ADMIN_IDS_RAW = _safe_get_env("ADMIN_IDS", "").strip()
REQUIRED_CHANNELS_RAW = _safe_get_env("REQUIRED_CHANNELS", "").strip()

# === التحقق من التوكن ===
if not BOT_TOKEN:
    raise ValueError(
        "❌ خطأ: لم يتم تعيين BOT_TOKEN.\n"
        "يرجى إضافته في Streamlit Secrets (أو كمتغير بيئة محلي)."
    )

# === معالجة القوائم بأمان ===
def _parse_comma_separated_ids(raw: str) -> list[int]:
    if not raw:
        return []
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():  # يدعم الأرقام السالبة (مثل -100...)
            ids.append(int(part))
        else:
            print(f"⚠️ تحذير: تجاهل القيمة غير الصالحة في القائمة: '{part}'")
    return ids

ADMIN_IDS = _parse_comma_separated_ids(ADMIN_IDS_RAW)
REQUIRED_CHANNELS = _parse_comma_separated_ids(REQUIRED_CHANNELS_RAW)

# === طباعة تأكيد التهيئة (لأغراض التصحيح) ===
if __name__ == "__main__":
    print("✅ تم تحميل الإعدادات بنجاح:")
    print(f"   BOT_TOKEN: {'*' * 12 + BOT_TOKEN[-6:]}")
    print(f"   ADMIN_IDS: {ADMIN_IDS}")
    print(f"   REQUIRED_CHANNELS: {REQUIRED_CHANNELS}")
