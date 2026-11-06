import asyncio
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path

import yt_dlp
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
COOKIES_FILE = os.environ.get("IG_COOKIES", "")  # اختیاری: فایل cookies.txt برای پست‌های خصوصی/محدود
MAX_SIZE = 50 * 1024 * 1024  # سقف آپلود ربات‌های تلگرام: ۵۰ مگابایت

IG_REGEX = re.compile(r"https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv|stories)/[^\s]+", re.I)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("igbot")


def download(url: str, out_dir: str) -> list[Path]:
    opts = {
        "outtmpl": os.path.join(out_dir, "%(id)s_%(autonumber)s.%(ext)s"),
        "format": "best[filesize<50M]/best[filesize_approx<50M]/best",
        "quiet": True,
        "noplaylist": False,
        "socket_timeout": 30,
    }
    if COOKIES_FILE and os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    return sorted(Path(out_dir).iterdir())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        " ینک پست، ریلز یا IGTV اینستاگرام رو بفرست تا برات دانلود ."
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            await status.edit_text("❌ چیزی برای دانلود پیدا نشد.")
            return

        sent = 0
        for f in files:
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.run_polling()


if __name__ == "__main__":
    main()
