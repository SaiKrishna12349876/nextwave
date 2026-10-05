"""
NxtWave Workshop Referral Tracker v2
------------------------------------
Single Flask service: landing page + registration + referral loop + admin funnel dashboard.

Endpoints
  GET  /                         landing page (register / share / referral count)
  GET  /dashboard                admin dashboard (needs ?key=ADMIN_KEY)
  POST /api/register             register a student  {name, college, branch, whatsapp, ref?, src?}
  GET  /api/stats                public counters (total, seats left, referrals)
  GET  /api/referrer/<code>      who owns a code (for "invited by X" banner)
  GET  /api/leaderboard          who referred how many (top 10, ?limit=N)
  GET  /api/share/<code>         pre-filled WhatsApp share link for a registrant
  GET  /api/admin/funnel         registrations by channel / college / day, K-factor   (ADMIN)
  GET  /api/admin/export.csv     full export                                           (ADMIN)
  GET  /api/messages/<day>       the WhatsApp broadcast copy for campaign day 1-7
"""
import os, csv, io, sqlite3, secrets, string, re
from datetime import datetime, date
from urllib.parse import quote
from flask import Flask, request, jsonify, render_template, Response, g

app = Flask(__name__)
try:
    from flask_cors import CORS
    CORS(app)
except ImportError:
    pass

DB_PATH   = os.environ.get("DB_PATH", "tracker.db")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "nxtwave-admin")
BASE_URL  = os.environ.get("BASE_URL", "").rstrip("/")
TARGET    = int(os.environ.get("TARGET_SEATS", "500"))
WORKSHOP  = os.environ.get("WORKSHOP_TITLE", "Build Your First AI Project in 60 Minutes")
WORKSHOP_DATE = os.environ.get("WORKSHOP_DATE", "Sunday, 7 PM IST")

CHANNELS = {"wa": "WhatsApp group", "ref": "Referral", "li": "LinkedIn",
            "club": "College club", "email": "Placement cell email", "qr": "QR poster", "direct": "Direct"}

# ---------- db ----------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d: d.close()

