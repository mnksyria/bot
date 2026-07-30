"""
api.py
سيرفر FastAPI يوفر endpoints للقراءة فقط (read-only) لصالح الـ Mini App.
بيشتغل جوا نفس بروسس البوت (bot.py) على خيط منفصل عن طريق uvicorn، وبيقرأ
مباشرة من نفس ملف database.db يلي البوت عم يكتب فيه - بدون أي خدمة Render
إضافية وبدون مشكلة مزامنة بين نسختين.
"""

from pathlib import Path
from typing import Optional

import firebase_admin
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from pydantic import BaseModel

import auth_store
import db

# مجلد ملفات المواد (.db) الجاهزة للتحميل من التطبيق. لازم يكون هون بنفس
# مستودع الكود (git) عشان ما ينمسح لما Render يعيد التشغيل (ephemeral filesystem).
PACKAGES_DIR = Path(__file__).parent / "packages"

# مجلد إصدار التطبيق نفسه (APK) - نفس فكرة PACKAGES_DIR تماماً: لازم يكون
# بنفس مستودع الكود، وكل إصدار جديد بينحط هون باسم latest.apk (استبدال الملف
# القديم). هيك التطبيق ينزّل التحديث من داخله مباشرة بدل تيليجرام/متصفح خارجي،
# فما يضل أي ملف تنزيل ظاهر بمجلد التنزيلات العام للجهاز.
APP_RELEASE_DIR = Path(__file__).parent / "app_release"

# تهيئة Firebase Admin مرة وحدة بس، من متغير بيئة (Environment Variable)
# اسمه FIREBASE_SERVICE_ACCOUNT_JSON يحتوي محتوى ملف مفتاح الخدمة كامل كنص JSON.
import json
import os

_service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
if _service_account_json and not firebase_admin._apps:
    _cred = credentials.Certificate(json.loads(_service_account_json))
    firebase_admin.initialize_app(_cred)

app = FastAPI(title="Question Bank API")

# مسموح لأي أصل (origin) يطلب - لازم هيك لأنو الـ Mini App بتنفتح جوا
# تطبيق تيليجرام (Web View) وممكن تجي من أي دومين/بروتوكول.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health():
    """health-check بسيط (نفس وظيفة السيرفر القديم) حتى يعتبر Render التطبيق شغال."""
    return {"status": "ok", "message": "البوت شغال ✅"}


