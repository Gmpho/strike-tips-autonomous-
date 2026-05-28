"""
Strike Tips - Telegram Agent Loop
The entry point for the interactive AI Agent via Telegram.
"""

import asyncio
import logging
import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
    CommandHandler,
    CallbackQueryHandler,
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

I'm your AI Racing Data Analyst. Just chat with me or use commands:

/scan - Daily race scan
/status - Quick balance check
/model - Switch AI models
/help - Show this message

What would you like to do?"""
        
        keyboard = [
            [InlineKeyboardButton("🚀 Open Intelligence HUD", web_app={"url": NOTIFICATIONS.twa_url})]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(welcome, reply_markup=reply_markup, parse_mode="Markdown")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """🧠 *Available Commands*

/auth <PIN> - Unlock bot access
/scan - Start today's full racing scan
/status - Get current bankroll & ROI stats
/model - Change the specialist AI model
/clear - Reset conversation history

*Ask me things like:*
• "Who is the top value pick at Vaal?"
• "Show me my open bets"
• "Calculate edge for horse A at 6.0 odds"
"""
        keyboard = [
            [InlineKeyboardButton("🚀 Open Intelligence HUD", web_app={"url": NOTIFICATIONS.twa_url})]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode="Markdown")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not brain.strike:
            await update.message.reply_text("❌ System not initialized")
            return
        
        s = brain.strike.get_bankroll_status()
        text = (
            f"💰 *Account Summary*\n\n"
            f"Balance: *R{s['current_bankroll']:.2f}*\n"
            f"P&L: *R{s['total_profit_loss']:.2f}*\n"
            f"Open Bets: *{s['open_bets']}*\n"
            f"Drawdown: *{s['drawdown_percent']:.1f}%*"
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    async def set_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("Auto (Fallback Chain)", callback_data="model:None")],
            [InlineKeyboardButton("Fast (llama3.2:1b)", callback_data="model:llama3.2:1b")],
            [InlineKeyboardButton("Logic (func_gemma)", callback_data="model:func_gemma")],
            [InlineKeyboardButton("Deep (lfm_racing)", callback_data="model:lfm_racing")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🤖 *Select AI Specialist Model*",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    async def model_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        model_name = query.data.replace("model:", "")
        if model_name == "None":
            context.user_data["selected_model"] = None
            text = "✅ Model reset to *Auto Fallback*"
        else:
            context.user_data["selected_model"] = model_name
            text = f"✅ Model set to: *{model_name}*"
            
        await query.edit_message_text(text, parse_mode="Markdown")

    async def chart_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not brain.strike:
            await update.message.reply_text("❌ System not initialized")
            return

        await update.message.reply_text("📊 *Generating Performance Chart...*", parse_mode="Markdown")
        
        try:
            from core_agent.tools.visualizer import PerformanceVisualizer
            
            history = brain.strike.bankroll.get_history_stats(days=15)
            if not history:
                await update.message.reply_text("⚠️ No betting history found yet.")
                return

            chart_bytes = await PerformanceVisualizer.generate_bankroll_chart(history)
            if chart_bytes:
                # We need to send it via our Telegram Notifier instance
                # because the current 'update.message' doesn't support easy byte-sending 
                # without extra complexity.
                if brain.strike.telegram:
                    await brain.strike.telegram.send_photo(
                        chart_bytes, 
                        caption="📈 *Strike Tips — 15 Day Performance*"
                    )
                else:
                    await update.message.reply_photo(photo=chart_bytes, caption="📈 15 Day Performance")
            else:
                await update.message.reply_text("❌ Failed to render chart.")
                
        except Exception as e:
            logger.error(f"Chart command failed: {e}")
            await update.message.reply_text(f"❌ *Chart Error*\n`{str(e)[:200]}`", parse_mode="Markdown")

    async def auth_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from core_agent.core.access_control import is_authorized, authorize

        chat_id = update.effective_chat.id
        pin = NOTIFICATIONS.access_pin
        parts = update.message.text.split()

        if len(parts) == 2 and parts[1] == pin:
            authorize(chat_id)
            await update.message.reply_text("✅ *Access granted!* You can now use the bot.", parse_mode="Markdown")
        else:
            await update.message.reply_text("🔒 *Invalid PIN.* Access denied.", parse_mode="Markdown")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_text = update.message.text
        chat_id = update.effective_chat.id

        from core_agent.core.access_control import is_authorized

        if not is_authorized(chat_id, NOTIFICATIONS.telegram_chat_id):
            await update.message.reply_text(
                "🔒 *Restricted Access*\n\n"
                "This bot requires authorization. "
                "Send `/auth <PIN>` to gain access.",
                parse_mode="Markdown",
            )
            return

        selected_model = context.user_data.get("selected_model")
        model_display = selected_model or "Auto"

        # Show initial status
        status_message = await update.message.reply_text(
            f"⏳ Thinking ({model_display})..."
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
            # Use the orchestrator for full RAG and history
            response = await brain.orchestrator.chat(
                user_text, model_override=selected_model, user_id=str(chat_id)
            )

            typing_task.cancel()

            # Clean up response
            text = self._clean_response(response.summary)
            
            # Print response to console for DevOps
            logger.info(f"[TELEGRAM] Response: {text[:100]}...")

            # Smart chunks
            MAX_LENGTH = 4000
            if len(text) > MAX_LENGTH:
                chunks = [text[i : i + MAX_LENGTH] for i in range(0, len(text), MAX_LENGTH)]
                await status_message.delete()
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode="Markdown")
            else:
                await status_message.edit_text(text, parse_mode="Markdown")

        except Exception as e:
            typing_task.cancel()
            logger.error(f"Telegram Agent Error: {e}")
            error_msg = f"❌ *Agent Error*\n\n`{str(e)[:200]}`\n\n_Retrying with fallback..._"
            try:
                await status_message.edit_text(error_msg, parse_mode="Markdown")
            except:
                await update.message.reply_text(error_msg, parse_mode="Markdown")

    async def scan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        await update.message.reply_text("🔄 *Starting Daily Scan...*\n_This may take 30-60 seconds._", parse_mode="Markdown")
        
        try:
            # Trigger daily scan via brain.strike
            result = await brain.strike.run_daily_scan()
            text = (
                f"✅ *Daily Scan Complete*\n\n"
                f"Tracks: *{result.get('tracks_scanned', 0)}*\n"
                f"Value Bets: *{result.get('total_value_bets', 0)}*\n"
                f"Auto-Bets: *{result.get('auto_bets_placed', 0)}*"
            )
            await update.message.reply_text(text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Scan failed: {e}")
            await update.message.reply_text(f"❌ *Scan Failed*\n`{str(e)[:200]}`", parse_mode="Markdown")

    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        brain.orchestrator.clear_history()
        await update.message.reply_text("🧹 *Conversation history cleared.*", parse_mode="Markdown")

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
        application.add_handler(CommandHandler("auth", self.auth_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("model", self.set_model))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CommandHandler("scan", self.scan_command))
        application.add_handler(CommandHandler("chart", self.chart_command))
        application.add_handler(CommandHandler("clear", self.clear_command))
        
        application.add_handler(CallbackQueryHandler(self.model_callback, pattern="^model:"))
        
        application.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message)
        )

        print("🚀 Strike Tips Telegram Agent Loop is running...")
        application.run_polling()


if __name__ == "__main__":
    agent = TelegramAgent()
    agent.run()
