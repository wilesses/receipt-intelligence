import tempfile
import unittest
from datetime import date
from pathlib import Path

import app.dashboard_service as dashboard
import app.db as db
from app.product_matcher import _cache
from app.web.app import create_app


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.old_db_path = db.DB_PATH
        db.DB_PATH = Path(self.tmpdir.name) / "test.db"
        db.create_tables()
        _cache.clear()

    def tearDown(self):
        _cache.clear()
        db.DB_PATH = self.old_db_path
        self.tmpdir.cleanup()

    def service(self):
        for name in (
            "resolve_period",
            "get_dashboard_data",
            "get_period_receipts",
            "rank_action_queue",
            "build_briefing",
            "build_month_story",
            "get_available_receipt_months",
            "resolve_story_month",
        ):
            self.assertTrue(hasattr(dashboard, name), f"missing dashboard API: {name}")
        return dashboard

    def add_receipt(self, receipt_date, total, number, store="RIMI", items=()):
        with db.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO receipts (date, store, total, receipt_number) VALUES (?, ?, ?, ?)",
                (receipt_date, store, total, number),
            )
            receipt_id = cursor.lastrowid
            for index, item in enumerate(items):
                conn.execute(
                    """
                    INSERT INTO items (
                        receipt_id, name, normalized_name, quantity, price, line_total,
                        unit_price, quantity_unit, package_size, package_unit,
                        normalized_unit_price, normalized_price_unit, price_parse_source,
                        price_parse_confidence, category, category_source
                    ) VALUES (?, ?, ?, 1, ?, ?, ?, 'piece', 1, 'piece', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        receipt_id,
                        item.get("name", f"Item {index}"),
                        item.get("normalized_name", f"item {index}"),
                        item.get("price", total),
                        item.get("line_total"),
                        item.get("line_total"),
                        item.get("normalized_unit_price"),
                        item.get("normalized_price_unit"),
                        item.get("source", "package_name"),
                        item.get("confidence"),
                        item.get("category", "прочее"),
                        item.get("category_source", "fallback"),
                    ),
                )
            conn.commit()
        return receipt_id

    def test_period_boundaries(self):
        service = self.service()
        as_of = date(2026, 7, 14)

        current = service.resolve_period("current_month", as_of)
        self.assertEqual((current.start, current.end), (date(2026, 7, 1), date(2026, 7, 15)))
        self.assertEqual(
            (current.previous_start, current.previous_end),
            (date(2026, 6, 1), date(2026, 6, 15)),
        )

        previous = service.resolve_period("previous_month", as_of)
        self.assertEqual((previous.start, previous.end), (date(2026, 6, 1), date(2026, 7, 1)))
        self.assertEqual(
            (previous.previous_start, previous.previous_end),
            (date(2026, 5, 1), date(2026, 6, 1)),
        )

        rolling = service.resolve_period("last_30_days", as_of)
        self.assertEqual((rolling.start, rolling.end), (date(2026, 6, 15), date(2026, 7, 15)))
        self.assertEqual(
            (rolling.previous_start, rolling.previous_end),
            (date(2026, 5, 16), date(2026, 6, 15)),
        )

        all_time = service.resolve_period("all_time", as_of)
        self.assertIsNone(all_time.start)
        self.assertIsNone(all_time.previous_start)
        self.assertIsNone(all_time.previous_end)
        self.assertEqual(all_time.end, date(2026, 7, 15))

        fallback = service.resolve_period("not-real", as_of)
        self.assertEqual(fallback.key, "current_month")

        selected_month = service.resolve_period("month:2026-05", as_of)
        self.assertEqual(selected_month.label, "Май 2026")
        self.assertEqual(
            (selected_month.start, selected_month.end),
            (date(2026, 5, 1), date(2026, 6, 1)),
        )
        self.assertEqual(
            (selected_month.previous_start, selected_month.previous_end),
            (date(2026, 4, 1), date(2026, 5, 1)),
        )

    def test_period_boundaries_cross_from_january_to_previous_year(self):
        service = self.service()
        as_of = date(2027, 1, 10)

        current = service.resolve_period("current_month", as_of)
        previous = service.resolve_period("previous_month", as_of)

        self.assertEqual((current.start, current.end), (date(2027, 1, 1), date(2027, 1, 11)))
        self.assertEqual(
            (current.previous_start, current.previous_end),
            (date(2026, 12, 1), date(2026, 12, 11)),
        )
        self.assertEqual(
            (previous.start, previous.end),
            (date(2026, 12, 1), date(2027, 1, 1)),
        )

    def test_available_story_months_are_data_backed_sorted_and_validated(self):
        service = self.service()
        self.add_receipt("2026-01-10", 10, "jan")
        self.add_receipt("2026-05-10", 20, "may")
        self.add_receipt("2026-07-10", 30, "jul")
        self.add_receipt("not-a-date", 99, "invalid")

        months = service.get_available_receipt_months()
        self.assertEqual([month["key"] for month in months], ["2026-07", "2026-05", "2026-01"])
        self.assertEqual(months[1]["label"], "Май 2026")
        self.assertEqual(months[1]["receipt_count"], 1)
        self.assertEqual(
            service.resolve_story_month("2026-05", months, as_of=date(2026, 7, 21)),
            "2026-05",
        )
        self.assertEqual(
            service.resolve_story_month("2025-12", months, as_of=date(2026, 7, 21)),
            "2026-07",
        )
        self.assertEqual(
            service.resolve_story_month("not-a-month", months, as_of=date(2026, 8, 21)),
            "2026-07",
        )

    def test_selected_month_rebuilds_story_and_archive_month_context(self):
        service = self.service()
        may_id = self.add_receipt("2026-05-08", 42, "may-story", store="MAXIMA")
        self.add_receipt("2026-07-08", 99, "july-story", store="RIMI")

        result = service.get_dashboard_data("month:2026-05", as_of=date(2026, 7, 21))
        story = result["month_story"]
        receipts = service.get_period_receipts(result["period"])

        self.assertEqual(story["month"]["display_label"], "Май 2026")
        self.assertEqual(story["total"], 42.0)
        self.assertEqual(story["receipt_count"], 1)
        self.assertEqual([receipt["id"] for receipt in story["highlighted_receipts"]], [may_id])
        self.assertEqual([receipt["id"] for receipt in receipts], [may_id])
        self.assertEqual(result["receipt_month"]["month_label"], "2026-05")
        self.assertEqual(result["receipt_month"]["spend"], 42.0)
        self.assertTrue(result["receipt_month"]["is_selected_month"])
        self.assertFalse(result["receipt_month"]["forecast"]["eligible"])

    def test_story_signature_is_independent_of_period_selector_key(self):
        service = self.service()
        self.add_receipt("2026-07-08", 42, "same-story")

        current = service.get_dashboard_data(
            "current_month", as_of=date(2026, 7, 31)
        )["month_story"]
        explicit = service.get_dashboard_data(
            "month:2026-07", as_of=date(2026, 7, 31)
        )["month_story"]

        self.assertEqual(current["story_signature"], explicit["story_signature"])

    def test_queries_respect_period_boundaries_and_ignore_invalid_dates(self):
        service = self.service()
        fixtures = (
            ("2026-05-15", 1),
            ("2026-05-16", 2),
            ("2026-06-14", 4),
            ("2026-06-15", 8),
            ("2026-06-30", 16),
            ("2026-07-01", 32),
            ("2026-07-14", 64),
            ("2026-07-15", 128),
            ("", 256),
            ("not-a-date", 512),
        )
        for index, (receipt_date, total) in enumerate(fixtures):
            self.add_receipt(receipt_date, total, f"boundary-{index}")

        as_of = date(2026, 7, 14)
        self.assertEqual(service.get_dashboard_data("current_month", as_of=as_of)["summary"]["spend"], 96.0)
        self.assertEqual(service.get_dashboard_data("previous_month", as_of=as_of)["summary"]["spend"], 28.0)
        self.assertEqual(service.get_dashboard_data("last_30_days", as_of=as_of)["summary"]["spend"], 120.0)
        self.assertEqual(service.get_dashboard_data("all_time", as_of=as_of)["summary"]["spend"], 127.0)

    def test_comparison_uses_receipt_totals_and_previous_equivalent_period(self):
        service = self.service()
        self.add_receipt("2026-06-01", 10, "june-1", items=({"price": 900},))
        self.add_receipt("2026-06-14", 40, "june-14", items=({"price": 900},))
        self.add_receipt("2026-06-15", 999, "june-out")
        self.add_receipt("2026-07-01", 30, "july-1", items=({"price": 1},))
        self.add_receipt("2026-07-14", 70, "july-14", items=({"price": 1},))
        self.add_receipt("2026-07-15", 999, "july-out")

        result = service.get_dashboard_data("current_month", as_of=date(2026, 7, 14))

        self.assertEqual(result["summary"]["spend"], 100.0)
        self.assertEqual(result["summary"]["receipt_count"], 2)
        self.assertEqual(result["comparison"]["previous_spend"], 50.0)
        self.assertEqual(result["comparison"]["absolute_delta"], 50.0)
        self.assertEqual(result["comparison"]["percentage_delta"], 100.0)

    def test_zero_previous_spend_has_no_percentage(self):
        service = self.service()
        self.add_receipt("2026-07-10", 25, "only-current")
        result = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))
        self.assertEqual(result["comparison"]["absolute_delta"], 25.0)
        self.assertIsNone(result["comparison"]["percentage_delta"])

    def test_briefing_conclusion_reports_increased_spend_cautiously(self):
        self.add_receipt("2026-06-10", 20, "previous")
        self.add_receipt("2026-07-09", 25, "current-1")
        self.add_receipt("2026-07-10", 35, "current-2")

        briefing = self.service().get_dashboard_data(
            "current_month", as_of=date(2026, 7, 10)
        )["briefing"]

        self.assertIn("выросли на 40.00 €", briefing["conclusion"])
        self.assertIn("совпало", briefing["conclusion"])
        self.assertNotIn("объясняет", briefing["conclusion"])

    def test_briefing_conclusion_reports_decreased_spend(self):
        self.add_receipt("2026-06-10", 80, "previous")
        self.add_receipt("2026-07-10", 30, "current")

        briefing = self.service().get_dashboard_data(
            "current_month", as_of=date(2026, 7, 10)
        )["briefing"]

        self.assertIn("снизились на 50.00 €", briefing["conclusion"])

    def test_briefing_uses_intentional_quiet_mode_for_stable_period(self):
        self.add_receipt("2026-06-10", 30, "previous")
        self.add_receipt("2026-07-10", 31, "current")

        briefing = self.service().get_dashboard_data(
            "current_month", as_of=date(2026, 7, 10)
        )["briefing"]

        self.assertTrue(briefing["quiet"])
        self.assertEqual(briefing["conclusion"], "Все выглядит стабильно за выбранный период.")
        self.assertEqual(briefing["findings"], [])

    def test_briefing_does_not_infer_change_without_comparison_data(self):
        self.add_receipt("2026-07-10", 30, "current")

        briefing = self.service().get_dashboard_data(
            "current_month", as_of=date(2026, 7, 10)
        )["briefing"]

        self.assertFalse(briefing["has_baseline"])
        self.assertIn("не хватает данных прошлого периода", briefing["conclusion"])
        self.assertNotIn("выросли", briefing["conclusion"])

    def test_briefing_findings_are_deterministic_capped_and_traceable(self):
        service = self.service()
        window = service.resolve_period("current_month", date(2026, 7, 10))
        findings = service.build_briefing(
            window,
            {"spend": 100.0, "receipt_count": 4},
            {
                "previous_spend": 50.0,
                "previous_receipt_count": 2,
                "absolute_delta": 50.0,
                "percentage_delta": 100.0,
            },
            [{"category": "молочные продукты и альтернативы", "current": 60.0, "previous": 10.0, "delta": 50.0}],
            [
                {
                    "key": "category_conflicts", "severity": "critical", "count": 2,
                    "title": "Конфликты категорий", "explanation": "Есть конфликт.",
                    "href": "/products/review?filter=conflict&sort=conflicts", "action": "Разобрать",
                },
                {
                    "key": "low_confidence_prices", "severity": "high", "count": 3,
                    "title": "Низкая уверенность цены", "explanation": "Мало уверенности.",
                    "href": "/data-quality/prices?filter=low_confidence", "action": "Проверить",
                },
            ],
        )["findings"]

        self.assertEqual(len(findings), 3)
        self.assertEqual(
            [finding["key"] for finding in findings],
            ["category_movement", "visit_frequency", "category_conflicts"],
        )
        for finding in findings:
            self.assertTrue(finding["comparison"])
            self.assertTrue(finding["reason"])
            self.assertTrue(finding["evidence_summary"])
            self.assertTrue(finding["decision"])
            self.assertTrue(finding["links"][0]["href"].startswith("/"))
        self.assertIn("category=%D0%BC%D0%BE%D0%BB%D0%BE%D1%87%D0%BD%D1%8B%D0%B5+%D0%BF%D1%80%D0%BE%D0%B4%D1%83%D0%BA%D1%82%D1%8B+%D0%B8+%D0%B0%D0%BB%D1%8C%D1%82%D0%B5%D1%80%D0%BD%D0%B0%D1%82%D0%B8%D0%B2%D1%8B", findings[0]["links"][0]["href"])
        self.assertEqual(findings[2]["links"][0]["href"], "/products/review?filter=conflict&sort=conflicts")

    def test_empty_database_is_safe(self):
        service = self.service()
        result = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))
        self.assertEqual(result["summary"], {"spend": 0.0, "receipt_count": 0})
        self.assertIsNone(result["forecast"])
        self.assertEqual(result["recent_receipts"], [])
        self.assertEqual(result["action_queue"], [])
        self.assertTrue(result["briefing"]["quiet"])
        self.assertEqual(result["briefing"]["findings"], [])
        story = result["month_story"]
        self.assertEqual(story["receipt_count"], 0)
        self.assertEqual(story["timeline_events"], [])
        self.assertEqual(story["highlighted_receipts"], [])
        self.assertEqual(story["grouped_remainder"]["count"], 0)
        self.assertEqual(story["insight"]["type"], "calm_month")
        self.assertEqual(story["insight"]["destination_link"], "/upload")

    def test_month_story_contract_highlights_and_signature_are_stable(self):
        service = self.service()
        ids = []
        for day in range(1, 13):
            ids.append(self.add_receipt(f"2026-07-{day:02d}", day, f"story-{day}"))

        first = service.get_dashboard_data("current_month", as_of=date(2026, 7, 14))["month_story"]
        second = service.get_dashboard_data("current_month", as_of=date(2026, 7, 14))["month_story"]

        self.assertEqual(first["month"]["key"], "current_month")
        self.assertEqual(first["total"], 78.0)
        self.assertEqual(first["receipt_count"], 12)
        self.assertEqual(first["actual_period"], {"start": "2026-07-01", "end": "2026-07-12"})
        self.assertEqual(len(first["timeline_events"]), 12)
        self.assertGreaterEqual(len(first["highlighted_receipts"]), 4)
        self.assertLessEqual(len(first["highlighted_receipts"]), 6)
        self.assertEqual(
            first["grouped_remainder"]["count"] + len(first["highlighted_receipts"]),
            12,
        )
        self.assertEqual(first["story_signature"], second["story_signature"])
        self.assertEqual(len(first["story_signature"]), 64)
        self.assertLessEqual(len(first["insight"]["evidence_events"]), 3)

    def test_month_story_uses_all_receipts_when_there_are_at_most_three(self):
        service = self.service()
        for day in range(1, 4):
            self.add_receipt(f"2026-07-{day:02d}", day * 10, f"few-{day}")
        story = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))["month_story"]
        self.assertEqual(len(story["highlighted_receipts"]), 3)
        self.assertEqual(story["grouped_remainder"]["count"], 0)

    def test_month_story_groups_large_timeline_by_real_dates(self):
        service = self.service()
        for index in range(70):
            day = index % 10 + 1
            self.add_receipt(f"2026-07-{day:02d}", 1, f"many-{index}")
        story = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))["month_story"]
        self.assertEqual(len(story["highlighted_receipts"]), 6)
        self.assertEqual(len(story["timeline_events"]), 10)
        self.assertTrue(all(event["type"] == "day_group" for event in story["timeline_events"]))
        self.assertEqual(sum(event["count"] for event in story["timeline_events"]), 70)

    def test_month_story_category_impact_caps_ratio_and_keeps_raw_ratio(self):
        service = self.service()
        for day in range(1, 4):
            self.add_receipt(
                f"2026-06-{day:02d}", 50, f"prev-{day}",
                items=(
                    {"name": f"Food {day}", "price": 100 / 3, "line_total": 100 / 3, "category": "еда"},
                    {"name": f"Home {day}", "price": 50 / 3, "line_total": 50 / 3, "category": "дом"},
                ),
            )
        # Total grows by 20, while one category grows by 40 and another falls by 20.
        for day in range(1, 4):
            self.add_receipt(
                f"2026-07-{day:02d}", 170 / 3, f"curr-{day}",
                items=(
                    {"name": f"Food now {day}", "price": 140 / 3, "line_total": 140 / 3, "category": "еда"},
                    {"name": f"Home now {day}", "price": 10, "line_total": 10, "category": "дом"},
                ),
            )
        story = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))["month_story"]
        insight = story["insight"]
        self.assertEqual(insight["type"], "category_impact")
        self.assertEqual(insight["impact_ratio"], 1)
        self.assertGreater(insight["raw_impact_ratio"], 1)
        self.assertIn("100%", insight["metric_confirmation"])

    def test_month_story_rejects_category_impact_when_coverage_is_low(self):
        service = self.service()
        for month, amount in (("06", 20), ("07", 50)):
            for day in range(1, 4):
                self.add_receipt(
                    f"2026-{month}-{day:02d}", amount, f"coverage-{month}-{day}",
                    items=({"name": "Known", "price": 5, "line_total": 5, "category": "еда"},),
                )
        insight = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))["month_story"]["insight"]
        self.assertNotEqual(insight["type"], "category_impact")

    def test_month_story_can_select_negative_category_impact(self):
        service = self.service()
        for day in range(1, 4):
            self.add_receipt(
                f"2026-06-{day:02d}", 50, f"negative-prev-{day}",
                items=({"name": "Clothes", "price": 50, "line_total": 50, "category": "бытовое и личный уход"},),
            )
            self.add_receipt(
                f"2026-07-{day:02d}", 20, f"negative-curr-{day}",
                items=({"name": "Clothes", "price": 20, "line_total": 20, "category": "бытовое и личный уход"},),
            )
        insight = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))["month_story"]["insight"]
        self.assertEqual(insight["type"], "category_impact")
        self.assertLess(insight["metric_value"], 0)
        self.assertIn("ниже", insight["metric_confirmation"])

    def test_month_story_price_requires_confidence_and_comparable_history(self):
        service = self.service()
        for day in (1, 3, 5):
            self.add_receipt(
                f"2026-06-{day:02d}", 10, f"price-prev-{day}",
                items=({"name": "Milk", "normalized_name": "milk", "price": 10, "line_total": 10,
                        "normalized_unit_price": 2, "normalized_price_unit": "eur_per_l", "confidence": 0.95},),
            )
        self.add_receipt(
            "2026-07-05", 10, "price-current-low",
            items=({"name": "Milk", "normalized_name": "milk", "price": 10, "line_total": 10,
                    "normalized_unit_price": 4, "normalized_price_unit": "eur_per_l", "confidence": 0.70},),
        )
        low = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))["month_story"]["insight"]
        self.assertNotEqual(low["type"], "normalized_price")

        with db.get_connection() as conn:
            conn.execute("UPDATE items SET price_parse_confidence = 0.95 WHERE receipt_id = (SELECT id FROM receipts WHERE receipt_number = 'price-current-low')")
            conn.commit()
        high = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))["month_story"]["insight"]
        self.assertEqual(high["type"], "normalized_price")

    def test_month_story_price_can_use_earlier_current_period_observations(self):
        service = self.service()
        self.add_receipt(
            "2026-06-20", 2, "price-prior",
            items=({"name": "Milk", "price": 2, "line_total": 2,
                    "normalized_unit_price": 2, "normalized_price_unit": "eur_per_piece", "confidence": 0.95},),
        )
        for day in (1, 2):
            self.add_receipt(
                f"2026-07-{day:02d}", 2, f"price-current-history-{day}",
                items=({"name": "Milk", "price": 2, "line_total": 2,
                        "normalized_unit_price": 2, "normalized_price_unit": "eur_per_piece", "confidence": 0.95},),
            )
        self.add_receipt(
            "2026-07-05", 5, "price-current-signal",
            items=({"name": "Milk", "price": 5, "line_total": 5,
                    "normalized_unit_price": 5, "normalized_price_unit": "eur_per_piece", "confidence": 0.95},),
        )

        insight = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))["month_story"]["insight"]

        self.assertEqual(insight["type"], "normalized_price")
        self.assertEqual(insight["metric_value"], 150.0)

    def test_month_story_prioritizes_unusual_purchase_with_enough_history(self):
        service = self.service()
        for day in range(1, 6):
            self.add_receipt(
                f"2026-06-{day:02d}", 10, f"usual-{day}",
                items=({"name": "Coffee", "normalized_name": "coffee", "price": 10, "line_total": 10},),
            )
        current_id = self.add_receipt(
            "2026-07-05", 60, "unusual-current",
            items=({"name": "Coffee", "normalized_name": "coffee", "price": 60, "line_total": 60},),
        )
        insight = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))["month_story"]["insight"]
        self.assertEqual(insight["type"], "unusual_purchase")
        self.assertEqual(insight["evidence_events"][0]["id"], current_id)
        self.assertNotIn("причин", insight["title"].lower())

    def test_month_story_selects_visit_frequency_when_thresholds_are_met(self):
        service = self.service()
        for day in (1, 4, 7):
            self.add_receipt(f"2026-06-{day:02d}", 10, f"visits-prev-{day}")
        for day in range(1, 8):
            self.add_receipt(f"2026-07-{day:02d}", 10, f"visits-current-{day}")
        insight = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))["month_story"]["insight"]
        self.assertEqual(insight["type"], "visit_frequency")
        self.assertEqual(insight["metric_value"], 4)
        self.assertLessEqual(len(insight["evidence_events"]), 3)

    def test_month_story_near_zero_change_does_not_become_frequency_story(self):
        service = self.service()
        for day in (1, 4, 7):
            self.add_receipt(f"2026-06-{day:02d}", 10, f"quiet-prev-{day}")
        for day, total in enumerate((5, 5, 5, 4, 4, 4, 4), start=1):
            self.add_receipt(f"2026-07-{day:02d}", total, f"quiet-current-{day}")
        insight = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))["month_story"]["insight"]
        self.assertEqual(insight["type"], "calm_month")
        self.assertIn("+1.00 €", insight["metric_confirmation"])

    def test_forecast_uses_daily_pace_when_eligible(self):
        service = self.service()
        self.add_receipt("2026-07-01", 20, "forecast-1")
        self.add_receipt("2026-07-05", 30, "forecast-2")
        self.add_receipt("2026-07-10", 50, "forecast-3")

        result = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))

        self.assertEqual(result["forecast"]["amount"], 310.0)
        self.assertEqual(result["forecast"]["elapsed_days"], 10)
        self.assertEqual(result["forecast"]["days_in_month"], 31)
        self.assertIsNone(
            service.get_dashboard_data("previous_month", as_of=date(2026, 8, 10))["forecast"]
        )

    def test_forecast_hidden_with_too_few_days_or_receipts(self):
        service = self.service()
        for index in range(3):
            self.add_receipt("2026-07-06", 10, f"early-{index}")
        self.assertIsNone(
            service.get_dashboard_data("current_month", as_of=date(2026, 7, 6))["forecast"]
        )

        with db.get_connection() as conn:
            conn.execute("DELETE FROM receipts")
            conn.commit()
        self.add_receipt("2026-07-01", 30, "few-1")
        self.add_receipt("2026-07-10", 70, "few-2")
        self.assertIsNone(
            service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))["forecast"]
        )

    def test_receipt_month_summary_uses_real_month_data_without_join_duplication(self):
        service = self.service()
        self.add_receipt(
            "2026-07-01",
            10,
            "month-1",
            items=(
                {"name": "A", "price": 4, "line_total": 4},
                {"name": "B", "price": 6, "line_total": 6},
            ),
        )
        self.add_receipt("2026-07-02", 20, "month-2", items=({"name": "C", "price": 20},))

        result = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))["receipt_month"]

        self.assertEqual(result["spend"], 30.0)
        self.assertEqual(result["receipt_count"], 2)
        self.assertEqual(result["item_line_count"], 3)

    def test_receipt_month_forecast_hidden_when_latest_receipt_is_stale(self):
        service = self.service()
        for day in (1, 2, 3):
            self.add_receipt(f"2026-07-{day:02d}", 10, f"stale-{day}", items=({"name": f"Item {day}", "price": 10},))

        forecast = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))["receipt_month"]["forecast"]

        self.assertFalse(forecast["eligible"])
        self.assertEqual(forecast["reason"], "Insufficient data for forecast")
        self.assertIn("latest_receipt_older_than_3_days", forecast["reasons"])

    def test_receipt_month_forecast_shows_current_pace_when_eligible(self):
        service = self.service()
        items = tuple({"name": f"Item {index}", "price": 2} for index in range(4))
        self.add_receipt("2026-07-01", 20, "pace-1", items=items)
        self.add_receipt("2026-07-05", 30, "pace-2", items=items)
        self.add_receipt("2026-07-10", 50, "pace-3", items=items)

        forecast = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))["receipt_month"]["forecast"]

        self.assertTrue(forecast["eligible"])
        self.assertEqual(forecast["amount"], 310.0)
        self.assertEqual(forecast["elapsed_days"], 10)

    def test_top_products_use_effective_identity_and_compare_only_same_normalized_unit(self):
        service = self.service()
        self.add_receipt(
            "2026-06-20",
            8,
            "prev",
            items=({"name": "Milk", "normalized_name": "milk", "price": 8, "line_total": 8, "normalized_unit_price": 2, "normalized_price_unit": "eur_per_l", "confidence": 1},),
        )
        self.add_receipt(
            "2026-07-05",
            10,
            "current",
            items=(
                {"name": "Milk", "normalized_name": "milk", "price": 10, "line_total": 10, "normalized_unit_price": 2.5, "normalized_price_unit": "eur_per_l", "confidence": 1},
                {"name": "Milk bad unit", "normalized_name": "milk bad unit", "price": 9, "line_total": 9, "normalized_unit_price": 9, "normalized_price_unit": "eur_per_kg", "confidence": 1},
            ),
        )

        products = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))["receipt_month"]["top_products"]
        by_name = {product["name"]: product for product in products}

        self.assertEqual(by_name["Milk"]["unit_label"], "EUR/l")
        self.assertEqual(by_name["Milk"]["change_percent"], 25.0)
        self.assertEqual(by_name["Milk bad unit"]["history_label"], "No comparable history")

    def test_action_queue_orders_caps_and_excludes_no_manual_rule(self):
        service = self.service()
        candidates = [
            {"key": "last", "priority": 9, "count": 1},
            {"key": "merge_suggestions", "priority": 4, "count": 2},
            {"key": "category_conflicts", "priority": 1, "count": 3},
            {"key": "no_manual_rule", "priority": 0, "count": 999},
            {"key": "uncategorized", "priority": 5, "count": 4},
            {"key": "price_warnings", "priority": 2, "count": 5},
            {"key": "supported-extra", "priority": 6, "count": 6},
        ]

        ranked = service.rank_action_queue(candidates)

        self.assertEqual(
            [item["key"] for item in ranked],
            ["category_conflicts", "price_warnings", "merge_suggestions", "uncategorized", "supported-extra"],
        )
        self.assertNotIn("no_manual_rule", {item["key"] for item in ranked})

    def test_action_queue_counts_match_filtered_destinations(self):
        service = self.service()
        self.add_receipt(
            "2026-07-01",
            20,
            "queue-1",
            items=(
                {"name": "Milk", "normalized_name": "milk", "category": "молочные продукты и альтернативы", "confidence": 1, "normalized_unit_price": 2, "normalized_price_unit": "eur_per_l"},
                {"name": "Milk", "normalized_name": "milk", "category": "безалкогольные напитки", "confidence": 1, "normalized_unit_price": 2, "normalized_price_unit": "eur_per_l"},
                {"name": "Bread", "normalized_name": "bread", "category": "хлеб и выпечка", "confidence": .5, "normalized_unit_price": 3, "normalized_price_unit": "eur_per_piece"},
                {"name": "Gold", "normalized_name": "gold", "category": "прочее", "confidence": 1, "normalized_unit_price": 20001, "normalized_price_unit": "eur_per_piece"},
            ),
        )

        result = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))
        queue = {item["key"]: item for item in result["action_queue"]}

        self.assertEqual(queue["category_conflicts"]["count"], 1)
        self.assertEqual(queue["category_conflicts"]["href"], "/products/review?filter=conflict&sort=conflicts")
        self.assertEqual(queue["low_confidence_prices"]["count"], 1)
        self.assertEqual(queue["low_confidence_prices"]["href"], "/data-quality/prices?filter=low_confidence")
        self.assertEqual(queue["suspicious_prices"]["count"], 1)
        self.assertEqual(queue["suspicious_prices"]["href"], "/data-quality/prices?filter=suspicious")
        self.assertEqual(queue["uncategorized"]["href"], "/products/review?filter=other")
        self.assertNotIn("no_manual_rule", queue)

    def test_recent_receipts_are_newest_first_and_limited_to_five(self):
        service = self.service()
        for day in range(1, 8):
            self.add_receipt(f"2026-07-{day:02d}", day, f"recent-{day}")

        result = service.get_dashboard_data("current_month", as_of=date(2026, 7, 10))

        self.assertEqual(len(result["recent_receipts"]), 5)
        self.assertEqual(
            [row["receipt_number"] for row in result["recent_receipts"]],
            ["recent-7", "recent-6", "recent-5", "recent-4", "recent-3"],
        )

    def test_dashboard_and_preserved_receipt_list_render(self):
        service = self.service()
        self.add_receipt(
            "2026-07-10",
            25,
            "route-1",
            store="MAXIMA",
            items=[{"name": "Receipt workspace item", "price": 25, "confidence": 0.95, "category": "мясо"}],
        )
        app = create_app()
        app.config["TESTING"] = True
        app.config["TODAY_PROVIDER"] = lambda: date(2026, 7, 14)
        client = app.test_client()

        overview = client.get("/")
        self.assertEqual(overview.status_code, 200)
        overview_html = overview.get_data(as_text=True)
        self.assertIn("Интеллектуальная сводка", overview_html)
        self.assertIn('class="home-document', overview_html)
        self.assertIn('data-story-act="month"', overview_html)
        self.assertIn('data-story-act="insight"', overview_html)
        self.assertIn('data-story-act="workspace"', overview_html)
        self.assertIn('id="story-month-title"', overview_html)
        self.assertIn('id="story-insight-title"', overview_html)
        self.assertIn('name="period"', overview_html)
        self.assertIn('name="store_search"', overview_html)
        self.assertIn('class="command-search-button"', overview_html)
        self.assertIn('href="/upload"', overview_html)
        self.assertIn('id="receiptTable"', overview_html)
        self.assertIn('href="/?view=receipts&amp;period=current_month"', overview_html)
        self.assertIn("25.00 €", overview_html)
        self.assertNotIn('class="dispatch"', overview_html)

        receipt_list = client.get("/?view=receipts&period=all_time&store_search=MAXIMA")
        self.assertEqual(receipt_list.status_code, 200)
        list_html = receipt_list.get_data(as_text=True)
        self.assertIn('id="searchInput"', list_html)
        self.assertIn('name="store_search"', list_html)
        self.assertIn('id="receiptTable"', list_html)
        self.assertIn('class="sort-button receipt-column-store"', list_html)
        self.assertIn('type="hidden" name="store_search" value="MAXIMA"', list_html)
        self.assertIn(
            'href="/receipt/1?return_to=/?view%3Dreceipts%26period%3Dall_time%26store_search%3DMAXIMA"',
            list_html,
        )
        self.assertIn('id="receipt-toggle-1"', list_html)
        self.assertIn('aria-expanded="false"', list_html)
        self.assertIn('aria-controls="receipt-detail-1"', list_html)
        self.assertIn('role="region"', list_html)
        self.assertIn('aria-labelledby="receipt-toggle-1"', list_html)
        self.assertIn("Receipt workspace item", list_html)
        self.assertIn("Сбросить фильтры", list_html)
        self.assertNotIn("Receipt Radar", list_html)
        self.assertNotIn("data-radar-reset", list_html)
        self.assertIn("receipt-summary-band", list_html)
        self.assertIn("receipt-register", list_html)
        self.assertIn("Сумма набора", list_html)
        self.assertNotIn("Receipt Workspace", list_html)
        self.assertNotIn("receipt-signal", list_html)
        self.assertNotIn("Вернуться к обзору", list_html)
        self.assertIn("MAXIMA", list_html)
        self.assertNotIn('class="home-document', list_html)
        self.assertNotIn('data-story-act="month"', list_html)
        self.assertNotIn("home-story.css", list_html)
        self.assertNotIn("searchInput.addEventListener('input'", list_html)

        analytics = client.get("/analytics?start=2026-07-01&end=2026-07-14&category=мясо%20и%20птица")
        analytics_html = analytics.get_data(as_text=True)
        self.assertRegex(analytics_html, r'id="startDate"[^>]+value="2026-07-01"')
        self.assertRegex(analytics_html, r'id="endDate"[^>]+value="2026-07-14"')
        self.assertIn('<option value="мясо и птица" selected>', analytics_html)

    def test_story_page_renders_grouped_remainder_and_real_evidence_links(self):
        service = self.service()
        for day in range(1, 4):
            self.add_receipt(
                f"2026-06-{day:02d}", 20, f"story-prev-{day}",
                items=({"name": "Одежда", "price": 20, "line_total": 20, "category": "бытовое и личный уход"},),
            )
        evidence_id = None
        for day in range(1, 8):
            evidence_id = self.add_receipt(
                f"2026-07-{day:02d}", 20, f"story-current-{day}", store="MAXIMA",
                items=({"name": "Одежда", "price": 20, "line_total": 20, "category": "бытовое и личный уход"},),
            )

        app = create_app()
        app.config["TESTING"] = True
        html = app.test_client().get("/").get_data(as_text=True)

        self.assertIn("Остальные 1 чек.", html)
        self.assertIn('class="story-evidence"', html)
        self.assertIn(f'href="/receipt/{evidence_id}"', html)
        self.assertIn("Открыть категорию", html)
        self.assertIn("category=", html)
        self.assertNotIn("raw_impact_ratio", html)
        self.assertNotIn("story_signature", html)


if __name__ == "__main__":
    unittest.main()
