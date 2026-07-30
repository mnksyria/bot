"""
auth_store.py
منطق حسابات المستخدمين المرتبطة بمعرّف الجهاز (device_id) - بديل نظام
اسم المستخدم + PIN القديم بالكامل.

الفكرة:
    كل حساب مربوط بشكل دائم بـ uid حتمي (deterministic) مُشتق رياضياً من
    device_id عبر sha256. يعني نفس الجهاز هيرجع دايماً لنفس الـ uid ونفس
    الحساب، بغض النظر عن عدد مرات حذف/تنزيل التطبيق. اسم المستخدم مجرد
    بيانات عرض فوق هاد الـ uid - أول اسم يتسجل فيه الجهاز بيصير هو الاسم
    الثابت الوحيد المقبول لهاد الجهاز، وأي محاولة دخول باسم مختلف عن نفس
    الجهاز بترفض (403) - هاي هي الحماية من "فتح حساب شخص تاني بمعرفة اسمه".

    بيانات الحسابات نفسها (username <-> device_id <-> uid) محفوظة بـ
    Firestore (collection: users) مش بقاعدة بيانات المحتوى (database.db)،
    لأنها بيانات هوية/دخول لا علاقة إلها ببنك الأسئلة.
"""

import hashlib
from typing import Optional

from firebase_admin import auth as firebase_auth
from firebase_admin import firestore

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = firestore.client()
    return _db


def uid_for_device(device_id: str) -> str:
    """uid حتمي وثابت لنفس device_id دايماً."""
    digest = hashlib.sha256(device_id.strip().encode("utf-8")).hexdigest()
    return f"d_{digest[:32]}"


def _normalize_username(username: str) -> str:
    return username.strip()


def login_or_register(device_id: str, username: str) -> dict:
    """
    - أول مرة لهاد الجهاز: بينشئ حساب جديد بهاد الاسم ويرجع توكن دخول.
    - جهاز موجود مسبقاً + نفس الاسم المسجل فيه (بغض النظر عن حالة
      الأحرف/المسافات الزايدة): بيرجع توكن دخول لنفس الحساب.
    - جهاز موجود مسبقاً + اسم مختلف: بيرجع {"error": "username_mismatch"}.
    """
    device_id = (device_id or "").strip()
    username = _normalize_username(username or "")
    if not device_id or not username:
        raise ValueError("device_id و username مطلوبين")

    uid = uid_for_device(device_id)
    db = _get_db()
    doc_ref = db.collection("users").document(uid)
    doc = doc_ref.get()

    if doc.exists:
        data = doc.to_dict() or {}
        stored_username = data.get("username", "")
        if stored_username.strip().lower() != username.lower():
            return {"error": "username_mismatch"}
    else:
        # أول تسجيل لهاد الجهاز - ننشئ مستخدم Firebase Auth بنفس الـ uid
        # الحتمي (لو موجود أصلاً من محاولة سابقة ما كملت، منتجاهل الخطأ).
        try:
            firebase_auth.get_user(uid)
        except firebase_auth.UserNotFoundError:
            firebase_auth.create_user(uid=uid)

        doc_ref.set(
            {
                "username": username,
                "device_id": device_id,
                "created_at": firestore.SERVER_TIMESTAMP,
            }
        )

    token = firebase_auth.create_custom_token(uid)
    if isinstance(token, bytes):
        token = token.decode("utf-8")

    return {"token": token, "uid": uid, "username": username}


def list_accounts(limit: int = 1000) -> list:
    """كل الحسابات (اسم + device_id) - تستخدم من لوحة التحكم فقط."""
    db = _get_db()
    query = db.collection("users").limit(limit)
    result = []
    for snap in query.stream():
        data = snap.to_dict() or {}
        created_at = data.get("created_at")
        result.append(
            {
                "uid": snap.id,
                "username": data.get("username"),
                "device_id": data.get("device_id"),
                "created_at": created_at.isoformat() if created_at else None,
            }
        )
    result.sort(key=lambda a: a["created_at"] or "", reverse=True)
    return result


def delete_account(uid: str) -> None:
    """
    حذف الحساب بالكامل (Firestore + Firebase Auth). بعد الحذف، نفس الجهاز
    (نفس device_id) لو رجع سجّل، بيرجع يترعامل كأنه أول مرة - يقدر يحط
    أي اسم جديد من الصفر.
    """
    db = _get_db()
    db.collection("users").document(uid).delete()
    try:
        firebase_auth.delete_user(uid)
    except firebase_auth.UserNotFoundError:
        pass


def get_account_by_device(device_id: str) -> Optional[dict]:
    uid = uid_for_device(device_id)
    doc = _get_db().collection("users").document(uid).get()
    if not doc.exists:
        return None
    data = doc.to_dict() or {}
    return {"uid": uid, "username": data.get("username"), "device_id": data.get("device_id")}