def verify_firebase_token(authorization: Optional[str]) -> str:
    """
    بتتحقق من رأس Authorization: Bearer <token> وبترجع uid المستخدم لو صحيح.
    بترمي HTTPException 401 لو التوكن ناقص أو غير صالح.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="لازم تسجل دخول أول")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="جلسة الدخول غير صالحة، سجّل دخول من جديد")


class DeviceLoginBody(BaseModel):
    device_id: str
    username: str


@app.post("/api/auth/device-login")
def api_device_login(body: DeviceLoginBody):
    """
    تسجيل دخول/تسجيل حساب جديد بدون أي كلمة سر - الاعتماد الكامل على
    device_id (معرّف الجهاز الفريد المُولَّد من تطبيق الأندرويد).

    - جهاز جديد كلياً => بينشئ حساب باسم username المُرسَل ويرجع توكن.
    - جهاز مسجّل مسبقاً بنفس الاسم => بيرجع توكن لنفس الحساب القديم.
    - جهاز مسجّل مسبقاً باسم مختلف عن يلي انبعت => 403 (حماية من انتحال
      حساب شخص تاني بمجرد معرفة اسمه).
    """
    try:
        result = auth_store.login_or_register(body.device_id, body.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if result.get("error") == "username_mismatch":
        raise HTTPException(
            status_code=403,
            detail="هذا الجهاز مسجّل مسبقاً باسم مختلف عن الاسم المدخل",
        )
    return result


def _verify_admin(x_admin_key: Optional[str]) -> None:
    """حماية بسيطة بمفتاح ثابت للوحة التحكم - مش Firebase ID token لأنو
    هاد استخدام إداري بس (إنت شخصياً)، مش جزء من تدفق تطبيق الطلاب."""
    expected = os.environ.get("ADMIN_API_KEY")
    if not expected or x_admin_key != expected:
        raise HTTPException(status_code=401, detail="غير مصرح")


@app.get("/api/admin/accounts")
def api_admin_list_accounts(x_admin_key: Optional[str] = Header(None)):
    """كل الحسابات: الاسم + device_id + تاريخ التسجيل."""
    _verify_admin(x_admin_key)
    return auth_store.list_accounts()


@app.delete("/api/admin/accounts/{uid}")
def api_admin_delete_account(uid: str, x_admin_key: Optional[str] = Header(None)):
    """حذف حساب بالكامل - نفس الجهاز إذا رجع سجّل بعدها بيصير كأنه جهاز
    جديد تماماً، وبيقدر يحط أي اسم من الصفر."""
    _verify_admin(x_admin_key)
    auth_store.delete_account(uid)
    return {"status": "deleted"}


@app.get("/api/app/latest")
def download_latest_apk():
    """
    تحميل آخر إصدار من التطبيق نفسه (APK) - يستخدمها التطبيق داخلياً بدل
    الاعتماد على رابط تيليجرام خارجي. لا يحتاج تسجيل دخول (المستخدم أصلاً
    ممكن يكون خارج حسابه ولسا لازم يحدّث التطبيق قبل ما يقدر يدخل).
    """
    apk_path = APP_RELEASE_DIR / "latest.apk"
    if not apk_path.exists():
        raise HTTPException(status_code=404, detail="لا يوجد إصدار متاح حالياً")
    return FileResponse(
        path=str(apk_path),
        media_type="application/vnd.android.package-archive",
        filename="QPlus.apk",
    )


@app.get("/api/packages")
def api_packages_list():
    """
    قائمة الكتل (packages) المتاحة للتحميل - بديل عن ملف Google Drive
    القديم المعطل. بيقرا من packages/packages.json (ملف بسيط، بدون حماية
    لأنه بس أسماء ووصف، مو محتوى فعلي).
    """
    manifest_path = PACKAGES_DIR / "packages.json"
    if not manifest_path.exists():
        return []
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/packages/{package_id}/download")
def download_package(package_id: str, authorization: Optional[str] = Header(None)):
    """
    تحميل ملف مادة (.zip يحتوي .db بداخله) - محمي: لازم تسجيل دخول فعلي
    (Firebase ID Token) قبل ما يوصل الملف. الملفات نفسها موجودة جوا مجلد
    packages/ بنفس الكود، بصيغة .zip (نفس الصيغة يلي تطبيق الأندرويد
    يتوقعها ويفك ضغطها لحاله).
    """
    verify_firebase_token(authorization)  # بيرمي 401 تلقائياً لو مش صالح

    # حماية بسيطة من محاولة الخروج عن مجلد packages عبر أسماء ملفات ملغومة
    safe_name = os.path.basename(package_id)
    file_path = PACKAGES_DIR / f"{safe_name}.zip"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="المادة غير موجودة")

    return FileResponse(
        path=str(file_path),
        media_type="application/zip",
        filename=f"{safe_name}.zip",
    )


@app.get("/api/subjects")
def api_subjects():
    subjects = db.get_all_subjects_with_counts()
    return [
        {"uuid": uuid_, "name": name, "questions_count": count}
        for uuid_, name, count in subjects
    ]


@app.get("/api/sheets")
def api_all_sheets(
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
):
    """كل الشيتات بكل المواد، مرتبة حسب التاريخ (الأحدث أولاً) - يستخدمها
    مسار "تصفح حسب الشيت" الجديد اللي بيبلش من التاريخ مباشرة."""
    sheets, total = db.get_all_sheets(limit=limit, offset=offset)
    return {
        "total": total,
        "sheets": [
            {"uuid": uuid_, "year": year, "term": term, "questions_count": count}
            for uuid_, year, term, count in sheets
        ],
    }


@app.get("/api/subjects/{subject_uuid}/sheets")
def api_subject_sheets(
    subject_uuid: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    sheets, total = db.get_sheets_by_subject(subject_uuid, limit=limit, offset=offset)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "sheets": [
            {"uuid": uuid_, "year": year, "term": term, "questions_count": count}
            for uuid_, year, term, count in sheets
        ],
    }


@app.get("/api/sheets/{sheet_uuid}")
def api_sheet_detail(sheet_uuid: str, subject_uuid: Optional[str] = None):
    """يرجّع الشيت كاملة: معلوماتها + كل المواد المشتركة فيها + كل أسئلتها
    (بإجاباتها وتصنيفاتها). إذا انعطى ?subject_uuid=... بيقتصر عرض
    الأسئلة على هاي المادة بس."""
    detail = db.get_sheet_full_detail(sheet_uuid, subject_uuid=subject_uuid)
    if detail is None:
        raise HTTPException(status_code=404, detail="الشيت مش موجودة")
    return detail


@app.get("/api/subjects/{subject_uuid}/tags")
def api_subject_tags(subject_uuid: str):
    """تصنيفات المادة، مرتبة حسب الأولوية (الأكتر تكراراً بالامتحانات أولاً)."""
    tags = db.get_tags_for_subject(subject_uuid)
    return [{"uuid": uuid_, "name": name, "count": count} for uuid_, name, count in tags]


@app.get("/api/subjects/{subject_uuid}/tags/{tag_uuid}/questions")
def api_tag_questions(
    subject_uuid: str,
    tag_uuid: str,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """كل أسئلة مادة معينة تحت تصنيف معين، مرتبة حسب الأولوية (الأحدث أولاً)."""
    questions, total = db.get_questions_by_tag(
        subject_uuid, tag_uuid, limit=limit, offset=offset
    )
    return {"total": total, "questions": questions}


@app.get("/api/stats/overview")
def api_stats_overview():
    return db.get_overview_stats()


@app.get("/api/stats/subjects/{subject_uuid}")
def api_subject_stats(subject_uuid: str):
    stats = db.get_subject_stats(subject_uuid)
    if stats is None:
        raise HTTPException(status_code=404, detail="المادة مش موجودة")
    return stats


# لازم هاد آخر شي بالملف - أي مسار API لازم يتسجل قبل mount الـ static files
# حتى ما يبلعها الـ StaticFiles catch-all.
app.mount("/webapp", StaticFiles(directory="static", html=True), name="webapp")
