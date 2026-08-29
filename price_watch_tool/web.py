"""本地演示网页服务。"""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from textwrap import dedent
from urllib.parse import parse_qs, urlparse

from .core import PLATFORM_LABELS, collect_price_data


def _page_html(initial_payload: dict, default_mode: str, default_limit: int) -> str:
    initial_json = json.dumps(initial_payload, ensure_ascii=False)
    sample_request = {
        "keyword": initial_payload["keyword"],
        "mode": default_mode,
        "limit": default_limit,
        "platforms": list(PLATFORM_LABELS.keys()),
    }
    request_json = json.dumps(sample_request, ensure_ascii=False, indent=2)
    result_example = json.dumps(initial_payload["recommendations"][0], ensure_ascii=False, indent=2)

    return dedent(
        f"""\
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>Price Watch Demo</title>
          <style>
            :root {{
              color-scheme: dark;
              --bg: #020617;
              --panel: rgba(15, 23, 42, 0.8);
              --panel-strong: rgba(10, 18, 32, 0.96);
              --line: rgba(148, 163, 184, 0.18);
              --text: #e2e8f0;
              --muted: #94a3b8;
              --cyan: #67e8f9;
              --pink: #f472b6;
              --yellow: #facc15;
              --green: #4ade80;
              --shadow: 0 26px 80px rgba(2, 8, 23, 0.46);
            }}
            * {{ box-sizing: border-box; }}
            body {{
              margin: 0;
              font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
              color: var(--text);
              background:
                radial-gradient(circle at top left, rgba(103, 232, 249, 0.14), transparent 24%),
                radial-gradient(circle at 85% 10%, rgba(244, 114, 182, 0.16), transparent 20%),
                linear-gradient(180deg, #020617 0%, #081120 48%, #020617 100%);
            }}
            .page {{
              width: min(1260px, calc(100vw - 32px));
              margin: 0 auto;
              padding: 28px 0 72px;
            }}
            .hero {{
              display: grid;
              grid-template-columns: 1.2fr 0.8fr;
              gap: 20px;
              align-items: stretch;
            }}
            .hero-card,
            .panel,
            .data-card,
            .table-card,
            .raw-card {{
              background: var(--panel);
              border: 1px solid var(--line);
              border-radius: 28px;
              box-shadow: var(--shadow);
              backdrop-filter: blur(16px);
            }}
            .hero-card {{
              padding: 28px;
              background:
                linear-gradient(135deg, rgba(9, 17, 32, 0.98), rgba(15, 23, 42, 0.72)),
                radial-gradient(circle at top right, rgba(103, 232, 249, 0.08), transparent 22%);
            }}
            .eyebrow {{
              margin-bottom: 12px;
              color: var(--cyan);
              text-transform: uppercase;
              letter-spacing: 0.14em;
              font-size: 12px;
            }}
            h1 {{
              margin: 0 0 16px;
              font-size: clamp(32px, 5vw, 62px);
              line-height: 0.98;
            }}
            .hero-copy {{
              margin: 0 0 24px;
              color: var(--muted);
              line-height: 1.75;
              max-width: 760px;
            }}
            .chip-row,
            .platform-row,
            .stat-row,
            .recommend-grid,
            .summary-grid {{
              display: flex;
              flex-wrap: wrap;
              gap: 10px;
            }}
            .chip {{
              padding: 10px 14px;
              border-radius: 999px;
              border: 1px solid var(--line);
              background: rgba(2, 6, 23, 0.48);
              color: var(--muted);
              font-size: 14px;
            }}
            .panel {{
              padding: 24px;
            }}
            .form-grid {{
              display: grid;
              gap: 14px;
            }}
            label {{
              display: block;
              margin-bottom: 8px;
              color: var(--muted);
              font-size: 14px;
            }}
            input[type="text"],
            select,
            input[type="number"] {{
              width: 100%;
              border: 1px solid rgba(103, 232, 249, 0.18);
              background: rgba(2, 6, 23, 0.65);
              color: var(--text);
              border-radius: 16px;
              padding: 14px 16px;
              font-size: 16px;
              outline: none;
            }}
            .platform-option {{
              display: inline-flex;
              align-items: center;
              gap: 8px;
              padding: 10px 14px;
              border-radius: 999px;
              background: rgba(2, 6, 23, 0.48);
              border: 1px solid var(--line);
              color: var(--muted);
              cursor: pointer;
            }}
            .platform-option input {{
              accent-color: var(--cyan);
            }}
            button {{
              border: 0;
              border-radius: 16px;
              padding: 14px 18px;
              background: linear-gradient(135deg, var(--cyan), var(--pink));
              color: #04111f;
              font-weight: 700;
              font-size: 15px;
              cursor: pointer;
            }}
            button.secondary {{
              background: rgba(2, 6, 23, 0.64);
              color: var(--text);
              border: 1px solid var(--line);
            }}
            .section-title {{
              margin: 28px 0 14px;
              font-size: 24px;
            }}
            .data-grid {{
              display: grid;
              grid-template-columns: 1fr 1fr;
              gap: 16px;
              margin-top: 20px;
            }}
            .data-card,
            .raw-card {{
              padding: 22px;
            }}
            .data-card h3,
            .raw-card h3 {{
              margin-top: 0;
              font-size: 18px;
            }}
            .summary-grid,
            .recommend-grid {{
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
              gap: 16px;
            }}
            .summary-item,
            .recommend-item {{
              padding: 20px;
              border-radius: 24px;
              background: var(--panel-strong);
              border: 1px solid var(--line);
            }}
            .summary-item .price,
            .recommend-item .price {{
              font-size: 30px;
              font-weight: 700;
              margin: 10px 0;
            }}
            .muted {{
              color: var(--muted);
              line-height: 1.65;
            }}
            .status {{
              min-height: 24px;
              color: var(--yellow);
              margin-top: 12px;
            }}
            .warning-list {{
              margin: 16px 0 0;
              padding-left: 18px;
              color: var(--yellow);
            }}
            .chart-shell,
            .table-card,
            .raw-card {{
              margin-top: 16px;
            }}
            .table-card {{
              overflow: auto;
              border-radius: 28px;
              border: 1px solid var(--line);
              background: var(--panel);
              box-shadow: var(--shadow);
            }}
            table {{
              width: 100%;
              min-width: 880px;
              border-collapse: collapse;
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
              font-size: 12px;
              text-transform: uppercase;
              letter-spacing: 0.04em;
            }}
            pre {{
              margin: 0;
              white-space: pre-wrap;
              word-break: break-word;
              padding: 16px;
              border-radius: 20px;
              background: rgba(2, 6, 23, 0.72);
              color: #cbd5e1;
              overflow: auto;
            }}
            .legend {{
              display: flex;
              flex-wrap: wrap;
              gap: 16px;
              margin-bottom: 10px;
              color: var(--muted);
              font-size: 13px;
            }}
            .legend-item {{
              display: inline-flex;
              align-items: center;
              gap: 8px;
            }}
            .legend-dot {{
              width: 10px;
              height: 10px;
              border-radius: 999px;
              display: inline-block;
            }}
            svg {{
              width: 100%;
              height: auto;
              display: block;
            }}
            .toolbar {{
              display: flex;
              flex-wrap: wrap;
              gap: 12px;
              align-items: center;
            }}
            .sample-button {{
              border: 1px solid var(--line);
              background: rgba(2, 6, 23, 0.48);
              color: var(--text);
            }}
            @media (max-width: 980px) {{
              .hero,
              .data-grid {{
                grid-template-columns: 1fr;
              }}
            }}
          </style>
        </head>
        <body>
          <main class="page">
            <section class="hero">
              <article class="hero-card">
                <div class="eyebrow">Price Watch Demo</div>
                <h1>电商价格自动化采集与对比</h1>
                <p class="hero-copy">同一套 Python 核心逻辑同时服务于 CLI 与网页：采集指定关键词的商品数据，自动清洗去重、按价格排序，输出横向对比、价格趋势和高性价比推荐。当前页面默认运行 sample 演示模式，便于无授权、无登录态时直接启动体验。</p>
                <div class="chip-row">
                  <span class="chip">CLI + 本地 Web</span>
                  <span class="chip">关键词批量采集</span>
                  <span class="chip">去重 / 排序 / 推荐</span>
                  <span class="chip">趋势图表</span>
                </div>
              </article>
              <section class="panel">
                <div class="form-grid">
                  <div>
                    <label for="keyword">搜索关键词</label>
                    <input id="keyword" name="keyword" type="text" value="{initial_payload['keyword']}" placeholder="例如：蓝牙耳机" />
                  </div>
                  <div>
                    <label for="mode">采集模式</label>
                    <select id="mode" name="mode">
                      <option value="sample" {"selected" if default_mode == "sample" else ""}>sample</option>
                      <option value="live" {"selected" if default_mode == "live" else ""}>live</option>
                    </select>
                  </div>
                  <div>
                    <label for="limit">每个平台条数</label>
                    <input id="limit" name="limit" type="number" min="1" max="10" value="{default_limit}" />
                  </div>
                  <div>
                    <label>平台选择</label>
                    <div class="platform-row">
                      <label class="platform-option"><input type="checkbox" name="platform" value="jd" checked /> 京东</label>
                      <label class="platform-option"><input type="checkbox" name="platform" value="taobao" checked /> 淘宝</label>
                      <label class="platform-option"><input type="checkbox" name="platform" value="pdd" checked /> 拼多多</label>
                    </div>
                  </div>
                  <div class="toolbar">
                    <button id="run">现场运行脚本</button>
                    <button type="button" class="secondary sample-button" data-keyword="蓝牙耳机">蓝牙耳机示例</button>
                    <button type="button" class="secondary sample-button" data-keyword="机械键盘">机械键盘示例</button>
                    <button type="button" class="secondary sample-button" data-keyword="手机壳">手机壳示例</button>
                  </div>
                  <div id="status" class="status"></div>
                </div>
              </section>
            </section>

            <h2 class="section-title">初始化示例</h2>
            <section class="data-grid">
              <article class="data-card">
                <h3>示例输入</h3>
                <pre id="sampleRequest">{request_json}</pre>
              </article>
              <article class="data-card">
                <h3>示例结果</h3>
                <pre id="sampleResult">{result_example}</pre>
              </article>
            </section>

            <h2 class="section-title">平台摘要</h2>
            <section id="summary" class="summary-grid"></section>

            <h2 class="section-title">性价比推荐</h2>
            <section id="recommendations" class="recommend-grid"></section>

            <h2 class="section-title">价格趋势</h2>
            <section class="panel chart-shell">
              <div id="chart"></div>
            </section>

            <h2 class="section-title">商品明细</h2>
            <section class="table-card">
              <table>
                <thead>
                  <tr>
                    <th>平台</th>
                    <th>商品名称</th>
                    <th>价格</th>
                    <th>销量</th>
                    <th>店铺评分</th>
                    <th>推荐</th>
                    <th>链接</th>
                  </tr>
                </thead>
                <tbody id="tableBody"></tbody>
              </table>
            </section>

            <section id="warnings" class="panel" style="display:none; margin-top:16px;">
              <h3 style="margin-top:0;">运行提示</h3>
              <ul id="warningList" class="warning-list"></ul>
            </section>

            <section class="raw-card">
              <h3>完整结果 JSON</h3>
              <pre id="rawJson"></pre>
            </section>
          </main>

          <script>
            const initialPayload = {initial_json};
            const palette = ['#67e8f9', '#f472b6', '#facc15', '#4ade80', '#c084fc'];

            function escapeHtml(text) {{
              return String(text)
                .replaceAll('&', '&amp;')
                .replaceAll('<', '&lt;')
                .replaceAll('>', '&gt;')
                .replaceAll('"', '&quot;')
                .replaceAll("'", '&#39;');
            }}

            function renderSummary(payload) {{
              const root = document.getElementById('summary');
              root.innerHTML = payload.summary.map((item) => `
                <article class="summary-item">
                  <div class="muted">${{escapeHtml(item.platform_label)}}</div>
                  <div class="price">¥${{Number(item.lowest_price).toFixed(2)}}</div>
                  <div class="muted">均价 ¥${{Number(item.average_price).toFixed(2)}} / 平均评分 ${{Number(item.average_rating).toFixed(2)}}</div>
                  <div class="muted">最低价商品：${{escapeHtml(item.cheapest_title)}}</div>
                </article>
              `).join('');
            }}

            function renderRecommendations(payload) {{
              const root = document.getElementById('recommendations');
              root.innerHTML = payload.recommendations.map((item) => `
                <article class="recommend-item">
                  <div class="muted">${{escapeHtml(item.platform_label)}} · 评分 ${{Number(item.shop_rating).toFixed(1)}}</div>
                  <h3 style="margin:8px 0 12px; line-height:1.4;">${{escapeHtml(item.title)}}</h3>
                  <div class="price">¥${{Number(item.price).toFixed(2)}}</div>
                  <div class="muted">性价比分：${{Number(item.value_score).toFixed(4)}}</div>
                  <div class="muted">${{escapeHtml(item.recommendation)}}</div>
                  <div style="margin-top:10px;"><a href="${{escapeHtml(item.url)}}" target="_blank" rel="noreferrer">打开商品链接</a></div>
                </article>
              `).join('');
            }}

            function renderWarnings(payload) {{
              const wrapper = document.getElementById('warnings');
              const root = document.getElementById('warningList');
              if (!payload.warnings || !payload.warnings.length) {{
                wrapper.style.display = 'none';
                root.innerHTML = '';
                return;
              }}
              wrapper.style.display = 'block';
              root.innerHTML = payload.warnings.map((item) => `<li>${{escapeHtml(item)}}</li>`).join('');
            }}

            function renderTable(payload) {{
              const root = document.getElementById('tableBody');
              root.innerHTML = payload.items.map((item) => `
                <tr>
                  <td>${{escapeHtml(item.platform_label)}}</td>
                  <td>${{escapeHtml(item.title)}}</td>
                  <td>¥${{Number(item.price).toFixed(2)}}</td>
                  <td>${{Number(item.sales).toLocaleString('zh-CN')}}</td>
                  <td>${{Number(item.shop_rating).toFixed(1)}}</td>
                  <td>${{escapeHtml(item.recommendation)}}</td>
                  <td><a href="${{escapeHtml(item.url)}}" target="_blank" rel="noreferrer">打开</a></td>
                </tr>
              `).join('');
            }}

            function renderChart(payload) {{
              const root = document.getElementById('chart');
              const trend = payload.trend || {{ dates: [], series: [] }};
              if (!trend.dates.length || !trend.series.length) {{
                root.innerHTML = '<div class="muted">暂无趋势数据</div>';
                return;
              }}

              const width = 920;
              const height = 320;
              const left = 56;
              const right = 24;
              const top = 24;
              const bottom = 44;
              const innerWidth = width - left - right;
              const innerHeight = height - top - bottom;
              const allValues = trend.series.flatMap((item) => item.values);
              const minValue = Math.min(...allValues);
              const maxValue = Math.max(...allValues);
              const span = Math.max(maxValue - minValue, 1);
              const x = (index) => left + innerWidth * (index / Math.max(trend.dates.length - 1, 1));
              const y = (value) => top + innerHeight * (1 - ((value - minValue) / span));

              const grid = Array.from({{ length: 5 }}, (_, index) => {{
                const currentY = top + innerHeight * (index / 4);
                const price = maxValue - span * (index / 4);
                return `
                  <line x1="${{left}}" y1="${{currentY}}" x2="${{width - right}}" y2="${{currentY}}" stroke="rgba(148,163,184,0.18)" stroke-width="1"></line>
                  <text x="8" y="${{currentY + 4}}" fill="#94a3b8" font-size="12">¥${{price.toFixed(0)}}</text>
                `;
              }}).join('');

              const lines = trend.series.map((item, index) => {{
                const color = palette[index % palette.length];
                const points = item.values.map((value, pointIndex) => `${{x(pointIndex).toFixed(1)}},${{y(value).toFixed(1)}}`).join(' ');
                const circles = item.values.map((value, pointIndex) => `
                  <circle cx="${{x(pointIndex).toFixed(1)}}" cy="${{y(value).toFixed(1)}}" r="4" fill="${{color}}" stroke="#07111f" stroke-width="1.5"></circle>
                `).join('');
                return `
                  <polyline fill="none" stroke="${{color}}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" points="${{points}}"></polyline>
                  ${{circles}}
                `;
              }}).join('');

              const labels = trend.dates.map((item, index) => `
                <text x="${{x(index).toFixed(1)}}" y="${{height - 14}}" text-anchor="middle" fill="#94a3b8" font-size="12">${{item.slice(5)}}</text>
              `).join('');

              const legend = trend.series.map((item, index) => `
                <div class="legend-item">
                  <span class="legend-dot" style="background:${{palette[index % palette.length]}}"></span>
                  ${{escapeHtml(item.platform_label)}}
                </div>
              `).join('');

              root.innerHTML = `
                <div class="legend">${{legend}}</div>
                <svg viewBox="0 0 ${{width}} ${{height}}">
                  ${{grid}}
                  ${{lines}}
                  ${{labels}}
                </svg>
              `;
            }}

            function renderRaw(payload) {{
              document.getElementById('rawJson').textContent = JSON.stringify(payload, null, 2);
              document.getElementById('sampleResult').textContent = JSON.stringify(payload.recommendations[0] || {{}}, null, 2);
              document.getElementById('sampleRequest').textContent = JSON.stringify({{
                keyword: payload.keyword,
                mode: payload.mode,
                limit: payload.items.length ? Math.floor(payload.items.length / 3) : 4,
                platforms: ['jd', 'taobao', 'pdd']
              }}, null, 2);
            }}

            function renderPayload(payload) {{
              renderSummary(payload);
              renderRecommendations(payload);
              renderWarnings(payload);
              renderTable(payload);
              renderChart(payload);
              renderRaw(payload);
            }}

            async function runCollect() {{
              const keyword = document.getElementById('keyword').value.trim();
              const mode = document.getElementById('mode').value;
              const limit = document.getElementById('limit').value;
              const platforms = Array.from(document.querySelectorAll('input[name="platform"]:checked')).map((node) => node.value);
              const status = document.getElementById('status');
              if (!keyword) {{
                status.textContent = '请输入关键词。';
                return;
              }}
              if (!platforms.length) {{
                status.textContent = '至少选择一个平台。';
                return;
              }}
              status.textContent = '脚本运行中，正在采集并生成对比结果...';
              const query = new URLSearchParams({{
                keyword,
                mode,
                limit,
                platforms: platforms.join(',')
              }});
              try {{
                const response = await fetch(`/api/collect?${{query.toString()}}`);
                if (!response.ok) {{
                  throw new Error(`请求失败: ${{response.status}}`);
                }}
                const payload = await response.json();
                renderPayload(payload);
                status.textContent = `采集完成，共返回 ${{payload.items.length}} 条结果。`;
              }} catch (error) {{
                status.textContent = `运行失败：${{error.message}}`;
              }}
            }}

            document.getElementById('run').addEventListener('click', runCollect);
            document.querySelectorAll('.sample-button').forEach((button) => {{
              button.addEventListener('click', () => {{
                document.getElementById('keyword').value = button.dataset.keyword || '';
                runCollect();
              }});
            }});

            renderPayload(initialPayload);
            document.getElementById('status').textContent = '已加载初始化示例，可直接修改关键词后再次运行。';
          </script>
        </body>
        </html>
        """
    )


