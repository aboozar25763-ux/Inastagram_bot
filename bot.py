import asyncio
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path

import yt_dlp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatMemberStatus
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
COOKIES_FILE = os.environ.get("IG_COOKIES", "")  # اختیاری: فایل cookies.txt برای پست‌های خصوصی/محدود
# عضویت اجباری: یوزرنیم کانال مثل @mychannel (یا آیدی عددی مثل -100123...). خالی = غیرفعال
REQUIRED_CHANNEL = os.environ.get("REQUIRED_CHANNEL", "@DollarChiFA").strip()
# برای کانال خصوصی: لینک دعوت کانال (https://t.me/+xxxx)
CHANNEL_LINK = os.environ.get("CHANNEL_LINK", "").strip()
MAX_SIZE = 50 * 1024 * 1024  # سقف آپلود ربات‌های تلگرام: ۵۰ مگابایت

IG_REGEX = re.compile(r"https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv|stories)/[^\s]+", re.I)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("igbot")


        ydl.download([url])
    return sorted(Path(out_dir).iterdir())


def channel_url() -> str:
    if CHANNEL_LINK:
        return CHANNEL_LINK
    return f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}"


async def is_member(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    if not REQUIRED_CHANNEL:
        return True
    try:
        m = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
    except Exception as e:
        # معمولاً یعنی ربات توی کانال ادمین نیست یا آیدی کانال اشتباهه
        log.error("membership check failed (is the bot an admin of the channel?): %s", e)
        return False
    if m.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        return True
    return m.status == ChatMemberStatus.RESTRICTED and getattr(m, "is_member", False)


async def ask_to_join(update: Update):
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📢 عضویت در کانال", url=channel_url())],
            [InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")],
        ]
    )
    text = "برای استفاده از ربات اول باید توی کانال ما عضو بشی 👇\nبعد از عضویت دکمه «عضو شدم» رو بزن."
    if update.callback_query:
        await update.callback_query.answer("هنوز عضو کانال نشدی ❌", show_alert=True)
    else:
        await update.effective_message.reply_text(text, reply_markup=kb)


async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if await is_member(context, q.from_user.id):
        await q.answer("عضویتت تأیید شد ✅")
        await q.message.edit_text("✅ عضویتت تأیید شد.\nحالا لینک پست یا ریلز اینستاگرام رو بفرست.")
    else:
        await ask_to_join(update)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_member(context, update.effective_user.id):
        await ask_to_join(update)
        return
    await update.message.reply_text(
        "سلام 👋\nلینک پست، ریلز یا IGTV اینستاگرام رو بفرست تا برات دانلود کنم."
    )


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_member(context, update.effective_user.id):
        await ask_to_join(update)
        return
    text = update.message.text or ""
    m = IG_REGEX.search(text)
    if not m:
        await update.message.reply_text("لطفاً یه لینک معتبر اینستاگرام بفرست.")
        return

    url = m.group(0)
    status = await update.message.reply_text("⏳ در حال دانلود...")
    tmp = tempfile.mkdtemp(prefix="igbot_")
    try:
        await update.message.chat.send_action(ChatAction.UPLOAD_VIDEO)
        files = await asyncio.to_thread(download, url, tmp)
        if not files:
            if f.stat().st_size > MAX_SIZE:
                await update.message.reply_text(f"⚠️ فایل {f.name} بزرگ‌تر از ۵۰ مگابایته و نمی‌تونم بفرستمش.")
                continue
            with open(f, "rb") as fh:
                if f.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"}:
                    await update.message.reply_video(fh, supports_streaming=True)
                elif f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    await update.message.reply_photo(fh)
                else:
                    await update.message.reply_document(fh)
            sent += 1

        await status.delete() if sent else await status.edit_text("❌ ارسال نشد.")
    except yt_dlp.utils.DownloadError as e:
        log.warning("download error: %s", e)
        await status.edit_text(
            "❌ دانلود نشد. ممکنه پست خصوصی باشه، حذف شده باشه یا اینستاگرام درخواست رو محدود کرده باشه."
        )
    except Exception:
        log.exception("unexpected error")
        await status.edit_text("❌ خطای غیرمنتظره رخ داد. بعداً دوباره امتحان کن.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    if not BOT_TOKEN:
        raise SystemExit("متغیر محیطی BOT_TOKEN تنظیم نشده.")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_join, pattern="^check_join$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.run_polling()


if name == "main":
    main()
