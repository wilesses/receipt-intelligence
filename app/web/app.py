import os
from datetime import date

from flask import Flask

from app.category_keywords import SOURCE_LABELS
from app.db import create_tables
from app.web.routes import init_routes


def category_color(category):
    colors = {
        "овощи": "#28a745",
        "фрукты": "#ff9800",
        "мясо": "#dc3545",
        "молочка": "#17a2b8",
        "молочные": "#17a2b8",
        "выпечка": "#ffc107",
        "сладости": "#6f42c1",
        "сладости/снеки": "#6f42c1",
        "напитки": "#007bff",
        "чай/кофе": "#20c997",
        "бытовое": "#6c757d",
        "быстрое питание": "#fd7e14",
        "замороженные продукты": "#00796b",
        "корма": "#9c27b0",
        "кот": "#9c27b0",
        "детское": "#0ea5e9",
        "аптека": "#16a34a",
        "служебные расходы": "#795548",
        "прочее": "#343a40",
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
        category_source_label=lambda source: SOURCE_LABELS.get(source or "rule", source or "rule"),
    )
    return app