def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS registrations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            college TEXT NOT NULL,
            branch TEXT,
            whatsapp TEXT UNIQUE NOT NULL,
            email TEXT,
            referrer_code TEXT,
            source TEXT DEFAULT 'direct',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ref ON registrations(referrer_code);
        CREATE INDEX IF NOT EXISTS idx_src ON registrations(source);
        """)
init_db()

# ---------- helpers ----------
def make_code(name):
    prefix = re.sub(r"[^A-Z]", "", name.upper())[:4] or "NXT"
    for _ in range(20):
        code = prefix + "".join(secrets.choice(string.digits) for _ in range(3))
        if not db().execute("SELECT 1 FROM registrations WHERE code=?", (code,)).fetchone():
            return code
    return prefix + secrets.token_hex(3).upper()

def norm_phone(p):
    digits = re.sub(r"\D", "", p or "")
    if len(digits) == 10: digits = "91" + digits
    return digits if 11 <= len(digits) <= 13 else None

def share_url(code):
    base = BASE_URL or request.url_root.rstrip("/")
    return f"{base}/?ref={code}"

def wa_share_text(name, code):
    link = share_url(code)
    return (f"Hey! I just registered for NxtWave's FREE workshop \u2014 *{WORKSHOP}* ({WORKSHOP_DATE}).\n"
            f"You walk out with a working AI project on GitHub for your resume \U0001F680\n"
            f"Only 500 seats. Register with my link: {link}")

def is_admin():
    return request.args.get("key") == ADMIN_KEY or request.headers.get("X-Admin-Key") == ADMIN_KEY

# ---------- pages ----------
@app.route("/")
def index():
    return render_template("index.html", workshop=WORKSHOP, when=WORKSHOP_DATE, target=TARGET)

@app.route("/dashboard")
def dashboard():
    if not is_admin():
        return "Add ?key=ADMIN_KEY", 401
    return render_template("dashboard.html", target=TARGET, key=request.args.get("key"))

@app.route("/health")
def health():
    return jsonify(status="online")

# ---------- public api ----------
@app.route("/api/register", methods=["POST"])
def register():
    d = request.get_json(silent=True) or request.form
    name    = (d.get("name") or "").strip()
    college = (d.get("college") or "").strip()
    branch  = (d.get("branch") or "").strip()
    email   = (d.get("email") or "").strip().lower()
    phone   = norm_phone(d.get("whatsapp"))
    ref     = (d.get("ref") or request.args.get("ref") or "").strip().upper() or None
    src     = (d.get("src") or request.args.get("src") or ("ref" if ref else "direct")).strip().lower()
    if src not in CHANNELS: src = "direct"

    if len(name) < 2:        return jsonify(error="Enter your full name"), 400
    if len(college) < 3:     return jsonify(error="Enter your college name"), 400
    if not phone:            return jsonify(error="Enter a valid 10-digit WhatsApp number"), 400

    c = db()
    if c.execute("SELECT 1 FROM registrations WHERE whatsapp=?", (phone,)).fetchone():
        return jsonify(error="This WhatsApp number is already registered"), 409
    if ref and not c.execute("SELECT 1 FROM registrations WHERE code=?", (ref,)).fetchone():
        ref = None  # invalid code: still register, just no credit

    code = make_code(name)
    c.execute("""INSERT INTO registrations(code,name,college,branch,whatsapp,email,referrer_code,source,created_at)
                 VALUES(?,?,?,?,?,?,?,?,?)""",
              (code, name, college, branch, phone, email, ref, src, datetime.utcnow().isoformat()))
    c.commit()
    text = wa_share_text(name, code)
    return jsonify(code=code, name=name, share_url=share_url(code),
                   whatsapp_share="https://wa.me/?text=" + quote(text), share_text=text), 201

@app.route("/api/stats")
def stats():
    c = db()
    total = c.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
    refs  = c.execute("SELECT COUNT(*) FROM registrations WHERE referrer_code IS NOT NULL").fetchone()[0]
    return jsonify(total_registrations=total, total_referrals=refs,
                   remaining_capacity=max(0, TARGET - total), target=TARGET)

@app.route("/api/referrer/<code>")
def referrer(code):
    r = db().execute("SELECT name, college, code FROM registrations WHERE code=?", (code.upper(),)).fetchone()
    if not r: return jsonify(error="Referrer not found"), 404
    n = db().execute("SELECT COUNT(*) FROM registrations WHERE referrer_code=?", (r["code"],)).fetchone()[0]
    return jsonify(name=r["name"], college=r["college"], referral_count=n)

@app.route("/api/leaderboard")
def leaderboard():
    """Who referred how many. Public, top N (default 10)."""
    limit = min(int(request.args.get("limit", 10)), 100)
    rows = db().execute("""
        SELECT r.name, r.college, r.code, COUNT(x.id) AS referrals
        FROM registrations r JOIN registrations x ON x.referrer_code = r.code
        GROUP BY r.code ORDER BY referrals DESC, r.created_at ASC LIMIT ?""", (limit,)).fetchall()
    return jsonify(leaderboard=[dict(rank=i+1, name=r["name"], college=r["college"], code=r["code"],
                                     referrals=r["referrals"]) for i, r in enumerate(rows)])

@app.route("/api/share/<code>")
def share(code):
    r = db().execute("SELECT name FROM registrations WHERE code=?", (code.upper(),)).fetchone()
    if not r: return jsonify(error="Unknown code"), 404
    text = wa_share_text(r["name"], code.upper())
    return jsonify(share_url=share_url(code.upper()), whatsapp_share="https://wa.me/?text=" + quote(text), share_text=text)

# ---------- admin api ----------
@app.route("/api/admin/funnel")
def funnel():
    if not is_admin(): return jsonify(error="unauthorized"), 401
    c = db()
    total = c.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
    by_src = {CHANNELS.get(r[0], r[0]): r[1] for r in
              c.execute("SELECT source, COUNT(*) FROM registrations GROUP BY source ORDER BY 2 DESC")}
    by_college = [dict(college=r[0], count=r[1]) for r in
                  c.execute("SELECT college, COUNT(*) FROM registrations GROUP BY college ORDER BY 2 DESC LIMIT 15")]
    by_day = [dict(day=r[0], count=r[1]) for r in
              c.execute("SELECT substr(created_at,1,10), COUNT(*) FROM registrations GROUP BY 1 ORDER BY 1")]
    sharers = c.execute("SELECT COUNT(DISTINCT referrer_code) FROM registrations WHERE referrer_code IS NOT NULL").fetchone()[0]
    referred = c.execute("SELECT COUNT(*) FROM registrations WHERE referrer_code IS NOT NULL").fetchone()[0]
    k_factor = round(referred / total, 2) if total else 0
    return jsonify(total=total, target=TARGET, progress_pct=round(100 * total / TARGET, 1),
                   by_channel=by_src, by_college=by_college, by_day=by_day,
                   referred=referred, active_referrers=sharers, k_factor=k_factor)

@app.route("/api/admin/export.csv")
def export_csv():
    if not is_admin(): return jsonify(error="unauthorized"), 401
    rows = db().execute("SELECT * FROM registrations ORDER BY id").fetchall()
    buf = io.StringIO(); w = csv.writer(buf)
    if rows: w.writerow(rows[0].keys())
    for r in rows: w.writerow(list(r))
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=registrations.csv"})

# ---------- whatsapp broadcast copy (campaign day 1-7) ----------
MESSAGES = {
 1: ("Seed: CR / coordinator post",
     "Hi all \U0001F44B Final-year folks \u2014 NxtWave is running a FREE 60-min live workshop: *{w}* ({d}).\n"
     "You build a real AI project live and leave with a GitHub repo + certificate for your resume.\n"
     "Only 500 seats across colleges. Register (30 sec): {link}"),
 2: ("Social proof",
     "Update: {n} students from {colleges} colleges already in \U0001F525 If you haven't registered for *{w}*, seats are filling: {link}"),
 3: ("Referral launch",
     "Registered already? Share your personal link \U0001F517 Every friend who joins through it counts as your referral. Top 10 referrers get Amazon vouchers + a shout-out in the live session. Your link is on the page after registering: {link}"),
 4: ("Value reminder",
     "Interviewer: \u201cAny AI project you've built?\u201d \U0001F62C Don't let that be awkward. 60 minutes on {d} fixes it. {link}"),
 5: ("Referral push",
     "{referred} students have already joined through a friend's link. 48 hours left \u2014 bring 3 friends and you're in the top 10 \U0001F680 {link}"),
 6: ("Scarcity",
     "Only {left} seats left for *{w}*. Final-years only. Register now: {link}"),
 7: ("Day-of reminder",
     "Today \u2b50 *{w}* starts at {d}. Keep a laptop + GitHub login ready. Join link lands here 30 min before. Not registered? Last chance: {link}"),
}
@app.route("/api/messages/<int:day>")
def messages(day):
    if day not in MESSAGES: return jsonify(error="day must be 1-7"), 400
    c = db()
    n = c.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
    colleges = c.execute("SELECT COUNT(DISTINCT college) FROM registrations").fetchone()[0]
    referred = c.execute("SELECT COUNT(*) FROM registrations WHERE referrer_code IS NOT NULL").fetchone()[0]
    title, body = MESSAGES[day]
    base = BASE_URL or request.url_root.rstrip("/")
    text = body.format(w=WORKSHOP, d=WORKSHOP_DATE, link=f"{base}/?src=wa", n=n, colleges=colleges,
                       referred=referred, left=max(0, TARGET - n))
    return jsonify(day=day, purpose=title, text=text)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("DEBUG") == "1")
