import os
from datetime import date

from flask import Flask

from app.category_keywords import SOURCE_LABELS, category_for_reporting
from app.db import create_tables
from app.web.routes import init_routes


def category_color(category):
    colors = {
        "овощи и фрукты": "#28a745",
        "мясо и птица": "#dc3545",
        "рыба и морепродукты": "#0ea5e9",
        "молочные продукты и альтернативы": "#17a2b8",
        "яйца": "#eab308",
        "хлеб и выпечка": "#ffc107",
        "бакалея и основные продукты": "#a16207",
        "готовая еда и быстрое приготовление": "#fd7e14",
        "замороженные продукты": "#00796b",
        "соусы, приправы и консервы": "#c2410c",
        "снеки и сладости": "#6f42c1",
        "безалкогольные напитки": "#007bff",
        "алкоголь": "#7c3aed",
        "детское": "#0ea5e9",
        "товары для животных": "#9c27b0",
        "бытовое и личный уход": "#6c757d",
        "служебные строки": "#795548",
        "прочее / требует решения": "#343a40",
    }
    return colors.get(category, "#999")


def create_app():
    create_tables()
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "receipt-tracker-dev")
    app.config.setdefault("TODAY_PROVIDER", date.today)
    init_routes(app)
    app.jinja_env.globals.update(
        category_color=category_color,
        category_for_reporting=category_for_reporting,
        category_source_label=lambda source: SOURCE_LABELS.get(source or "rule", source or "rule"),
    )
    return app
