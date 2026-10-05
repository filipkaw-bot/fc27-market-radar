import json, os, math, hashlib, time
from datetime import datetime, timezone
from market_provider import MarketProvider

TAX = 0.05
MARKET_PAGES = 4
PAGE_DELAY_SECONDS = 13

def first(o, *keys, default=None):
    for k in keys:
        if isinstance(o, dict) and o.get(k) is not None:
            return o[k]
    return default

def number(v):
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return float(v.replace(",", "").replace(" ", "").strip())
        except ValueError:
            return None
    return None

def flatten(data):
    p = first(data, "players", "items", "data", default=[]) or []
    if isinstance(p, dict):
        p = first(p, "players", "items", "data", default=[])
    return p if isinstance(p, list) else []

def market_snapshot(provider, pages=MARKET_PAGES):
    """Fetch one shared cheap-market snapshot instead of querying once per EVO/position.
    This keeps the free Parse tier under its 5 requests/minute rate limit.
    """
    all_players = []
    seen = set()

    for page in range(1, pages + 1):
        params = {
            "page": page,
            "sort_by": "price",
            "sort_order": "asc",
            "min_rating": 1,
            "max_rating": 99,
        }
        for attempt in range(2):
            try:
                data = provider.players(**params)
                players = flatten(data)
                break
            except Exception as e:
                print(f"market page {page} attempt {attempt + 1} failed: {e}")
                if attempt == 0 and "429" in str(e):
                    time.sleep(PAGE_DELAY_SECONDS)
                    continue
                players = []
                break

        if not players:
            break

        for p in players:
            card_id = str(first(p, "card_id", "id", default=""))
            price = number(first(p, "price"))
            if not card_id or price is None or price <= 0 or card_id in seen:
                continue
            seen.add(card_id)
            rating = number(first(p, "rating"))
            all_players.append({
                "card_id": card_id,
                "name": first(p, "name", default="Unknown"),
                "rating": int(rating) if rating is not None else None,
                "position": first(p, "position"),
                "league": first(p, "league"),
                "club": first(p, "club"),
                "nation": first(p, "nation"),
                "card_type": first(p, "card_type"),
                "price": int(price),
            })

        print(f"market page {page}: {len(players)} rows")
        if len(players) < 30:
            break
        if page < pages:
            time.sleep(PAGE_DELAY_SECONDS)

    return all_players

def qualifies(p, req):
    max_rating = req.get("overall_max")
    rating = p.get("rating")
    if max_rating is not None and rating is not None and rating > int(max_rating):
        return False
    positions = set(req.get("positions") or [])
    excluded = set(req.get("excluded_positions") or [])
    pos = p.get("position")
    if positions and pos not in positions:
        return False
    if pos in excluded:
        return False
    return True

def score_pool(pool, evo_name):
    if not pool:
        return []
    prices = sorted(x["price"] for x in pool)
    median = prices[len(prices) // 2]
    result = []

    for x in pool:
        rank = sum(1 for p in prices if p <= x["price"])
        discount = (median - x["price"]) / median if median else 0
        near = sum(1 for p in prices if p <= x["price"] * 1.15)

        score = 50
        score += min(20, max(0, round(discount * 40)))
        if rank <= 3:
            score += 12
        elif rank <= 7:
            score += 6
        if near <= 2:
            score += 10
        elif near <= 5:
            score += 5
        if len(prices) <= 8:
            score += 5

        score = min(100, score)
        x = dict(x)
        x.update({
            "evolution": evo_name,
            "score": score,
            "action": "buy" if score >= 85 else ("watch" if score >= 60 else "skip"),
            "net_sale": math.floor(x["price"] * (1 - TAX)),
            "potential_vs_median": round(discount * 100, 1),
            "qualifying_cards_found": len(prices),
            "price_rank": rank,
            "price_percentile": round(rank / len(prices) * 100, 1),
            "supply_proxy": near,
            "tags": ["EVO", "ELIGIBLE"],
            "why": (
                f"{evo_name}: {len(prices)} kwalifikujących kart znalezionych w "
                f"wspólnym skanie rynku. Ta karta jest #{rank} cenowo i "
                f"{round(discount * 100, 1)}% poniżej mediany. W promieniu +15% "
                f"ceny jest {near} kart. To proxy ograniczonej podaży, nie licznik live aukcji."
            ),
        })
        if rank <= 3:
            x["tags"].append("LOW PRICE")
        if near <= 2:
            x["tags"].append("BOTTLENECK PROXY")
        if len(prices) <= 8:
            x["tags"].append("LOW QUALIFIER COUNT")
        result.append(x)

    return result

def run():
    provider = MarketProvider(platform=os.getenv("FC27_PLATFORM", "ps"))
    if not provider.enabled:
        raise RuntimeError("PARSE_API_KEY missing")

    with open("data/opportunities.json", encoding="utf-8") as f:
        content = json.load(f)

    evos = [x for x in content if x.get("kind") == "Evolutions" and x.get("requirements")]
    fingerprint = hashlib.sha256(
        json.dumps(evos, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()

    try:
        with open("data/market.json", encoding="utf-8") as f:
            old = json.load(f)
    except Exception:
        old = {}

    if old.get("content_fingerprint") == fingerprint and old.get("opportunities"):
        print("content unchanged; keeping existing market scan")
        return

    snapshot = market_snapshot(provider)
    rows = []

    for evo in evos[:12]:
        pool = [dict(p) for p in snapshot if qualifies(p, evo["requirements"])]
        rows.extend(score_pool(pool, evo["name"]))

    dedup = {}
    for x in rows:
        dedup[(x["card_id"], x["evolution"])] = x
    rows = list(dedup.values())
    rows.sort(key=lambda x: (x.get("score", 0), x.get("potential_vs_median", 0)), reverse=True)

    payload = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "content_fingerprint": fingerprint,
        "provider": provider.health(),
        "content_triggers": len(evos),
        "market_pages": MARKET_PAGES,
        "market_rows_scanned": len(snapshot),
        "scoring_note": "Supply is a price-distribution proxy; no live auction-count claim is made.",
        "opportunities": rows[:150],
    }

    os.makedirs("data", exist_ok=True)
    with open("data/market.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("market rows scanned:", len(snapshot))
    print("market opportunities:", len(rows))

if __name__ == "__main__":
    run()