def run_demo_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    initial_keyword: str = "蓝牙耳机",
    default_mode: str = "sample",
    default_limit: int = 4,
) -> None:
    initial_payload = collect_price_data(
        keyword=initial_keyword,
        mode=default_mode,
        limit=default_limit,
        platforms=list(PLATFORM_LABELS.keys()),
    )
    page_html = _page_html(
        initial_payload=initial_payload,
        default_mode=default_mode,
        default_limit=default_limit,
    ).encode("utf-8")

    class DemoHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._write_html(page_html)
                return
            if parsed.path == "/api/collect":
                self._handle_collect(parsed.query)
                return
            if parsed.path == "/favicon.ico":
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

        def _handle_collect(self, query: str) -> None:
            params = parse_qs(query)
            keyword = params.get("keyword", [initial_keyword])[0]
            mode = params.get("mode", [default_mode])[0]
            try:
                limit = int(params.get("limit", [str(default_limit)])[0])
            except ValueError:
                limit = default_limit
            platforms_raw = params.get("platforms", [",".join(PLATFORM_LABELS.keys())])[0]
            platforms = [item.strip() for item in platforms_raw.split(",") if item.strip()]
            payload = collect_price_data(
                keyword=keyword,
                mode=mode if mode in {"sample", "live"} else default_mode,
                limit=max(1, min(limit, 10)),
                platforms=platforms,
            )
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _write_html(self, body: bytes) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((host, port), DemoHandler)
    print(f"Price Watch Demo 已启动: http://{host}:{port}")
    print("按 Ctrl+C 停止服务")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
    finally:
        server.server_close()
