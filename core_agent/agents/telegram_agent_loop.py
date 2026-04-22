"""
Strike Tips - Telegram Agent Loop
The entry point for the interactive AI Agent via Telegram.
"""

import asyncio
import logging
import os
import re
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
    CommandHandler,
)

from core_agent.core.strike_brain import brain
from core_agent.config.settings import NOTIFICATIONS

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("strike-telegram")


class TelegramAgent:
    def __init__(self):
        self.bot_token = NOTIFICATIONS.telegram_bot_token
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not found in environment")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome = """🏇 *Strike Tips Agent*

I'm your AI Racing Data Analyst. Just chat with me:

• "scan today's races"
• "analyze race at Turffontein Race 3"
• "check my bankroll"
• "search for horse data"
• "record my selection"

Use /model to switch AI models.

What would you like to do?"""
        await update.message.reply_text(welcome, parse_mode="Markdown")

    async def set_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from telegram import ReplyKeyboardMarkup

        models = [
            ["Auto", "racing_llama"],
            ["racing_qwen", "racing_qwen"],
            ["func_gemma", "func_gemma"],
            ["lfm_racing", "lfm_racing"],
        ]

        reply_markup = ReplyKeyboardMarkup(
            models, one_time_keyboard=True, resize_keyboard=True
        )
        await update.message.reply_text(
            "🤖 *Select AI Model*\n\nChoose your engine:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_text = update.message.text
        chat_id = update.effective_chat.id

        # Handle model selection buttons
        if user_text in ["racing_llama", "racing_qwen", "func_gemma", "lfm_racing"]:
            context.user_data["selected_model"] = user_text
            await update.message.reply_text(
                f"✅ Model set to: *{user_text}*", parse_mode="Markdown"
            )
            return

        if user_text == "Auto":
            context.user_data["selected_model"] = None
            await update.message.reply_text("✅ Model reset to Auto")
            return

        if NOTIFICATIONS.telegram_chat_id and str(chat_id) != str(
            NOTIFICATIONS.telegram_chat_id
        ):
            logger.warning(f"Unauthorized access attempt from chat_id: {chat_id}")
            return

        selected_model = context.user_data.get("selected_model")
        model_display = selected_model or "Auto"

        status_message = await update.message.reply_text(
            f"⏳ Analyzing with {model_display}..."
        )

        async def keep_typing():
            while True:
                try:
                    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
                    await asyncio.sleep(3)
                except Exception:
                    break

        typing_task = asyncio.create_task(keep_typing())

        try:
            response = await brain.pipeline.chat(
                user_text, model_override=selected_model
            )

            typing_task.cancel()

            try:
                await status_message.delete()
            except:
                pass

            # Clean up ASCII tags and convert to emojis
            text = self._clean_response(response.summary)

            # Print response to console for debugging
            print(f"\n[BOT] >>> Response to user:")
            print(f"      {text[:500]}")
            print(f"[BOT] <<< Sent via Telegram\n")

            MAX_LENGTH = 4000
            chunks = [text[i : i + MAX_LENGTH] for i in range(0, len(text), MAX_LENGTH)]

            for chunk in chunks:
                try:
                    await update.message.reply_text(chunk, parse_mode="Markdown")
                except Exception:
                    await update.message.reply_text(chunk)

        except Exception as e:
            typing_task.cancel()
            logger.error(f"Telegram Agent Error: {e}")
            try:
                await status_message.edit_text(f"❌ Error: {str(e)[:200]}")
            except:
                await update.message.reply_text(f"❌ Error: {str(e)[:200]}")

    def _clean_response(self, text: str) -> str:
        """Convert ASCII tags to emojis and clean up response."""
        replacements = {
            "[RACE]": "🏇",
            "[LOC]": "📍",
            "[DATE]": "📅",
            "[STATS]": "📊",
            "[OK]": "✅",
            "[ERR]": "❌",
            "[WARN]": "⚠️",
            "[LOOKUP]": "🔍",
            "[BOT]": "🤖",
            "[CHAT]": "💬",
            "[START]": "🚀",
            "[SCAN]": "🔄",
            "[HIT]": "🎯",
            "[TIME]": "⏰",
            "[MAF]": "🧠",
            "[STOP]": "🛑",
            "[WORLD]": "🌍",
            "[SA]": "🇿🇦",
            "[UK]": "🇬🇧",
            "[AU]": "🇦🇺",
            "[US]": "🇺🇸",
            "[IE]": "🇮🇪",
            "[FR]": "🇫🇷",
            "[HK]": "🇭🇰",
            "[JP]": "🇯🇵",
            "[SAVE]": "💾",
            "[HEALTH]": "🏥",
            "[SEC]": "🔐",
            "[SIGNAL]": "📡",
            "[NO]": "🚫",
            "[IDEA]": "💡",
            "[PKG]": "📦",
            "[VASE]": "🏺",
            "[MSG]": "📨",
            "[FAST]": "⚡",
            "[RUN]": "🏃",
            "[LIST]": "📋",
            "[HI]": "👋",
            "[LINK]": "🔗",
            "[NOTE]": "📝",
            "[Y]": "✓",
            "[X]": "✗",
            "[INFO]": "ℹ️",
            "Status: online": "✅ Online",
        }

        for tag, emoji in replacements.items():
            text = text.replace(tag, emoji)

        # Remove any remaining [XXX] tags
        text = re.sub(r"\[([A-Z]{2,})\]", "", text)

        return text.strip()

    async def error_handler(
        self, update: object, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        from telegram.error import NetworkError

        if isinstance(context.error, NetworkError):
            logger.warning(f"Network error: {context.error}")
        else:
            logger.error(f"Telegram Exception: {context.error}", exc_info=context.error)

    def run(self):
        brain.initialize()

        application = ApplicationBuilder().token(self.bot_token).build()
        application.add_error_handler(self.error_handler)

        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("model", self.set_model))
        application.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message)
        )

        print("🚀 Strike Tips Telegram Agent Loop is running...")
        application.run_polling()


if __name__ == "__main__":
    agent = TelegramAgent()
    agent.run()
