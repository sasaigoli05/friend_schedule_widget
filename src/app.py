import csv
import json
import re
from pathlib import Path
from html import escape

# ---------- CONFIG ----------
CSV_PATH = "/Users/suhanasaigoli/Desktop/Projects/friend_schedule_widget/data/schedule.csv"
OUT_HTML = "schedule_dashboard.html"     # your output HTML
ICONS_DIR = "icons"                      # where you’ll put person PNGs

# Map day codes to JS Date.getDay() values (Sun=0 ... Sat=6)
DAY_MAP = {
    "MWF":  [1, 3, 5],
    "TTH":  [2, 4],
    "MON":  [1],
    "TUE":  [2],
    "WED":  [3],
    "THU":  [4],
    "FRI":  [5],
}

# Regex for entries like: TTH14001515-psyc  or  MWF09301015-bio
ENTRY_RE = re.compile(r"^(MWF|TTH|MON|TUE|WED|THU|FRI)(\d{4})(\d{4})-(.+)$", re.IGNORECASE)

def to_minutes(hhmm: str) -> int:
    hh = int(hhmm[:2])
    mm = int(hhmm[2:])
    return hh * 60 + mm

def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "", name.strip().lower().replace(" ", "_"))

def parse_entry(token: str):
    token = token.strip()
    if not token:
        return None
    m = ENTRY_RE.match(token)
    if not m:
        return None
    code, start, end, course = m.groups()
    days = DAY_MAP.get(code.upper(), [])
    return {
        "days": days,                       # e.g., [2,4]
        "start_min": to_minutes(start),     # e.g., 1400 -> 14*60
        "end_min": to_minutes(end),         # e.g., 1515
        "course": course.strip()
    }

def read_csv(path: str):
    """
    CSV format:
    First column = person name
    Remaining columns = zero or more class codes, e.g. TTH14001515-psyc
    """
    people = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            name = row[0].strip()
            if not name:
                continue
            entries = []
            for cell in row[1:]:
                if cell and cell.strip():
                    parsed = parse_entry(cell)
                    if parsed:
                        entries.append(parsed)
            people.append({
                "name": name,
                "slug": slugify(name),
                "entries": entries
            })
    return people

