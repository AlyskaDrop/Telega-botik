from handlers.registration import build_registration_handlers
from handlers.admin import build_admin_handlers
from handlers.reports import build_report_handlers
from handlers.balance import build_balance_handlers
from handlers.orders import build_order_handlers
from handlers.rating import build_rating_handlers
from handlers.calculators import build_calculator_handlers
from handlers.guides import build_guides_handlers
from handlers.news import build_news_handlers
from handlers.tags import build_tag_handlers
from handlers.ai_agent import build_ai_handlers

__all__ = [
    "build_registration_handlers",
    "build_admin_handlers",
    "build_report_handlers",
    "build_balance_handlers",
    "build_order_handlers",
    "build_rating_handlers",
    "build_calculator_handlers",
    "build_guides_handlers",
    "build_news_handlers",
    "build_tag_handlers",
    "build_ai_handlers",
]
