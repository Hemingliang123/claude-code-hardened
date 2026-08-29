"""内置演示数据。

默认提供 sample 模式，保证 CLI 和 Web 演示在无平台授权、无浏览器会话的情况下
也可以直接运行。后续若接入官方 API 或浏览器自动化，只需要替换 provider 的
live 采集逻辑，不影响清洗、排序、推荐和可视化链路。
"""

from __future__ import annotations

from copy import deepcopy
from urllib.parse import quote_plus

DEFAULT_KEYWORD = "蓝牙耳机"
TREND_DATES = [
    "2026-08-24",
    "2026-08-25",
    "2026-08-26",
    "2026-08-27",
    "2026-08-28",
    "2026-08-29",
    "2026-08-30",
]

_SAMPLE_CATALOG = {
    "jd": [
        {
            "id": "jd-01",
            "title_template": "漫步者 NeoBuds Pro {keyword} 主动降噪版",
            "price": 329.0,
            "sales": 8600,
            "shop": "京东自营旗舰店",
            "shop_rating": 4.9,
            "url_template": "https://demo.local/jd/neobuds-pro?keyword={keyword}",
            "price_history": [359, 349, 345, 339, 335, 332, 329],
        },
        {
            "id": "jd-02",
            "title_template": "倍思 Bowie M2s {keyword} Hi-Res 低延迟",
            "price": 219.0,
            "sales": 15200,
            "shop": "Baseus 京东旗舰店",
            "shop_rating": 4.8,
            "url_template": "https://demo.local/jd/bowie-m2s?keyword={keyword}",
            "price_history": [239, 235, 232, 229, 225, 222, 219],
        },
        {
            "id": "jd-03",
            "title_template": "小米 Buds 5 {keyword} 空间音频款",
            "price": 269.0,
            "sales": 9700,
            "shop": "小米京东自营店",
            "shop_rating": 4.8,
            "url_template": "https://demo.local/jd/xiaomi-buds-5?keyword={keyword}",
            "price_history": [289, 285, 282, 279, 276, 272, 269],
        },
        {
            "id": "jd-04",
            "title_template": "QCY AilyBuds Lite {keyword} 长续航版",
            "price": 139.0,
            "sales": 28400,
            "shop": "QCY 京东旗舰店",
            "shop_rating": 4.7,
            "url_template": "https://demo.local/jd/qcy-ailybuds-lite?keyword={keyword}",
            "price_history": [159, 155, 149, 145, 143, 141, 139],
        },
    ],
    "taobao": [
        {
            "id": "tb-01",
            "title_template": "索尼 WF-C700N {keyword} 店播专享套装",
            "price": 459.0,
            "sales": 5300,
            "shop": "Sony 淘宝旗舰店",
            "shop_rating": 4.9,
            "url_template": "https://demo.local/taobao/sony-c700n?keyword={keyword}",
            "price_history": [499, 489, 485, 479, 469, 465, 459],
        },
        {
            "id": "tb-02",
            "title_template": "漫步者 NeoBuds Pro {keyword} 主动降噪版",
            "price": 319.0,
            "sales": 6400,
            "shop": "漫步者天猫旗舰店",
            "shop_rating": 4.9,
            "url_template": "https://demo.local/taobao/neobuds-pro?keyword={keyword}",
            "price_history": [339, 336, 333, 329, 326, 323, 319],
        },
        {
            "id": "tb-03",
            "title_template": "倍思 Bowie M2s {keyword} 旗舰升级版",
            "price": 209.0,
            "sales": 18100,
            "shop": "Baseus 天猫旗舰店",
            "shop_rating": 4.8,
            "url_template": "https://demo.local/taobao/bowie-m2s?keyword={keyword}",
            "price_history": [229, 225, 222, 219, 215, 212, 209],
        },
        {
            "id": "tb-04",
            "title_template": "OPPO Enco Air4 {keyword} 低延迟游戏款",
            "price": 179.0,
            "sales": 12000,
            "shop": "OPPO 官方旗舰店",
            "shop_rating": 4.8,
            "url_template": "https://demo.local/taobao/oppo-enco-air4?keyword={keyword}",
            "price_history": [199, 195, 191, 188, 185, 182, 179],
        },
    ],
    "pdd": [
        {
            "id": "pdd-01",
            "title_template": "QCY AilyBuds Lite {keyword} 百亿补贴",
            "price": 119.0,
            "sales": 36200,
            "shop": "QCY 拼多多品牌店",
            "shop_rating": 4.7,
            "url_template": "https://demo.local/pdd/qcy-ailybuds-lite?keyword={keyword}",
            "price_history": [139, 135, 132, 128, 125, 122, 119],
        },
        {
            "id": "pdd-02",
            "title_template": "小米 Buds 5 {keyword} 百亿补贴",
            "price": 249.0,
            "sales": 14300,
            "shop": "小米拼购官方店",
            "shop_rating": 4.8,
            "url_template": "https://demo.local/pdd/xiaomi-buds-5?keyword={keyword}",
            "price_history": [275, 269, 265, 261, 257, 253, 249],
        },
        {
            "id": "pdd-03",
            "title_template": "漫步者 NeoBuds Pro {keyword} 秒杀特惠",
            "price": 299.0,
            "sales": 9800,
            "shop": "漫步者拼购专卖店",
            "shop_rating": 4.7,
            "url_template": "https://demo.local/pdd/neobuds-pro?keyword={keyword}",
            "price_history": [325, 319, 315, 311, 307, 303, 299],
        },
        {
            "id": "pdd-04",
            "title_template": "联想 LP40 Pro {keyword} 入门高配版",
            "price": 89.0,
            "sales": 52800,
            "shop": "联想数码拼购店",
            "shop_rating": 4.6,
            "url_template": "https://demo.local/pdd/lenovo-lp40-pro?keyword={keyword}",
            "price_history": [109, 105, 102, 98, 95, 92, 89],
        },
    ],
}


def _price_shift(keyword: str) -> float:
    """根据关键词生成一个小范围的价格扰动，让示例对不同关键词保持响应感。"""

    checksum = sum(ord(char) for char in keyword)
    return float((checksum % 7) - 3)


def get_sample_items(platform: str, keyword: str, limit: int) -> list[dict]:
    """返回指定平台的演示商品数据。"""

    items = deepcopy(_SAMPLE_CATALOG.get(platform, []))
    delta = _price_shift(keyword)
    encoded_keyword = quote_plus(keyword)
    enriched: list[dict] = []

    for raw in items[:limit]:
        adjusted_history = [round(value + delta, 2) for value in raw["price_history"]]
        current_price = round(raw["price"] + delta, 2)
        enriched.append(
            {
                "id": raw["id"],
                "title": raw["title_template"].format(keyword=keyword),
                "price": max(current_price, 1.0),
                "sales": raw["sales"],
                "shop": raw["shop"],
                "shop_rating": raw["shop_rating"],
                "url": raw["url_template"].format(keyword=encoded_keyword),
                "price_history": [max(value, 1.0) for value in adjusted_history],
            }
        )

    return enriched
