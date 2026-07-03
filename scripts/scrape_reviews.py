#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрапер отзывов «Фотостудия на Остоженке» с Яндекс Карт.
Разбирает микроразметку schema.org (aggregateRating + review) и пишет reviews.json.
Выход с кодом 1, если данные получить не удалось (страница заблокирована/пустая) —
это сигнал для GitHub Actions повторить попытку на следующий день.
"""
import sys, os, json, time, argparse, datetime
from bs4 import BeautifulSoup

URL = "https://yandex.ru/maps/org/fotostudiya_na_ostozhenke/15220662082/reviews/"
MAX_REVIEWS = 20
MONTHS = {1:"января",2:"февраля",3:"марта",4:"апреля",5:"мая",6:"июня",
          7:"июля",8:"августа",9:"сентября",10:"октября",11:"ноября",12:"декабря"}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def fetch(url, attempts=4):
    """Скачать HTML. requests, если есть; иначе urllib. С повторами."""
    try:
        import requests
        get = lambda u: requests.get(u, headers=HEADERS, timeout=30).text
    except ImportError:
        import urllib.request
        def get(u):
            req = urllib.request.Request(u, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
    last = ""
    for i in range(attempts):
        try:
            html = get(url)
            # признак, что пришла реальная страница с отзывами, а не капча/заглушка
            if 'itemprop="review"' in html.lower() or 'itemprop="reviewbody"' in html.lower():
                return html
            last = "нет разметки отзывов в ответе (возможна капча)"
        except Exception as e:
            last = str(e)
        time.sleep(5 * (i + 1))
    raise SystemExit(f"[scrape] не удалось получить страницу: {last}")

def parse(html):
    soup = BeautifulSoup(html, "html.parser")

    agg = soup.find(attrs={"itemprop": "aggregateRating"})
    if not agg:
        raise SystemExit("[scrape] не найден блок aggregateRating")
    rv_meta = agg.find("meta", attrs={"itemprop": "ratingValue"})
    cnt_meta = agg.find("meta", attrs={"itemprop": "reviewCount"})
    rating = round(float(rv_meta["content"]), 1) if rv_meta else None
    total = int(cnt_meta["content"]) if cnt_meta else None

    reviews = []
    for rev in soup.find_all(attrs={"itemprop": "review"}):
        author = rev.find(attrs={"itemprop": "author"})
        name = author.get_text(" ", strip=True) if author else ""

        body = rev.find(attrs={"itemprop": "reviewBody"})
        text = body.get_text(" ", strip=True) if body else ""
        text = " ".join(text.split())  # схлопнуть пробелы/переносы

        rmeta = rev.find("meta", attrs={"itemprop": "ratingValue"})
        try:
            r = int(round(float(rmeta["content"]))) if rmeta else 5
        except Exception:
            r = 5

        d = ""
        dmeta = rev.find("meta", attrs={"itemprop": "datePublished"})
        if dmeta and dmeta.get("content"):
            try:
                dt = datetime.datetime.fromisoformat(dmeta["content"].replace("Z", "+00:00"))
                d = f"{dt.day} {MONTHS[dt.month]} {dt.year}"
            except Exception:
                d = ""

        if name and text:
            reviews.append({"name": name, "r": r, "d": d, "t": text})

    return rating, total, reviews

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="разобрать локальный HTML-файл вместо запроса (для теста)")
    ap.add_argument("--out", default="reviews.json")
    args = ap.parse_args()

    html = open(args.html, encoding="utf-8").read() if args.html else fetch(URL)
    rating, total, reviews = parse(html)

    # валидация: без этого не перезаписываем данные
    if rating is None or len(reviews) < 5:
        raise SystemExit(f"[scrape] недостаточно данных: rating={rating}, отзывов={len(reviews)}")

    data = {
        "rating": rating,
        "total": total if total else len(reviews),
        "updated": datetime.date.today().isoformat(),
        "source": URL,
        "reviews": reviews[:MAX_REVIEWS],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[scrape] OK: рейтинг {rating}, всего {data['total']}, записано карточек {len(data['reviews'])}")

if __name__ == "__main__":
    main()
