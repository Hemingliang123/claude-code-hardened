# Price Watch Tool

一个可直接运行的电商商品价格自动化采集与对比演示工具。

## 能力范围

- 支持按关键词批量采集 `jd`、`taobao`、`pdd` 三个平台的商品结果
- 自动清洗去重、按价格从低到高排序
- 输出商品横向对比、价格趋势图、性价比推荐
- 同时提供命令行工具与本地演示网页
- 默认内置 `sample` 模式，保证无授权也能直接运行

## 架构设计

工具分为四层：

1. `Provider` 适配层
   - 每个平台对应一个 provider，负责采集并标准化为统一字段：
     `title / price / sales / shop / shop_rating / url / price_history`
   - 当前实现内置 sample 模式，并预留 live 模式扩展点

2. `Pipeline` 数据处理层
   - 去重规则：`platform + 归一化标题 + 店铺 + 价格`
   - 排序规则：按价格从低到高输出
   - 推荐规则：综合最低价、销量、店铺评分生成 `value_score`

3. `Report` 可视化层
   - 生成 `results.json`、`results.csv`、`report.html`
   - HTML 报告内置平台摘要、推荐卡片、趋势 SVG 和明细表

4. `Delivery` 交付层
   - `python -m price_watch_tool collect ...` 生成离线报告
   - `python -m price_watch_tool serve ...` 启动本地演示网页

## 为什么默认 sample 模式

京东、淘宝、拼多多的真实搜索结果通常受登录态、风控、验证码、接口签名和平台协议限制。
在当前仓库没有官方 API 凭证、也没有浏览器登录态注入能力的前提下，直接宣称“已实现稳定真实抓取”并不可靠。

因此当前版本提供：

- 一个可以直接运行、完整闭环的 sample 演示链路
- 一个清晰的 provider 扩展接口，用于后续接入真实采集能力

如果你要升级到 live 采集，建议优先采用：

- 平台开放平台 / 联盟 API
- 你自有的浏览器自动化登录会话
- 经法务和平台协议确认后的采集方案

## 目录说明

```text
price_watch_tool/
  __init__.py
  __main__.py
  cli.py
  core.py
  sample_data.py
  web.py
```

## 运行方式

### 1. 生成一次采集结果

```bash
python3 -m price_watch_tool collect \
  --keyword "蓝牙耳机" \
  --platforms jd,taobao,pdd \
  --limit 4 \
  --mode sample \
  --output-dir ./price_watch_output
```

输出：

- `price_watch_output/results.json`
- `price_watch_output/results.csv`
- `price_watch_output/report.html`

### 2. 启动演示网页

```bash
python3 -m price_watch_tool serve --host 127.0.0.1 --port 8765
```

打开：

- `http://127.0.0.1:8765`

## 示例输入与结果

初始化示例关键词：

```json
{
  "keyword": "蓝牙耳机",
  "mode": "sample",
  "limit": 4,
  "platforms": ["jd", "taobao", "pdd"]
}
```

结果示例字段：

```json
{
  "platform": "pdd",
  "platform_label": "拼多多",
  "title": "联想 LP40 Pro 蓝牙耳机 入门高配版",
  "price": 89.0,
  "sales": 52800,
  "shop": "联想数码拼购店",
  "shop_rating": 4.6,
  "url": "https://demo.local/pdd/lenovo-lp40-pro?keyword=%E8%93%9D%E7%89%99%E8%80%B3%E6%9C%BA",
  "price_history": [109.0, 105.0, 102.0, 98.0, 95.0, 92.0, 89.0],
  "value_score": 0.982,
  "recommendation": "高性价比推荐 / 最低价"
}
```

## 后续扩展 live 模式

扩展入口在 `core.py` 中的各 provider：

- `JdProvider._collect_live()`
- `TaobaoProvider._collect_live()`
- `PddProvider._collect_live()`

接入真实采集时，建议保持统一输出结构不变，这样 CLI、网页和报告层无需改动。
