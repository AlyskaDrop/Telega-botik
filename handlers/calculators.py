"""Industry calculator (production cost by skills) and Implant leveling calculator."""

from __future__ import annotations

import math

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ══════════════════════════════════════════════════════════════════════════════
# INDUSTRY CALCULATOR
# ══════════════════════════════════════════════════════════════════════════════
# Conversation states
IND_SKILL, IND_BASE_COST, IND_MATERIAL_EFF = range(3)

# Each point of Industry skill reduces manufacturing time by 4 %
# Each point of Advanced Industry skill reduces it by 3 %
# Material Efficiency (ME) research reduces material cost
ME_BONUS_PER_LEVEL = 0.01   # 1 % per ME level up to 10
TIME_REDUCTION_INDUSTRY = 0.04   # 4 % per level (5 levels)
TIME_REDUCTION_ADV = 0.03        # 3 % per level (5 levels)


async def ind_calc_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🏭 *Калькулятор производства*\n\n"
        "Введи уровень навыка *Industry* (1-5) и *Advanced Industry* (1-5) через пробел:\n"
        "Например: `4 3`",
        parse_mode="Markdown",
    )
    return IND_SKILL


async def ind_skill_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    parts = update.message.text.strip().split()
    try:
        ind = max(0, min(5, int(parts[0])))
        adv = max(0, min(5, int(parts[1]) if len(parts) > 1 else 0))
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Формат: `<Industry> <AdvancedIndustry>`, например: `5 3`")
        return IND_SKILL

    context.user_data["ind"] = ind
    context.user_data["adv"] = adv
    await update.message.reply_text("Введи базовую стоимость материалов (в ISK):")
    return IND_BASE_COST


async def ind_base_cost_received(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    try:
        base = float(update.message.text.strip().replace(",", ".").replace(" ", ""))
    except ValueError:
        await update.message.reply_text("❌ Введи число:")
        return IND_BASE_COST
    context.user_data["base_cost"] = base
    await update.message.reply_text("Введи уровень исследования материальной эффективности чертежа (ME, 0-10):")
    return IND_MATERIAL_EFF


async def ind_me_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        me = max(0, min(10, int(update.message.text.strip())))
    except ValueError:
        await update.message.reply_text("❌ Введи целое число 0-10:")
        return IND_MATERIAL_EFF

    base = context.user_data["base_cost"]
    ind = context.user_data["ind"]
    adv = context.user_data["adv"]

    me_discount = 1.0 - me * ME_BONUS_PER_LEVEL
    effective_cost = base * me_discount

    time_mult = (1 - ind * TIME_REDUCTION_INDUSTRY) * (1 - adv * TIME_REDUCTION_ADV)
    time_mult = max(time_mult, 0.20)   # cap at 80 % reduction

    await update.message.reply_text(
        "🏭 *Результат расчёта производства*\n\n"
        f"Базовая стоимость материалов: `{base:,.0f}` ISK\n"
        f"ME {me} → скидка {me * ME_BONUS_PER_LEVEL * 100:.0f}%\n"
        f"*Итоговая стоимость:* `{effective_cost:,.0f}` ISK\n\n"
        f"Industry {ind} + Advanced Industry {adv}\n"
        f"Сокращение времени: {(1 - time_mult) * 100:.1f}%",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def ind_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
# IMPLANT LEVELING CALCULATOR  (levels 1-40)
# ══════════════════════════════════════════════════════════════════════════════
# In Eve Echoes implants cost SP (skill points) to level up.
# Approximate SP formula used: SP(level) = 250 * level * (level - 1) + 500
# This is a simplified model since actual data may vary.

IMP_CURRENT_LVL, IMP_TARGET_LVL = range(2)

SP_PER_HOUR_BASE = 1800   # base SP/h with no boosters


def _implant_sp_for_level(lvl: int) -> int:
    """Cumulative SP needed to reach implant level `lvl` from level 0."""
    return sum(int(500 * (i ** 1.6)) for i in range(1, lvl + 1))


async def imp_calc_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🧬 *Калькулятор прокачки имплантов* (1–40 ур.)\n\n"
        "Введи *текущий уровень* импланта:",
        parse_mode="Markdown",
    )
    return IMP_CURRENT_LVL


async def imp_current_lvl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lvl = max(0, min(39, int(update.message.text.strip())))
    except ValueError:
        await update.message.reply_text("❌ Введи число от 0 до 39:")
        return IMP_CURRENT_LVL
    context.user_data["imp_current"] = lvl
    await update.message.reply_text(f"Текущий уровень: {lvl}.\nВведи *целевой уровень* (до 40):", parse_mode="Markdown")
    return IMP_TARGET_LVL


async def imp_target_lvl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    current = context.user_data["imp_current"]
    try:
        target = max(current + 1, min(40, int(update.message.text.strip())))
    except ValueError:
        await update.message.reply_text("❌ Введи число:")
        return IMP_TARGET_LVL

    sp_current = _implant_sp_for_level(current)
    sp_target = _implant_sp_for_level(target)
    sp_needed = sp_target - sp_current

    hours = sp_needed / SP_PER_HOUR_BASE
    days = hours / 24
    hours_remainder = hours % 24

    await update.message.reply_text(
        "🧬 *Результат прокачки импланта*\n\n"
        f"С уровня *{current}* до *{target}*\n"
        f"Требуется SP: `{sp_needed:,}`\n\n"
        f"🕐 Время прокачки (базовое):\n"
        f"≈ {int(days)}д {int(hours_remainder)}ч (при {SP_PER_HOUR_BASE} SP/ч)\n\n"
        f"_Реальное время зависит от бустеров и альфа/омега клона._",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def imp_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


def build_calculator_handlers() -> list:
    ind_conv = ConversationHandler(
        entry_points=[CommandHandler("industry_calc", ind_calc_start)],
        states={
            IND_SKILL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ind_skill_received)],
            IND_BASE_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, ind_base_cost_received)],
            IND_MATERIAL_EFF: [MessageHandler(filters.TEXT & ~filters.COMMAND, ind_me_received)],
        },
        fallbacks=[CommandHandler("cancel", ind_cancel)],
    )
    imp_conv = ConversationHandler(
        entry_points=[CommandHandler("implant_calc", imp_calc_start)],
        states={
            IMP_CURRENT_LVL: [MessageHandler(filters.TEXT & ~filters.COMMAND, imp_current_lvl)],
            IMP_TARGET_LVL: [MessageHandler(filters.TEXT & ~filters.COMMAND, imp_target_lvl)],
        },
        fallbacks=[CommandHandler("cancel", imp_cancel)],
    )
    return [ind_conv, imp_conv]
