#!/usr/bin/env python3
"""Download DAILY VIX, MOVE, HY OAS, BTC and build a static Fear Score dashboard.

This is an unofficial composite, not Fundstrat's original proprietary series.
The score uses a fixed-sample z-score normalization (2020-01-01 to 2026-11-30).
Requires: requests, pandas, yfinance. Data providers may block unauthenticated access.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import math
import os
import pathlib
import statistics
import sys
import time
from bisect import bisect_right
from typing import Dict
from urllib.parse import quote

import requests

BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
OUT = BASE_DIR / "site" / "data.js"
START = dt.date(2020, 1, 1)
BASE_END = dt.date(2026, 11, 30)
END = dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=2)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FearScoreDashboard/1.0; personal research)", "Accept": "text/csv,application/json,*/*"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def download(url: str) -> requests.Response:
    err = None
    for attempt in range(3):
        try:
            r = SESSION.get(url, timeout=45)
            r.raise_for_status()
            if len(r.content) < 100:
                raise ValueError("too few bytes in response")
            return r
        except Exception as e:
            err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Failed fetching {url}: {err}")


def parse_csv(text: str, date_col: str, value_col: str) -> Dict[dt.date, float]:
    rdr = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if not rdr.fieldnames:
        raise ValueError("No CSV header found")
    original = {name.strip().upper(): name for name in rdr.fieldnames}
    dc = original.get(date_col.upper())
    vc = original.get(value_col.upper())
    if not dc or not vc:
        raise ValueError(f"Missing columns {date_col}/{value_col}; got {rdr.fieldnames}")
    result = {}
    for row in rdr:
        day = row.get(dc, '').strip()
        raw = row.get(vc, '').strip().replace(',', '')
        if not day or raw in ('', '.', 'NA', 'N/A', 'null'):
            continue
        try:
            date = dt.datetime.strptime(day, '%m/%d/%Y').date() if '/' in day else dt.date.fromisoformat(day)
            val = float(raw)
            if math.isfinite(val) and val > 0 and START - dt.timedelta(days=12) <= date < END:
                result[date] = val
        except (ValueError, TypeError):
            continue
    if len(result) < 200:
        raise ValueError(f"Only {len(result)} valid daily rows in {value_col}")
    return result


def fetch_vix():
    urls = [
        'https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv',
        'https://cdn-api.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv',
    ]
    for url in urls:
        try:
            return parse_csv(download(url).text, 'DATE', 'CLOSE')
        except Exception as e:
            print('VIX provider failed:', repr(e), file=sys.stderr)
    raise RuntimeError('VIX: Cboe official CSV sources unavailable')


def fetch_fred():
    urls = [
        'https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2',
        'https://fred.stlouisfed.org/graph/fredgraph.csv?cosd=2020-01-01&id=BAMLH0A0HYM2',
    ]
    for url in urls:
        try:
            text = download(url).text
            for label in ('DATE', 'observation_date'):
                try:
                    return parse_csv(text, label, 'BAMLH0A0HYM2')
                except ValueError:
                    pass
        except Exception as e:
            print('FRED provider failed:', repr(e), file=sys.stderr)
    raise RuntimeError('HY OAS: FRED CSV unavailable')


def fetch_yahoo_chart(ticker: str) -> Dict[dt.date, float]:
    t0 = int(dt.datetime(2019, 12, 20, tzinfo=dt.timezone.utc).timestamp())
    t1 = int(dt.datetime.combine(END, dt.time.min, dt.timezone.utc).timestamp())
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker, safe="")}?period1={t0}&period2={t1}&interval=1d'
    obj = download(url).json()['chart']['result'][0]
    ts = obj['timestamp']
    close = obj['indicators']['quote'][0]['close']
    pairs = {}
    for t, p in zip(ts, close):
        if p is not None and math.isfinite(float(p)) and p > 0:
            day = dt.datetime.fromtimestamp(t, tz=dt.timezone.utc).date()
            if day >= START - dt.timedelta(days=12):
                pairs[day] = float(p)
    return pairs


def fetch_yahoo(ticker: str) -> Dict[dt.date, float]:
    try:
        import yfinance as yf
        history = yf.Ticker(ticker).history(start='2019-12-20', end=END.isoformat(), auto_adjust=False, raise_errors=True)
        pairs = {}
        for index, row in history.iterrows():
            price = float(row['Close'])
            if math.isfinite(price) and price > 0:
                day = index.date()
                if day >= START - dt.timedelta(days=12):
                    pairs[day] = price
        if len(pairs) >= 200:
            return pairs
        print(f'yfinance {ticker} returned only {len(pairs)} rows', file=sys.stderr)
    except Exception as e:
        print(f'yfinance failed for {ticker}: {e}', file=sys.stderr)
    pairs = fetch_yahoo_chart(ticker)
    if len(pairs) < 200:
        raise RuntimeError(f'Yahoo {ticker}: Only {len(pairs)} rows found')
    return pairs


def asof_value(series: Dict[dt.date, float], keys: list, date: dt.date, max_days: int):
    k = bisect_right(keys, date) - 1
    if k < 0 or (date - keys[k]).days > max_days:
        return None
    return series[keys[k]]


def make_dataset(vix, move, oas, btc):
    move_keys, oas_keys, btc_keys = (sorted(x) for x in (move, oas, btc))
    raw = []
    # VIX series defines US equity market sessions; market holidays are omitted.
    for date in sorted(vix):
        if date < START:
            continue
        m = asof_value(move, move_keys, date, 4)
        o = asof_value(oas, oas_keys, date, 7)
        b = asof_value(btc, btc_keys, date, 3)
        if m is None or o is None or b is None:
            continue
        raw.append({'date': date.isoformat(), 'vix': vix[date], 'move': m, 'oas': o, 'btc': b})
    base = [r for r in raw if START <= dt.date.fromisoformat(r['date']) <= BASE_END]
    if len(base) < 300:
        raise RuntimeError(f'Cannot compute baseline from just {len(base)} observations')
    moments = {}
    for key in ('vix', 'move', 'oas'):
        vals = [r[key] for r in base]
        moments[key] = (statistics.mean(vals), statistics.pstdev(vals))
        if moments[key][1] <= 1e-9:
            raise RuntimeError(f'Zero standard deviation for {key}')
    final = []
    for r in raw:
        score = statistics.mean((r[key] - moments[key][0]) / moments[key][1] for key in ('vix', 'move', 'oas'))
        final.append({'date': r['date'], 'score': round(score, 4), 'btc': round(r['btc'], 2), 'vix': round(r['vix'], 2), 'move': round(r['move'], 2), 'oas': round(r['oas'], 3)})
    if not final:
        raise RuntimeError('Empty output')
    base_dates = [r['date'] for r in base]
    payload = {
        'status': 'ok',
        'meta': {
            'updated_utc': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
            'baseline_start': base_dates[0],
            'baseline_end': base_dates[-1],
            'baseline_count': len(base),
            'latest_date': final[-1]['date'],
            'extreme_count_all': sum(r['score'] >= 1.5 for r in final),
            'source_last_dates': {name: max(s).isoformat() for name, s in [('vix', vix), ('move', move), ('oas', oas), ('btc', btc)]},
            'notes': 'Latest available daily data, not intraday; HY OAS may be lagged. Unofficial reconstruction.'
        },
        'rows': final,
    }
    return payload


def main():
    print('Fetching Cboe VIX')
    vix = fetch_vix()
    print('Fetching FRED HY OAS')
    oas = fetch_fred()
    print('Fetching Yahoo ^MOVE')
    move = fetch_yahoo('^MOVE')
    print('Fetching Yahoo BTC-USD')
    btc = fetch_yahoo('BTC-USD')
    print('Observations:', {name: len(s) for name, s in [('VIX', vix), ('HY OAS', oas), ('MOVE', move), ('BTC', btc)]})
    data = make_dataset(vix, move, oas, btc)
    contents = '/* auto-generated; source scripts/update_data.py */\nwindow.FEARDATA = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n'
    OUT.write_text(contents, encoding='utf-8')
    print('Wrote', OUT, 'for', data['meta']['latest_date'], 'with', len(data['rows']), 'rows')


if __name__ == '__main__':
    main()
