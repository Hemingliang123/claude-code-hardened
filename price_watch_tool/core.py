"""价格采集、清洗、对比与报告生成核心逻辑。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from html import escape, unescape
import json
import math
from pathlib import Path
import re
from statistics import mean
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

from .sample_data import TREND_DATES, get_sample_items

PLATFORM_LABELS = {
    "jd": "京东",
    "taobao": "淘宝",
    "pdd": "拼多多",
}

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)
LIVE_REQUEST_TIMEOUT = 12


class LiveCollectionUnavailable(RuntimeError):
    """当前未接入真实平台会话或官方 API。"""


@dataclass(slots=True)
class ProductRecord:
    platform: str
    keyword: str
    title: str
    price: float
    sales: int
    shop: str
    shop_rating: float
    url: str
    price_history: list[float]
    value_score: float = 0.0
    recommendation: str = ""

    @property
    def platform_label(self) -> str:
        return PLATFORM_LABELS.get(self.platform, self.platform.upper())

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["platform_label"] = self.platform_label
        return payload


class ProviderBase:
    platform: str = ""
    label: str = ""

    def collect(self, keyword: str, limit: int = 5, mode: str = "sample") -> list[ProductRecord]:
        if mode == "sample":
            return self._collect_sample(keyword=keyword, limit=limit)
        if mode == "live":
            return self._collect_live(keyword=keyword, limit=limit)
        raise ValueError(f"不支持的采集模式: {mode}")

    def _collect_sample(self, keyword: str, limit: int) -> list[ProductRecord]:
        records: list[ProductRecord] = []
        for raw in get_sample_items(platform=self.platform, keyword=keyword, limit=limit):
            records.append(
                ProductRecord(
                    platform=self.platform,
                    keyword=keyword,
                    title=raw["title"],
                    price=float(raw["price"]),
                    sales=int(raw["sales"]),
                    shop=raw["shop"],
                    shop_rating=float(raw["shop_rating"]),
                    url=raw["url"],
                    price_history=[float(value) for value in raw["price_history"]],
                )
            )
        return records

    def _collect_live(self, keyword: str, limit: int) -> list[ProductRecord]:
        raise LiveCollectionUnavailable(
            f"{self.label} live 模式未接入。当前实现默认提供 sample 演示链路；"
            "若需要真实抓取，请在该 provider 中接入官方 API 或浏览器自动化会话。"
        )

    def _request_live_page(self, url: str, params: dict[str, str | int] | None = None) -> tuple[str, str]:
        query = urlencode(params or {}, doseq=True)
        target_url = f"{url}?{query}" if query else url
        request = Request(
            target_url,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
        )
        opener = build_opener(ProxyHandler())
        try:
            with opener.open(request, timeout=LIVE_REQUEST_TIMEOUT) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                body = response.read().decode(charset, errors="replace")
                return response.geturl(), body
        except HTTPError as exc:
            raise LiveCollectionUnavailable(
                f"{self.label} live 请求失败，HTTP {exc.code}: {target_url}"
            ) from exc
        except URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise LiveCollectionUnavailable(
                f"{self.label} live 请求失败，网络不可用: {reason}"
            ) from exc


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _parse_price_text(price_text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)", price_text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_quoted_json(text: str, pattern: str) -> dict | None:
    match = re.search(pattern, text, flags=re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _raise_live_unavailable(label: str, reason: str, final_url: str) -> None:
    raise LiveCollectionUnavailable(f"{label} live 已发起真实请求，但{reason}。最终地址: {final_url}")


class JdProvider(ProviderBase):
    platform = "jd"
    label = "京东"

    def _collect_live(self, keyword: str, limit: int) -> list[ProductRecord]:
        final_url, html = self._request_live_page(
            "https://search.jd.com/Search",
            params={"keyword": keyword},
        )
        if "passport.jd.com" in final_url:
            _raise_live_unavailable(self.label, "被重定向到登录页", final_url)
        if 'id="J_goodsList"' not in html and 'class="gl-item"' not in html:
            _raise_live_unavailable(
                self.label,
                "当前返回为前端骨架页或动态渲染页，未暴露可稳定解析的商品列表",
                final_url,
            )
        _raise_live_unavailable(
            self.label,
            "当前匿名页面结构未稳定暴露价格与店铺字段，暂未接入官方 API 凭证",
            final_url,
        )


class TaobaoProvider(ProviderBase):
    platform = "taobao"
    label = "淘宝"

    def _collect_live(self, keyword: str, limit: int) -> list[ProductRecord]:
        final_url, html = self._request_live_page(
            "https://s.taobao.com/search",
            params={"q": keyword},
        )
        if "login.taobao.com" in final_url:
            _raise_live_unavailable(self.label, "被重定向到登录页", final_url)

        item_cards = re.findall(
            (
                r'<a[^>]+href="(?P<url>//item\.taobao\.com/item\.htm[^"]+)"[^>]*>'
                r'(?P<block>.*?)</a>'
            ),
            html,
            flags=re.S,
        )
        records: list[ProductRecord] = []
        for raw_url, block in item_cards:
            title = _normalize_whitespace(re.sub(r"<[^>]+>", " ", block))
            price = _parse_price_text(block)
            if not title or price is None:
                continue
            records.append(
                ProductRecord(
                    platform=self.platform,
                    keyword=keyword,
                    title=title,
                    price=price,
                    sales=0,
                    shop="未知店铺",
                    shop_rating=0.0,
                    url=f"https:{raw_url}" if raw_url.startswith("//") else raw_url,
                    price_history=[price for _ in TREND_DATES],
                )
            )
            if len(records) >= limit:
                break

        if records:
            return records

        if '"routePath":"/mainSearch"' in html or "请不要禁用JS" in html:
            _raise_live_unavailable(
                self.label,
                "当前返回为 CSR 骨架页，真实商品列表依赖浏览器会话与后续动态接口",
                final_url,
            )

        search_result = _extract_quoted_json(
            html,
            r"window\.__SEARCH_RESULT__\s*=\s*(\{.*?\})\s*;</script>",
        )
        if search_result:
            _raise_live_unavailable(
                self.label,
                "已发现预载状态入口，但当前页面未包含可直接落库的标准商品字段",
                final_url,
            )

        _raise_live_unavailable(
            self.label,
            "未解析到稳定商品卡片，当前需登录态或浏览器 API 回放才能继续",
            final_url,
        )


class PddProvider(ProviderBase):
    platform = "pdd"
    label = "拼多多"

    def _collect_live(self, keyword: str, limit: int) -> list[ProductRecord]:
        final_url, html = self._request_live_page(
            "https://mobile.yangkeduo.com/search_result.html",
            params={"search_key": keyword},
        )
        if "/login.html" in final_url:
            _raise_live_unavailable(self.label, "被重定向到登录页", final_url)
        if 'id="main"' in html and "__SSR_STREAM_END__" in html:
            _raise_live_unavailable(
                self.label,
                "当前返回为移动端壳页面，商品数据需要后续 JS 拉取",
                final_url,
            )
        _raise_live_unavailable(
            self.label,
            "匿名访问未返回可稳定解析的商品列表，暂未接入商家 API 凭证",
            final_url,
        )


PROVIDERS = {
    "jd": JdProvider(),
    "taobao": TaobaoProvider(),
    "pdd": PddProvider(),
}


def normalize_title(title: str) -> str:
    return "".join(ch.lower() for ch in title if ch.isalnum())


def repair_mojibake(text: str) -> str:
    """修复常见的 UTF-8 被按 Latin-1 解释后的乱码。"""

    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    return repaired


def deduplicate_records(records: Iterable[ProductRecord]) -> list[ProductRecord]:
    unique: dict[tuple[str, str, str, float], ProductRecord] = {}
    for record in records:
        key = (
            record.platform,
            normalize_title(record.title),
            record.shop.strip().lower(),
            round(record.price, 2),
        )
        unique.setdefault(key, record)
    return list(unique.values())


def score_records(records: list[ProductRecord]) -> None:
    if not records:
        return

    min_price = min(record.price for record in records)
    max_sales = max(record.sales for record in records)
    max_rating = max(record.shop_rating for record in records)

    for record in records:
        price_score = min_price / record.price if record.price else 0.0
        sales_score = (
            math.log(record.sales + 1) / math.log(max_sales + 1) if max_sales else 0.0
        )
        rating_score = record.shop_rating / 5.0
        record.value_score = round(
            0.45 * price_score + 0.35 * sales_score + 0.20 * rating_score,
            4,
        )

    ranked = sorted(records, key=lambda item: item.value_score, reverse=True)
    for index, record in enumerate(ranked):
        tags: list[str] = []
        if index < 3:
            tags.append("高性价比推荐")
        if math.isclose(record.price, min_price, rel_tol=0.0, abs_tol=0.01):
            tags.append("最低价")
        if math.isclose(record.shop_rating, max_rating, rel_tol=0.0, abs_tol=0.01):
            tags.append("口碑优")
        record.recommendation = " / ".join(tags) if tags else "常规候选"


def build_platform_summary(records: list[ProductRecord]) -> list[dict]:
    grouped: dict[str, list[ProductRecord]] = {}
    for record in records:
        grouped.setdefault(record.platform, []).append(record)

    summary: list[dict] = []
    for platform, items in grouped.items():
        cheapest = min(items, key=lambda item: item.price)
        summary.append(
            {
                "platform": platform,
                "platform_label": PLATFORM_LABELS.get(platform, platform),
                "count": len(items),
                "lowest_price": round(min(item.price for item in items), 2),
                "average_price": round(mean(item.price for item in items), 2),
                "average_sales": round(mean(item.sales for item in items), 0),
                "average_rating": round(mean(item.shop_rating for item in items), 2),
                "cheapest_title": cheapest.title,
            }
        )
    return sorted(summary, key=lambda item: item["lowest_price"])


def build_trend(records: list[ProductRecord]) -> dict:
    series: list[dict] = []
    grouped: dict[str, list[ProductRecord]] = {}
    for record in records:
        grouped.setdefault(record.platform, []).append(record)

    for platform, items in grouped.items():
        history_length = min(len(item.price_history) for item in items)
        values = []
        for index in range(history_length):
            values.append(round(mean(item.price_history[index] for item in items), 2))
        series.append(
            {
                "platform": platform,
                "platform_label": PLATFORM_LABELS.get(platform, platform),
                "values": values,
            }
        )

    return {
        "dates": TREND_DATES[: len(series[0]["values"])] if series else [],
        "series": series,
    }


def collect_price_data(
    keyword: str,
    platforms: list[str] | None = None,
    limit: int = 5,
    mode: str = "sample",
    allow_sample_fallback: bool | None = None,
) -> dict:
    keyword = repair_mojibake(keyword.strip())
    if allow_sample_fallback is None:
        allow_sample_fallback = mode != "live"
    selected_platforms = platforms or list(PROVIDERS.keys())
    warnings: list[str] = []
    raw_records: list[ProductRecord] = []

    for platform in selected_platforms:
        provider = PROVIDERS.get(platform)
        if not provider:
            warnings.append(f"忽略未知平台: {platform}")
            continue

        try:
            raw_records.extend(provider.collect(keyword=keyword, limit=limit, mode=mode))
        except LiveCollectionUnavailable as exc:
            warnings.append(str(exc))
            if allow_sample_fallback:
                raw_records.extend(provider.collect(keyword=keyword, limit=limit, mode="sample"))
                warnings.append(f"{provider.label} 已自动回退到 sample 模式。")

    if mode == "live" and not raw_records:
        warnings.append("live 模式本次未采集到真实商品数据，可切回 sample 模式查看演示闭环。")

    cleaned_records = deduplicate_records(raw_records)
    score_records(cleaned_records)
    ordered_records = sorted(cleaned_records, key=lambda item: item.price)
    recommendations = sorted(
        ordered_records,
        key=lambda item: item.value_score,
        reverse=True,
    )[:3]

    summary = build_platform_summary(ordered_records)
    trend = build_trend(ordered_records)

    return {
        "keyword": keyword,
        "mode": mode,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "warnings": warnings,
        "items": [record.to_dict() for record in ordered_records],
        "recommendations": [record.to_dict() for record in recommendations],
        "summary": summary,
        "trend": trend,
    }


def _render_line_chart_svg(trend: dict) -> str:
    dates = trend.get("dates", [])
    series = trend.get("series", [])
    if not dates or not series:
        return "<div class='empty-chart'>暂无趋势数据</div>"

    width = 920
    height = 320
    left = 56
    right = 24
    top = 24
    bottom = 44
    inner_width = width - left - right
    inner_height = height - top - bottom
    all_values = [value for item in series for value in item["values"]]
    min_value = min(all_values)
    max_value = max(all_values)
    span = max(max_value - min_value, 1)
    palette = ["#67e8f9", "#f472b6", "#facc15", "#4ade80", "#c084fc"]

    def x(index: int) -> float:
        denominator = max(len(dates) - 1, 1)
        return left + inner_width * index / denominator

    def y(value: float) -> float:
        return top + inner_height * (1 - ((value - min_value) / span))

    paths: list[str] = []
    legend: list[str] = []
    for index, item in enumerate(series):
        color = palette[index % len(palette)]
        points = " ".join(f"{x(i):.1f},{y(value):.1f}" for i, value in enumerate(item["values"]))
        circles = "".join(
            (
                f"<circle cx='{x(i):.1f}' cy='{y(value):.1f}' r='4'"
                f" fill='{color}' stroke='#07111f' stroke-width='1.5' />"
            )
            for i, value in enumerate(item["values"])
        )
        paths.append(
            (
                f"<polyline fill='none' stroke='{color}' stroke-width='3.5' "
                f"stroke-linecap='round' stroke-linejoin='round' points='{points}' />"
                f"{circles}"
            )
        )
        legend.append(
            (
                f"<div class='legend-item'><span class='legend-dot' "
                f"style='background:{color}'></span>{escape(item['platform_label'])}</div>"
            )
        )

    grid = []
    for step in range(5):
        current_y = top + inner_height * step / 4
        price = max_value - span * step / 4
        grid.append(
            f"<line x1='{left}' y1='{current_y:.1f}' x2='{width - right}' y2='{current_y:.1f}' "
            "stroke='rgba(148,163,184,0.18)' stroke-width='1' />"
            f"<text x='8' y='{current_y + 4:.1f}' fill='#94a3b8' font-size='12'>¥{price:.0f}</text>"
        )

    labels = "".join(
        f"<text x='{x(index):.1f}' y='{height - 14}' text-anchor='middle' fill='#94a3b8' font-size='12'>{escape(label[5:])}</text>"
        for index, label in enumerate(dates)
    )

    return (
        "<div class='chart-card'>"
        "<div class='chart-title'>价格趋势</div>"
        f"<div class='legend'>{''.join(legend)}</div>"
        f"<svg viewBox='0 0 {width} {height}' class='trend-svg'>"
        f"{''.join(grid)}"
        f"{''.join(paths)}"
        f"{labels}"
        "</svg>"
        "</div>"
    )


def render_report_html(payload: dict) -> str:
    """生成可直接打开的静态 HTML 报告。"""

    summary_cards = "".join(
        (
            "<article class='summary-card'>"
            f"<div class='summary-platform'>{escape(item['platform_label'])}</div>"
            f"<div class='summary-price'>¥{item['lowest_price']:.2f}</div>"
            f"<div class='summary-meta'>均价 ¥{item['average_price']:.2f} / 平均评分 {item['average_rating']:.2f}</div>"
            f"<div class='summary-desc'>{escape(item['cheapest_title'])}</div>"
            "</article>"
        )
        for item in payload["summary"]
    )
    recommendation_cards = "".join(
        (
            "<article class='recommend-card'>"
            f"<div class='recommend-top'>{escape(item['platform_label'])} · 评分 {item['shop_rating']:.1f}</div>"
            f"<h3>{escape(item['title'])}</h3>"
            f"<div class='recommend-price'>¥{item['price']:.2f}</div>"
            f"<div class='recommend-score'>性价比分 {item['value_score']:.4f}</div>"
            f"<div class='recommend-tag'>{escape(item['recommendation'])}</div>"
            f"<a href='{escape(item['url'])}' target='_blank' rel='noreferrer'>查看商品链接</a>"
            "</article>"
        )
        for item in payload["recommendations"]
    )
    table_rows = "".join(
        (
            "<tr>"
            f"<td>{escape(item['platform_label'])}</td>"
            f"<td>{escape(item['title'])}</td>"
            f"<td>¥{item['price']:.2f}</td>"
            f"<td>{int(item['sales'])}</td>"
            f"<td>{item['shop_rating']:.1f}</td>"
            f"<td>{escape(item['recommendation'])}</td>"
            f"<td><a href='{escape(item['url'])}' target='_blank' rel='noreferrer'>打开</a></td>"
            "</tr>"
        )
        for item in payload["items"]
    )
    warnings = "".join(f"<li>{escape(warning)}</li>" for warning in payload.get("warnings", []))
    warning_block = (
        f"<section class='warning-box'><h3>运行提示</h3><ul>{warnings}</ul></section>"
        if warnings
        else ""
    )
    chart = _render_line_chart_svg(payload["trend"])
    payload_json = escape(json.dumps(payload, ensure_ascii=False, indent=2))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(payload['keyword'])} - 电商价格对比报告</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #050816;
      --panel: rgba(15, 23, 42, 0.88);
      --line: rgba(148, 163, 184, 0.22);
      --text: #e2e8f0;
      --muted: #94a3b8;
      --accent: #67e8f9;
      --accent-2: #f472b6;
      --accent-3: #facc15;
      --shadow: 0 18px 50px rgba(2, 8, 23, 0.45);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(103, 232, 249, 0.16), transparent 28%),
        radial-gradient(circle at top right, rgba(244, 114, 182, 0.12), transparent 24%),
        linear-gradient(180deg, #020617 0%, #0f172a 48%, #020617 100%);
      color: var(--text);
    }}
    .page {{
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 36px 0 64px;
    }}
    .hero {{
      padding: 32px;
      border: 1px solid rgba(103, 232, 249, 0.18);
      border-radius: 28px;
      background: linear-gradient(135deg, rgba(8, 15, 30, 0.96), rgba(15, 23, 42, 0.72));
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
    }}
    .eyebrow {{
      color: var(--accent);
      letter-spacing: 0.14em;
      text-transform: uppercase;
      font-size: 12px;
      margin-bottom: 12px;
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: clamp(32px, 5vw, 56px);
      line-height: 1.02;
    }}
    .hero p {{
      margin: 0;
      color: var(--muted);
      max-width: 760px;
      line-height: 1.7;
    }}
    .meta-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 22px;
    }}
    .meta-chip {{
      padding: 10px 14px;
      border-radius: 999px;
      background: rgba(15, 23, 42, 0.78);
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 14px;
    }}
    .section-title {{
      margin: 34px 0 14px;
      font-size: 22px;
    }}
    .summary-grid,
    .recommend-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
    }}
    .summary-card,
    .recommend-card,
    .table-card,
    .chart-card,
    .warning-box,
    .raw-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(16px);
    }}
    .summary-card,
    .recommend-card,
    .warning-box,
    .raw-card {{
      padding: 20px;
    }}
    .summary-platform,
    .recommend-top {{
      color: var(--muted);
      font-size: 14px;
      margin-bottom: 10px;
    }}
    .summary-price,
    .recommend-price {{
      font-size: 30px;
      font-weight: 700;
      margin-bottom: 10px;
    }}
    .summary-meta,
    .summary-desc,
    .recommend-score,
    .recommend-tag,
    .warning-box li {{
      color: var(--muted);
      line-height: 1.6;
    }}
    .recommend-card h3 {{
      margin: 0 0 14px;
      font-size: 21px;
      line-height: 1.35;
    }}
    a {{
      color: var(--accent);
      text-decoration: none;
    }}
    .chart-card {{
      padding: 24px;
      margin-top: 16px;
    }}
    .chart-title {{
      font-size: 20px;
      margin-bottom: 12px;
    }}
    .legend {{
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .legend-item {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
    }}
    .legend-dot {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      display: inline-block;
    }}
    .trend-svg {{
      width: 100%;
      height: auto;
    }}
    .table-card {{
      overflow: auto;
      margin-top: 16px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 840px;
    }}
    th,
    td {{
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      font-size: 14px;
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      font-size: 12px;
    }}
    .warning-box {{
      margin-top: 16px;
      border-color: rgba(250, 204, 21, 0.22);
    }}
    .warning-box h3,
    .raw-card h3 {{
      margin-top: 0;
    }}
    .raw-card {{
      margin-top: 16px;
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      color: #cbd5e1;
      background: rgba(2, 6, 23, 0.68);
      padding: 16px;
      border-radius: 18px;
      overflow: auto;
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="eyebrow">Price Watch Demo</div>
      <h1>{escape(payload['keyword'])} 价格自动化对比</h1>
      <p>该报告由本地命令行工具直接生成，包含按平台采集后的清洗去重、价格排序、横向对比、价格趋势与高性价比推荐结果。</p>
      <div class="meta-row">
        <div class="meta-chip">采集模式：{escape(payload['mode'])}</div>
        <div class="meta-chip">记录数：{len(payload['items'])}</div>
        <div class="meta-chip">生成时间：{escape(payload['generated_at'])}</div>
      </div>
    </section>
    <h2 class="section-title">平台摘要</h2>
    <section class="summary-grid">{summary_cards}</section>
    <h2 class="section-title">性价比推荐</h2>
    <section class="recommend-grid">{recommendation_cards}</section>
    <h2 class="section-title">价格趋势</h2>
    {chart}
    <h2 class="section-title">商品明细</h2>
    <section class="table-card">
      <table>
        <thead>
          <tr>
            <th>平台</th>
            <th>商品名</th>
            <th>价格</th>
            <th>销量</th>
            <th>店铺评分</th>
            <th>推荐标记</th>
            <th>链接</th>
          </tr>
        </thead>
        <tbody>{table_rows}</tbody>
      </table>
    </section>
    {warning_block}
    <section class="raw-card">
      <h3>结果 JSON 示例</h3>
      <pre>{payload_json}</pre>
    </section>
  </main>
</body>
</html>
"""


def export_result_files(payload: dict, output_dir: str | Path) -> dict[str, str]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    json_path = directory / "results.json"
    csv_path = directory / "results.csv"
    html_path = directory / "report.html"

    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    csv_lines = [
        "platform,platform_label,title,price,sales,shop_rating,shop,recommendation,url"
    ]
    for item in payload["items"]:
        columns = [
            item["platform"],
            item["platform_label"],
            item["title"].replace(",", "，"),
            f"{item['price']:.2f}",
            str(item["sales"]),
            f"{item['shop_rating']:.1f}",
            item["shop"].replace(",", "，"),
            item["recommendation"].replace(",", "，"),
            item["url"],
        ]
        csv_lines.append(",".join(columns))
    csv_path.write_text("\n".join(csv_lines) + "\n", encoding="utf-8")

    html_path.write_text(render_report_html(payload), encoding="utf-8")

    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "html": str(html_path),
    }
