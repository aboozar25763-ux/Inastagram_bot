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
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
COOKIES_FILE = os.environ.get("IG_COOKIES", "")  # اختیاری: فایل cookies.txt برای پست‌های خصوصی/محدود
MAX_SIZE = 50 * 1024 * 1024  # سقف آپلود ربات‌های تلگرام: 1000 مگابایت

IG_REGEX = re.compile(r"https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv|stories)/[^\s]+", re.I)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("igbot")
async def check_membership(update, context):
    user_id = update.effective_user.id

    member = await context.bot.get_chat_member(
        chat_id="@DollarChiFA",
        user_id=user_id
    )

    if member.status in ("left", "kicked"):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "عضویت در کانال",
                url="https://t.me/DollarChiFA"
            )]
        ])

        await update.effective_message.reply_text(
            "برای استفاده از ربات ابتدا عضو کانال شوید.",
            reply_markup=keyboard
        )
        return False

    return True

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
    return sorted(Path(out_dir).iterdir

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        " ینک پست، ریلز یا IGTV اینستاگرام رو بفرست تا برات دانلود ."
 if not await check_membership(update, context):
        return   )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):    
    text = update.message.text or ""
    if not await check_membership(update, context):
        returnm = IG_REGEX.search(text)
    if not m:
        await update.message.reply_text("لطفاً یه لینک معتبر اینستاگرام بفرست.")
        return

  async def check_membership_callback(update, context):
    query = update.callback_query
    await query.answer()

    try:
        member = await context.bot.get_chat_member(
            chat_id="@DollarChiFA",
            user_id=query.from_user.id
        )

        if member.status in ("member", "administrator", "creator"):
            await query.edit_message_text(
                "✅ عضویت تأیید شد! حالا لینک اینستاگرام رو بفرست."
            )
        else:
            await query.answer(
                "❌ هنوز عضو کانال نشدی!",
                show_alert=True
            )
    except Exception:
        await query.answer(
            "خطا در بررسی عضویت. دوباره تلاش کن.",
            show_alert=True
        )


def main():
    if not BOT_TOKEN:
        raise SystemExit("متغیر محیطی BOT_TOKEN تنظیم نشده.")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(
        check_membership_callback,
        pattern="^check_membership$"
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_link
    ))

    app.run_polling()


if name == "main":
    main()  


if __name__ == "__main__":
    main()