def build_html(people):
    data_json = json.dumps(people, separators=(",", ":"))

    # Inline CSS + JS for a drop-in static page
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Class Status Dashboard</title>
<style>
  :root {{
    --bg: #0b1220;
    --card: #121a2a;
    --text: #e8eefb;
    --muted: #a9b3c7;
    --green: #3ddc84;
    --red: #ff5d5d;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px; background: var(--bg); color: var(--text);
    font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
  }}
  header {{
    display: flex; align-items: baseline; justify-content: space-between; gap: 16px; flex-wrap: wrap;
    margin-bottom: 20px;
  }}
  h1 {{ font-size: 24px; margin: 0; }}
  #now {{
    font-variant-numeric: tabular-nums; color: var(--muted); font-size: 14px;
  }}

  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
    gap: 16px;
  }}
  .card {{
    background: var(--card);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: 16px;
    display: flex; flex-direction: column; align-items: center; gap: 10px;
    box-shadow: 0 10px 20px rgba(0,0,0,0.18);
  }}
  .avatar {{
    width: 96px; height: 96px; border-radius: 50%; overflow: hidden;
    background: #0d1322; display: grid; place-items: center;
    border: 2px solid rgba(255,255,255,0.1);
  }}
  .avatar img {{ width: 100%; height: 100%; object-fit: cover; }}
  .name {{ font-weight: 700; text-align: center; }}
  .status {{
    display: inline-flex; align-items: center; gap: 8px;
    padding: 6px 10px; border-radius: 999px; font-size: 12px;
    background: rgba(255,255,255,0.05); color: var(--muted);
  }}
  .dot {{
    width: 10px; height: 10px; border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 0 2px rgba(0,0,0,0.15) inset;
  }}
  .dot.on {{ background: var(--red); }}
  .course {{ color: var(--text); font-size: 13px; text-align: center; min-height: 1.2em; }}
  .small {{ color: var(--muted); font-size: 12px; }}
  footer {{ margin-top: 24px; color: var(--muted); font-size: 12px; }}
  a, a:visited {{ color: #93b7ff; text-decoration: none; }}
</style>
</head>
<body>
<header>
  <h1>Class Status Dashboard</h1>
  <div id="now">—</div>
</header>

<div id="app" class="grid"></div>


<script>
const PEOPLE = {data_json};

function minutesNowLocal(d) {{
  return d.getHours() * 60 + d.getMinutes();
}}

// Returns the matching class (or null) for a person at a given Date
function getCurrentClass(entryList, now) {{
  const day = now.getDay(); // Sun=0 ... Sat=6
  const mins = minutesNowLocal(now);
  for (const e of entryList) {{
    if (e.days.includes(day) && mins >= e.start_min && mins < e.end_min) {{
      return e;
    }}
  }}
  return null;
}}

function fmtTime(d) {{
  // e.g., "Tue • 2:07 PM"
  const day = d.toLocaleDateString(undefined, {{ weekday: 'short' }});
  const time = d.toLocaleTimeString(undefined, {{ hour: 'numeric', minute: '2-digit' }});
  return `${{day}} • ${{time}}`;
}}

function render() {{
  const app = document.getElementById('app');
  const nowLbl = document.getElementById('now');
  const now = new Date();
  nowLbl.textContent = fmtTime(now);

  app.innerHTML = '';

  for (const p of PEOPLE) {{
    const cur = getCurrentClass(p.entries, now);
    const hasClass = !!cur;
    const iconPath = '{escape(ICONS_DIR)}/' + p.slug + '.png';

    const card = document.createElement('div');
    card.className = 'card';

    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    const img = document.createElement('img');
    img.alt = p.name;
    img.src = iconPath;
    img.onerror = () => {{
      // fallback SVG avatar
      avatar.innerHTML = `
        <svg viewBox="0 0 128 128" width="96" height="96" role="img" aria-label="avatar">
          <circle cx="64" cy="48" r="28" fill="#1f2a44"/>
          <rect x="16" y="78" width="96" height="38" rx="19" fill="#1f2a44"/>
        </svg>`;
    }};
    avatar.appendChild(img);
    card.appendChild(avatar);

    const name = document.createElement('div');
    name.className = 'name';
    name.textContent = p.name;
    card.appendChild(name);

    const status = document.createElement('div');
    status.className = 'status';
    const dot = document.createElement('span');
    dot.className = 'dot' + (hasClass ? ' on' : '');
    status.appendChild(dot);
    const label = document.createElement('span');
    label.textContent = hasClass ? 'In class' : 'Free';
    status.appendChild(label);
    card.appendChild(status);

    const course = document.createElement('div');
    course.className = 'course';
    course.textContent = hasClass ? cur.course : '';
    card.appendChild(course);

    // Optional next-up line (nearest upcoming class today)
    const mins = minutesNowLocal(now);
    const today = p.entries
      .filter(e => e.days.includes(now.getDay()) && e.start_min > mins)
      .sort((a,b) => a.start_min - b.start_min);
    const small = document.createElement('div');
    small.className = 'small';
    if (today.length) {{
      const nxt = today[0];
      const hh = String(Math.floor(nxt.start_min/60)).padStart(2,'0');
      const mm = String(nxt.start_min%60).padStart(2,'0');
      small.textContent = 'Next: ' + nxt.course + ' at ' + hh + ':' + mm;
    }} else {{
      small.textContent = 'No more classes today';
    }}
    card.appendChild(small);

    app.appendChild(card);
  }}
}}

render();
setInterval(render, 30 * 1000); // refresh every 30s
</script>
</body>
</html>
"""
    return html

def main():
    people = read_csv(CSV_PATH)
    Path(OUT_HTML).write_text(build_html(people), encoding="utf-8")
    print(f"✓ Wrote {OUT_HTML}\n"
          f"Place PNGs in ./{ICONS_DIR}/ like suhan.png, raghav.png (up to 6 unique now).")

if __name__ == "__main__":
    main()
