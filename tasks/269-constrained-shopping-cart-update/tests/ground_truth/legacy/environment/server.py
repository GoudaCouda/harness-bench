#!/usr/bin/env python3
"""Synthetic loopback-published product catalog and cart service."""

from __future__ import annotations

import html
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from state_model import connect, load_json


DB_PATH = Path(os.environ.get("CASE_DB_PATH", "/run/state.sqlite"))
CATALOG_PATH = Path(os.environ.get("CASE_CATALOG_PATH", "/run/catalog.json"))
FIXED_TIME = os.environ.get("CASE_FIXED_TIME", "2026-07-20T08:00:00Z")


class Handler(BaseHTTPRequestHandler):
    server_version = "AuroraCatalog/1.0"

    def _json(self, status: int, payload: object) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _html(self, status: int, content: str) -> None:
        encoded = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json(HTTPStatus.OK, {"status": "ok", "fixed_time": FIXED_TIME})
            return
        if parsed.path in {"/", "/catalog"}:
            catalog = load_json(CATALOG_PATH)
            cards = []
            for product in catalog["products"]:
                variants = "、".join(
                    f"{item['size']}/{item['color']}"
                    for item in product["variants"]
                    if item["active"]
                )
                cards.append(
                    "<article class='product' data-product-id='{}'>"
                    "<h2>{}</h2><p>编号：{}</p><p>价格：¥{:.2f}</p>"
                    "<p>评分：{:.1f}</p><p>库存：{}</p><p>规格：{}</p></article>".format(
                        html.escape(product["product_id"]),
                        html.escape(product["name"]),
                        html.escape(product["product_id"]),
                        product["price_cents"] / 100,
                        product["rating_x10"] / 10,
                        product["inventory"],
                        html.escape(variants),
                    )
                )
            self._html(
                HTTPStatus.OK,
                "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
                "<title>晨星生活馆｜本地目录</title></head><body>"
                "<h1>晨星生活馆</h1><p>本页为固定的项目合成商品目录。</p>"
                + "".join(cards)
                + "</body></html>",
            )
            return
        if parsed.path == "/api/snapshot":
            self._json(
                HTTPStatus.OK,
                {
                    "page_title": "晨星生活馆｜本地目录",
                    "products": load_json(CATALOG_PATH)["products"],
                },
            )
            return
        if parsed.path == "/api/cart":
            user_id = parse_qs(parsed.query).get("user_id", [""])[0]
            with connect(DB_PATH) as connection:
                rows = connection.execute(
                    "SELECT product_id, quantity FROM cart_items "
                    "WHERE user_id = ? ORDER BY product_id",
                    (user_id,),
                ).fetchall()
            self._json(
                HTTPStatus.OK,
                {
                    "user_id": user_id,
                    "items": [dict(row) for row in rows],
                },
            )
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/cart/items":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            user_id = str(payload["user_id"])
            product_id = str(payload["product_id"])
            quantity = int(payload["quantity"])
            if quantity != 1:
                raise ValueError("quantity_must_equal_one")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        try:
            with connect(DB_PATH) as connection:
                if connection.execute(
                    "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
                ).fetchone() is None:
                    raise LookupError("unknown_user")
                product = connection.execute(
                    "SELECT inventory FROM products WHERE product_id = ?", (product_id,)
                ).fetchone()
                if product is None:
                    raise LookupError("unknown_product")
                if product["inventory"] < quantity:
                    raise LookupError("out_of_stock")
                connection.execute(
                    "INSERT INTO cart_items(user_id, product_id, quantity) VALUES (?, ?, ?) "
                    "ON CONFLICT(user_id, product_id) DO UPDATE SET "
                    "quantity = cart_items.quantity + excluded.quantity",
                    (user_id, product_id, quantity),
                )
                connection.execute(
                    "INSERT INTO audit_log(event_type, user_id, product_id, quantity, event_time) "
                    "VALUES ('cart_add', ?, ?, ?, ?)",
                    (user_id, product_id, quantity, FIXED_TIME),
                )
                connection.commit()
        except LookupError as exc:
            self._json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            return
        self._json(
            HTTPStatus.CREATED,
            {"status": "added", "user_id": user_id, "product_id": product_id, "quantity": 1},
        )

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    bind_host = os.environ.get("CASE_BIND_HOST", "127.0.0.1")
    port = int(os.environ.get("CASE_PORT", "8000"))
    server = ThreadingHTTPServer((bind_host, port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
