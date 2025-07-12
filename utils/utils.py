import requests
import pandas as pd

def get_option_chain_data():
    url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nseindia.com/option-chain"
    }

    session = requests.Session()
    session.headers.update(headers)

    homepage = "https://www.nseindia.com"
    try:
        # Hit homepage first to get cookies
        res = session.get(homepage, timeout=5)
        if res.status_code != 200:
            raise ValueError(f"Failed to get NSE homepage cookies, status: {res.status_code}")
    except Exception as e:
        raise ValueError(f"Error accessing NSE homepage: {e}")

    # Now get the option chain data with the same session
    response = session.get(url, timeout=5)
    if response.status_code != 200:
        raise ValueError(f"NSE API returned error status: {response.status_code}")

    data = response.json()

    spot_price = data['records']['underlyingValue']
    all_data = data['records']['data']

    ce_data, pe_data = [], []

    for item in all_data:
        strike = item.get("strikePrice")
        ce_oi = item.get("CE", {}).get("openInterest", 0)
        pe_oi = item.get("PE", {}).get("openInterest", 0)

        if strike is not None and (ce_oi != 0 or pe_oi != 0):
            ce_data.append([strike, ce_oi])
            pe_data.append([strike, pe_oi])

    df_ce = pd.DataFrame(ce_data, columns=['Strike', 'CE_OI'])
    df_pe = pd.DataFrame(pe_data, columns=['Strike', 'PE_OI'])
    df = df_ce.merge(df_pe, on='Strike')
    df['Total_OI'] = df['CE_OI'] + df['PE_OI']
    df['PCR'] = df['PE_OI'] / df['CE_OI'].replace(0, 1)

    df_filtered = df[(df['Strike'] >= spot_price - 300) & (df['Strike'] <= spot_price + 300)]
    df_filtered = df_filtered.sort_values("Strike").reset_index(drop=True)

    return df_filtered, spot_price

def analyze_oi(df, spot_price):
    # Find top 2 supports (highest PE OI) below or near spot
    supports = df[df['Strike'] <= spot_price].sort_values(by='PE_OI', ascending=False).head(2)['Strike'].tolist()
    if len(supports) < 2:
        below_spot = df[df['Strike'] <= spot_price]['Strike'].sort_values(ascending=False).tolist()
        for s in below_spot:
            if s not in supports and len(supports) < 2:
                supports.append(s)

    # Find top 2 resistances (highest CE OI) above or near spot
    resistances = df[df['Strike'] >= spot_price].sort_values(by='CE_OI', ascending=False).head(2)['Strike'].tolist()
    if len(resistances) < 2:
        above_spot = df[df['Strike'] >= spot_price]['Strike'].sort_values(ascending=True).tolist()
        for r in above_spot:
            if r not in resistances and len(resistances) < 2:
                resistances.append(r)

    supports = sorted(supports)
    resistances = sorted(resistances)

    suggestion = ""
    target = None

    if spot_price < supports[0]:
        suggestion = f"🟢 Bounce expected from strong support at {supports[0]}"
        target = resistances[0]
    elif spot_price > resistances[-1]:
        suggestion = f"🔴 Pullback expected from strong resistance at {resistances[-1]}"
        target = supports[-1]
    elif supports[0] <= spot_price <= resistances[-1]:
        nearest_strike = df.iloc[(df['Strike'] - spot_price).abs().argsort()[:1]]['Strike'].values[0]
        pe_near = df[df['Strike'] == nearest_strike]['PE_OI'].values[0]
        ce_near = df[df['Strike'] == nearest_strike]['CE_OI'].values[0]

        if pe_near > ce_near:
            suggestion = "🟢 Bullish bias near spot"
            target = resistances[-1]
        elif ce_near > pe_near:
            suggestion = "🔴 Bearish bias near spot"
            target = supports[0]
        else:
            suggestion = "⚪ Range-bound market near spot"
            target = None
    else:
        suggestion = "⚠️ Spot outside monitored range"
        target = None

    return suggestion, supports, resistances, target
