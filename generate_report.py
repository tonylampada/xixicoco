#!/usr/bin/env python3
"""Generate HTML report for Isaac's potty training data."""

import csv
from collections import Counter, defaultdict
from datetime import datetime, timedelta

def load_csv(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def generate_html(events):
    real = [e for e in events if e['tipo'] != 'nao_fez']
    nao_fez = [e for e in events if e['tipo'] == 'nao_fez']
    successes = [e for e in real if e['sucesso'] == 'sim']
    escapes = [e for e in real if e['sucesso'] == 'escape']

    first_date = events[0]['data']
    last_date = events[-1]['data']
    d1 = datetime.strptime(first_date, '%Y-%m-%d')
    d2 = datetime.strptime(last_date, '%Y-%m-%d')
    total_days = (d2 - d1).days + 1

    # Weekly data
    weekly = defaultdict(lambda: {'success': 0, 'escape': 0, 'nao_fez': 0, 'days': set(),
                                   'sozinho': 0, 'pediu': 0, 'mandei': 0, 'levei': 0,
                                   'coco_ok': 0, 'coco_esc': 0})
    for e in events:
        d = datetime.strptime(e['data'], '%Y-%m-%d')
        ws = d - timedelta(days=d.weekday())
        wk = ws.strftime('%d/%m')
        weekly[wk]['days'].add(e['data'])
        if e['tipo'] == 'nao_fez':
            weekly[wk]['nao_fez'] += 1
        elif e['sucesso'] == 'sim':
            weekly[wk]['success'] += 1
            init = e['iniciativa']
            if init in ('sozinho', 'pediu'):
                weekly[wk]['sozinho'] += 1
            if init == 'pediu':
                weekly[wk]['pediu'] += 1
            if init == 'mandei':
                weekly[wk]['mandei'] += 1
            if init == 'levei':
                weekly[wk]['levei'] += 1
            if 'coco' in e['tipo']:
                weekly[wk]['coco_ok'] += 1
        else:
            weekly[wk]['escape'] += 1
            if 'coco' in e['tipo']:
                weekly[wk]['coco_esc'] += 1

    week_keys = sorted(weekly.keys(), key=lambda x: datetime.strptime(x, '%d/%m'))

    # Daily data for the chart
    daily = defaultdict(lambda: {'success': 0, 'escape': 0})
    for e in real:
        daily[e['data']]['success' if e['sucesso'] == 'sim' else 'escape'] += 1

    daily_dates = sorted(daily.keys())

    # Periods
    period_data = defaultdict(lambda: {'escape': 0, 'total': 0})
    for e in real:
        h = int(e['hora'].split(':')[0])
        if 6 <= h < 12: p = 'Manha (6-12h)'
        elif 12 <= h < 18: p = 'Tarde (12-18h)'
        elif 18 <= h < 24: p = 'Noite (18-24h)'
        else: p = 'Madrugada (0-6h)'
        period_data[p]['total'] += 1
        if e['sucesso'] == 'escape':
            period_data[p]['escape'] += 1

    # Day of week
    dow_data = defaultdict(lambda: {'escape': 0, 'total': 0})
    for e in real:
        dow_data[e['dia_semana']]['total'] += 1
        if e['sucesso'] == 'escape':
            dow_data[e['dia_semana']]['escape'] += 1

    # Activities
    activities = Counter(e['atividade_escape'] for e in escapes if e['atividade_escape'])

    # Coco
    cocos = [e for e in real if 'coco' in e['tipo']]
    coco_ok = [e for e in cocos if e['sucesso'] == 'sim']
    coco_esc = [e for e in cocos if e['sucesso'] == 'escape']
    coco_sozinho = [e for e in coco_ok if e['iniciativa'] == 'sozinho']

    # Initiative
    init_counts = Counter(e['iniciativa'] for e in successes)

    # Intervals
    daily_times = defaultdict(list)
    for e in events:
        if e['tipo'] != 'nao_fez':
            h, m = map(int, e['hora'].split(':'))
            daily_times[e['data']].append(h * 60 + m)
    all_intervals = []
    for day, times in daily_times.items():
        times.sort()
        for i in range(1, len(times)):
            iv = times[i] - times[i-1]
            if 5 <= iv <= 300:
                all_intervals.append(iv)
    all_intervals.sort()
    avg_iv = sum(all_intervals) / len(all_intervals) if all_intervals else 0
    med_iv = all_intervals[len(all_intervals)//2] if all_intervals else 0

    # Build chart data
    week_labels = [f"'{wk}'" for wk in week_keys]
    week_success = [weekly[wk]['success'] for wk in week_keys]
    week_escape = [weekly[wk]['escape'] for wk in week_keys]
    week_nao_fez = [weekly[wk]['nao_fez'] for wk in week_keys]
    week_pct = [round(100 * weekly[wk]['success'] / max(weekly[wk]['success'] + weekly[wk]['escape'], 1)) for wk in week_keys]
    week_indep_pct = [round(100 * weekly[wk]['sozinho'] / max(weekly[wk]['success'], 1)) for wk in week_keys]
    week_esc_per_day = [round(weekly[wk]['escape'] / max(len(weekly[wk]['days']), 1), 1) for wk in week_keys]

    period_labels = ['Manha (6-12h)', 'Tarde (12-18h)', 'Noite (18-24h)']
    period_esc_pct = [round(100 * period_data[p]['escape'] / max(period_data[p]['total'], 1), 1) for p in period_labels]
    period_totals = [period_data[p]['total'] for p in period_labels]
    period_escapes = [period_data[p]['escape'] for p in period_labels]

    dow_labels = ['seg', 'ter', 'qua', 'qui', 'sex', 'sab', 'dom']
    dow_esc_pct = [round(100 * dow_data[d]['escape'] / max(dow_data[d]['total'], 1), 1) for d in dow_labels]

    # Daily rolling average (7-day)
    daily_esc_rates = []
    for i, dt in enumerate(daily_dates):
        window_start = max(0, i - 6)
        window = daily_dates[window_start:i+1]
        s = sum(daily[d]['success'] for d in window)
        e = sum(daily[d]['escape'] for d in window)
        rate = round(100 * s / max(s + e, 1), 1)
        daily_esc_rates.append(rate)

    # Activity chart
    act_top = activities.most_common(10)
    act_labels = [f"'{a[0]}'" for a in act_top]
    act_values = [a[1] for a in act_top]

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Relatorio Desfralde - Isaac</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --blue: #3b82f6;
    --green: #22c55e;
    --red: #ef4444;
    --orange: #f59e0b;
    --purple: #8b5cf6;
    --gray: #6b7280;
    --bg: #f8fafc;
    --card: #ffffff;
    --border: #e2e8f0;
    --text: #1e293b;
    --muted: #64748b;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 20px;
    max-width: 1100px;
    margin: 0 auto;
  }}
  h1 {{
    font-size: 1.8rem;
    margin-bottom: 4px;
    color: var(--text);
  }}
  .subtitle {{
    color: var(--muted);
    font-size: 0.95rem;
    margin-bottom: 24px;
  }}
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
    margin-bottom: 28px;
  }}
  .kpi {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px;
    text-align: center;
  }}
  .kpi .value {{
    font-size: 2rem;
    font-weight: 700;
    line-height: 1.2;
  }}
  .kpi .label {{
    font-size: 0.8rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  .kpi.green .value {{ color: var(--green); }}
  .kpi.red .value {{ color: var(--red); }}
  .kpi.blue .value {{ color: var(--blue); }}
  .kpi.orange .value {{ color: var(--orange); }}
  .kpi.purple .value {{ color: var(--purple); }}

  .section {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
  }}
  .section h2 {{
    font-size: 1.1rem;
    margin-bottom: 16px;
    color: var(--text);
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .section h2 .icon {{ font-size: 1.3rem; }}

  .chart-container {{
    position: relative;
    height: 280px;
    width: 100%;
  }}
  .chart-container.tall {{
    height: 320px;
  }}

  .grid-2 {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
  }}
  @media (max-width: 768px) {{
    .grid-2 {{ grid-template-columns: 1fr; }}
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
  }}
  th {{
    text-align: left;
    padding: 8px 10px;
    border-bottom: 2px solid var(--border);
    font-weight: 600;
    color: var(--muted);
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }}
  td {{
    padding: 7px 10px;
    border-bottom: 1px solid var(--border);
  }}
  tr:last-child td {{ border-bottom: none; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .good {{ color: var(--green); font-weight: 600; }}
  .bad {{ color: var(--red); font-weight: 600; }}
  .neutral {{ color: var(--muted); }}

  .bar-bg {{
    background: #e2e8f0;
    border-radius: 4px;
    height: 8px;
    width: 100%;
    position: relative;
    overflow: hidden;
  }}
  .bar-fill {{
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s;
  }}
  .bar-fill.green {{ background: var(--green); }}
  .bar-fill.red {{ background: var(--red); }}
  .bar-fill.blue {{ background: var(--blue); }}

  .insight {{
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 12px;
    font-size: 0.9rem;
  }}
  .insight strong {{
    display: block;
    margin-bottom: 4px;
    color: #92400e;
  }}
  .insight:last-child {{ margin-bottom: 0; }}

  .tag {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
  }}
  .tag-green {{ background: #dcfce7; color: #166534; }}
  .tag-red {{ background: #fee2e2; color: #991b1b; }}
  .tag-blue {{ background: #dbeafe; color: #1e40af; }}
  .tag-orange {{ background: #fef3c7; color: #92400e; }}

  .footer {{
    text-align: center;
    color: var(--muted);
    font-size: 0.8rem;
    margin-top: 24px;
    padding: 12px;
  }}
</style>
</head>
<body>

<h1>Relatorio de Desfralde - Isaac</h1>
<p class="subtitle">Periodo: {first_date} a {last_date} ({total_days} dias) &middot; {len(events)} registros totais</p>

<!-- KPIs -->
<div class="kpi-grid">
  <div class="kpi green">
    <div class="value">{100*len(successes)/len(real):.0f}%</div>
    <div class="label">Taxa de Sucesso</div>
  </div>
  <div class="kpi red">
    <div class="value">{len(escapes)/total_days:.1f}</div>
    <div class="label">Escapes / Dia</div>
  </div>
  <div class="kpi blue">
    <div class="value">{len(successes)/total_days:.0f}</div>
    <div class="label">Sucessos / Dia</div>
  </div>
  <div class="kpi purple">
    <div class="value">{100*(init_counts.get('sozinho',0)+init_counts.get('pediu',0))/len(successes):.0f}%</div>
    <div class="label">Independencia</div>
  </div>
  <div class="kpi orange">
    <div class="value">{avg_iv:.0f}min</div>
    <div class="label">Intervalo Medio</div>
  </div>
  <div class="kpi green">
    <div class="value">{100*len(coco_ok)/max(len(cocos),1):.0f}%</div>
    <div class="label">Coco no Vaso</div>
  </div>
</div>

<!-- Weekly Evolution Chart -->
<div class="section">
  <h2><span class="icon">📈</span> Evolucao Semanal</h2>
  <div class="chart-container tall">
    <canvas id="weeklyChart"></canvas>
  </div>
</div>

<!-- Success Rate Trend -->
<div class="section">
  <h2><span class="icon">📊</span> Taxa de Sucesso - Media Movel 7 dias</h2>
  <div class="chart-container">
    <canvas id="trendChart"></canvas>
  </div>
</div>

<div class="grid-2">
  <!-- Independence Trend -->
  <div class="section">
    <h2><span class="icon">🧠</span> Independencia por Semana</h2>
    <div class="chart-container">
      <canvas id="indepChart"></canvas>
    </div>
  </div>

  <!-- Period of Day -->
  <div class="section">
    <h2><span class="icon">🕐</span> Escapes por Periodo</h2>
    <div class="chart-container">
      <canvas id="periodChart"></canvas>
    </div>
  </div>
</div>

<div class="grid-2">
  <!-- Day of Week -->
  <div class="section">
    <h2><span class="icon">📅</span> Escapes por Dia da Semana</h2>
    <div class="chart-container">
      <canvas id="dowChart"></canvas>
    </div>
  </div>

  <!-- Activities -->
  <div class="section">
    <h2><span class="icon">🎯</span> Atividade Durante Escapes</h2>
    <div class="chart-container">
      <canvas id="actChart"></canvas>
    </div>
  </div>
</div>

<!-- Weekly Table -->
<div class="section">
  <h2><span class="icon">📋</span> Dados Semanais Detalhados</h2>
  <table>
    <thead>
      <tr>
        <th>Semana</th>
        <th class="num">Dias</th>
        <th class="num">Sucesso</th>
        <th class="num">Escape</th>
        <th class="num">Nao Fez</th>
        <th class="num">% Sucesso</th>
        <th class="num">Esc/Dia</th>
        <th class="num">% Indep.</th>
        <th>Tendencia</th>
      </tr>
    </thead>
    <tbody>
"""

    for wk in week_keys:
        w = weekly[wk]
        total_w = w['success'] + w['escape']
        days = len(w['days'])
        pct = 100 * w['success'] / total_w if total_w > 0 else 0
        epd = w['escape'] / days if days > 0 else 0
        ipct = 100 * w['sozinho'] / w['success'] if w['success'] > 0 else 0
        pct_class = 'good' if pct >= 80 else ('bad' if pct < 75 else '')
        epd_class = 'bad' if epd >= 3 else ('good' if epd <= 2 else '')
        html += f"""      <tr>
        <td>{wk}</td>
        <td class="num">{days}</td>
        <td class="num good">{w['success']}</td>
        <td class="num bad">{w['escape']}</td>
        <td class="num neutral">{w['nao_fez']}</td>
        <td class="num {pct_class}">{pct:.0f}%</td>
        <td class="num {epd_class}">{epd:.1f}</td>
        <td class="num">{ipct:.0f}%</td>
        <td><div class="bar-bg"><div class="bar-fill green" style="width:{pct}%"></div></div></td>
      </tr>
"""

    html += """    </tbody>
  </table>
</div>

<!-- Initiative Breakdown -->
<div class="grid-2">
  <div class="section">
    <h2><span class="icon">🤝</span> Iniciativa nos Sucessos</h2>
    <table>
      <thead><tr><th>Tipo</th><th class="num">Qtd</th><th class="num">%</th><th></th></tr></thead>
      <tbody>
"""
    init_labels = {'levei': 'Adulto levou', 'sozinho': 'Foi sozinho', 'pediu': 'Pediu', 'mandei': 'Adulto mandou/ofertou', '': 'Nao especificado'}
    init_colors = {'levei': 'blue', 'sozinho': 'green', 'pediu': 'green', 'mandei': 'blue', '': 'neutral'}
    for init, count in init_counts.most_common():
        pct = 100 * count / len(successes)
        label = init_labels.get(init, init)
        color = init_colors.get(init, '')
        html += f"""        <tr>
          <td><span class="tag tag-{color}">{label}</span></td>
          <td class="num">{count}</td>
          <td class="num">{pct:.0f}%</td>
          <td><div class="bar-bg"><div class="bar-fill {color}" style="width:{pct}%"></div></div></td>
        </tr>
"""

    html += f"""      </tbody>
    </table>
  </div>

  <div class="section">
    <h2><span class="icon">💩</span> Analise de Coco</h2>
    <table>
      <thead><tr><th>Metrica</th><th class="num">Valor</th></tr></thead>
      <tbody>
        <tr><td>Total de cocos</td><td class="num">{len(cocos)}</td></tr>
        <tr><td>No vaso</td><td class="num good">{len(coco_ok)} ({100*len(coco_ok)/max(len(cocos),1):.0f}%)</td></tr>
        <tr><td>Escape</td><td class="num bad">{len(coco_esc)} ({100*len(coco_esc)/max(len(cocos),1):.0f}%)</td></tr>
        <tr><td>Foi sozinho</td><td class="num good">{len(coco_sozinho)} ({100*len(coco_sozinho)/max(len(cocos),1):.0f}%)</td></tr>
        <tr><td>Media por semana</td><td class="num">{len(cocos)/max(len(week_keys),1):.1f}</td></tr>
      </tbody>
    </table>
  </div>
</div>

<!-- Insights -->
<div class="section">
  <h2><span class="icon">💡</span> Insights e Observacoes</h2>

  <div class="insight">
    <strong>1. Plato na taxa de sucesso</strong>
    A taxa de sucesso oscila entre 71-82% ao longo de 8 semanas sem tendencia clara de melhora.
    O protocolo atual (levar a cada 1h) parece ter atingido seu limite de eficacia.
    A alta dependencia do adulto (57% "levei") sugere que Isaac ainda nao internalizou a rotina.
  </div>

  <div class="insight">
    <strong>2. Noite e o periodo mais critico</strong>
    {period_data['Noite (18-24h)']['escape']} escapes a noite ({round(100*period_data['Noite (18-24h)']['escape']/max(period_data['Noite (18-24h)']['total'],1),1)}% de taxa de escape)
    vs {period_data['Tarde (12-18h)']['escape']} a tarde ({round(100*period_data['Tarde (12-18h)']['escape']/max(period_data['Tarde (12-18h)']['total'],1),1)}%).
    Possiveis fatores: cansaco, desregulacao sensorial, menor supervisao.
  </div>

  <div class="insight">
    <strong>3. Domingos tem mais escapes (31%)</strong>
    Taxa de escape no domingo e quase o dobro da segunda-feira (16.7%).
    Rotina menos estruturada no fim de semana pode ser um fator.
  </div>

  <div class="insight">
    <strong>4. Coco mostra boa autonomia</strong>
    {100*len(coco_sozinho)/max(len(cocos),1):.0f}% dos cocos Isaac foi sozinho. A autopercecao para coco
    parece mais desenvolvida que para xixi. Possivel hipotese: coco da sinais corporais mais claros.
  </div>

  <div class="insight">
    <strong>5. Escapes ligados a hiperfoco e sedentarismo</strong>
    Atividades mais comuns durante escapes: sofa/TV, jogando/tela, rede.
    Quando Isaac esta em hiperfoco (tela, brincadeira), parece nao perceber a necessidade.
    Considerar timer visual ou alerta durante atividades de tela.
  </div>

  <div class="insight">
    <strong>6. Independencia cresceu mas estabilizou em ~30%</strong>
    Crescimento rapido nas primeiras 3 semanas (7% &rarr; 33%), depois estabilizou.
    "Pediu" (comunicacao ativa) ainda muito baixo: apenas {init_counts.get('pediu',0)} vezes ({100*init_counts.get('pediu',0)/len(successes):.1f}%).
    O uso do iPad para modelagem na escola esta dando resultados (Vanessa registra mais pedidos).
  </div>

  <div class="insight">
    <strong>7. Padrao de "pinguinhos" frequentes</strong>
    Isaac vai frequentemente ao banheiro fazer pouca quantidade.
    Possibilidades: fuga de demanda (confirmado pelo psicologo em algumas situacoes),
    dificuldade de esvaziar completamente a bexiga, ou fase de aprendizado do controle do esfincter.
  </div>

  <div class="insight">
    <strong>8. "Levou mas nao fez" = {len(nao_fez)} vezes ({len(nao_fez)/total_days:.1f}/dia)</strong>
    Alta frequencia de idas improdutivas. Pode estar gerando resistencia.
    Semanas com mais "nao fez" (W03-W04: 26) coincidem com mudanca no protocolo (levar a cada 40min).
  </div>
</div>

<div class="footer">
  Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} &middot; Dados de {total_days} dias de registro &middot; {len(events)} eventos totais
</div>

<script>
const chartColors = {{
  green: '#22c55e',
  red: '#ef4444',
  blue: '#3b82f6',
  orange: '#f59e0b',
  purple: '#8b5cf6',
  gray: '#94a3b8',
  greenBg: 'rgba(34,197,94,0.15)',
  redBg: 'rgba(239,68,68,0.15)',
  blueBg: 'rgba(59,130,246,0.15)',
}};

Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.pointStyle = 'circle';

// Weekly stacked bar
new Chart(document.getElementById('weeklyChart'), {{
  type: 'bar',
  data: {{
    labels: [{','.join(week_labels)}],
    datasets: [
      {{ label: 'Sucesso', data: {week_success}, backgroundColor: chartColors.green, borderRadius: 4 }},
      {{ label: 'Escape', data: {week_escape}, backgroundColor: chartColors.red, borderRadius: 4 }},
      {{ label: 'Nao Fez', data: {week_nao_fez}, backgroundColor: chartColors.gray, borderRadius: 4 }},
    ]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      tooltip: {{
        callbacks: {{
          afterBody: function(ctx) {{
            const i = ctx[0].dataIndex;
            const s = {week_success}[i];
            const e = {week_escape}[i];
            const pct = Math.round(100 * s / (s + e));
            return 'Taxa sucesso: ' + pct + '%';
          }}
        }}
      }}
    }},
    scales: {{
      x: {{ stacked: true, grid: {{ display: false }} }},
      y: {{ stacked: true, grid: {{ color: '#f1f5f9' }} }}
    }}
  }}
}});

// 7-day rolling trend
new Chart(document.getElementById('trendChart'), {{
  type: 'line',
  data: {{
    labels: {[f"'{d[5:]}'" for d in daily_dates]},
    datasets: [{{
      label: '% Sucesso (7d)',
      data: {daily_esc_rates},
      borderColor: chartColors.green,
      backgroundColor: chartColors.greenBg,
      fill: true,
      tension: 0.3,
      pointRadius: 0,
      borderWidth: 2.5,
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: false }}
    }},
    scales: {{
      x: {{ grid: {{ display: false }}, ticks: {{ maxTicksLimit: 10 }} }},
      y: {{ min: 50, max: 100, grid: {{ color: '#f1f5f9' }},
        ticks: {{ callback: v => v + '%' }} }}
    }}
  }}
}});

// Independence trend
new Chart(document.getElementById('indepChart'), {{
  type: 'bar',
  data: {{
    labels: [{','.join(week_labels)}],
    datasets: [{{
      label: '% Independente',
      data: {week_indep_pct},
      backgroundColor: chartColors.purple,
      borderRadius: 6,
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ grid: {{ display: false }} }},
      y: {{ min: 0, max: 50, grid: {{ color: '#f1f5f9' }},
        ticks: {{ callback: v => v + '%' }} }}
    }}
  }}
}});

// Period chart
new Chart(document.getElementById('periodChart'), {{
  type: 'bar',
  data: {{
    labels: {[f"'{p}'" for p in period_labels]},
    datasets: [{{
      label: '% Escape',
      data: {period_esc_pct},
      backgroundColor: [chartColors.orange, chartColors.green, chartColors.red],
      borderRadius: 6,
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        callbacks: {{
          afterLabel: function(ctx) {{
            const totals = {period_totals};
            const escs = {period_escapes};
            return escs[ctx.dataIndex] + ' escapes de ' + totals[ctx.dataIndex] + ' eventos';
          }}
        }}
      }}
    }},
    scales: {{
      x: {{ min: 0, max: 35, grid: {{ color: '#f1f5f9' }},
        ticks: {{ callback: v => v + '%' }} }},
      y: {{ grid: {{ display: false }} }}
    }}
  }}
}});

// Day of week
new Chart(document.getElementById('dowChart'), {{
  type: 'bar',
  data: {{
    labels: ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom'],
    datasets: [{{
      label: '% Escape',
      data: {dow_esc_pct},
      backgroundColor: {dow_esc_pct}.map(v => v >= 25 ? chartColors.red : (v >= 20 ? chartColors.orange : chartColors.blue)),
      borderRadius: 6,
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ grid: {{ display: false }} }},
      y: {{ min: 0, max: 40, grid: {{ color: '#f1f5f9' }},
        ticks: {{ callback: v => v + '%' }} }}
    }}
  }}
}});

// Activities
new Chart(document.getElementById('actChart'), {{
  type: 'bar',
  data: {{
    labels: [{','.join(act_labels)}],
    datasets: [{{
      label: 'Escapes',
      data: {act_values},
      backgroundColor: chartColors.orange,
      borderRadius: 6,
    }}]
  }},
  options: {{
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ grid: {{ color: '#f1f5f9' }} }},
      y: {{ grid: {{ display: false }} }}
    }}
  }}
}});
</script>

</body>
</html>"""

    return html

if __name__ == '__main__':
    events = load_csv('/Users/tony/work/solo/xixicoco/isaac_desfralde.csv')
    html = generate_html(events)
    with open('/Users/tony/work/solo/xixicoco/relatorio_desfralde.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("HTML report generated: relatorio_desfralde.html")
