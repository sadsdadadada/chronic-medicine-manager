from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = "change-this-secret-key-before-real-use"
DB_PATH = os.path.join(os.path.dirname(__file__), "medicine_manager.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        nickname TEXT DEFAULT '',
        age INTEGER DEFAULT 0,
        diseases TEXT DEFAULT '',
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS medicines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        disease TEXT NOT NULL,
        dose TEXT NOT NULL,
        take_time TEXT NOT NULL,
        relation_to_meal TEXT DEFAULT '',
        stock INTEGER NOT NULL,
        daily_use INTEGER NOT NULL,
        threshold INTEGER NOT NULL,
        visit_date TEXT NOT NULL,
        doctor_note TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS checkins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        medicine_id INTEGER NOT NULL,
        check_date TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(user_id, medicine_id, check_date),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (medicine_id) REFERENCES medicines(id)
    )
    """)

    conn.commit()
    conn.close()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def today_str():
    return date.today().isoformat()


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def days_left(target_date):
    try:
        return (parse_date(target_date) - date.today()).days
    except Exception:
        return 0


def stock_days(med):
    daily_use = med["daily_use"] or 1
    return med["stock"] // daily_use


def get_user():
    if "user_id" not in session:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    conn.close()
    return user


@app.route("/")
@login_required
def index():
    user = get_user()
    conn = get_db()

    meds = conn.execute("""
        SELECT * FROM medicines
        WHERE user_id = ?
        ORDER BY take_time ASC, id ASC
    """, (session["user_id"],)).fetchall()

    check_rows = conn.execute("""
        SELECT medicine_id, status FROM checkins
        WHERE user_id = ? AND check_date = ?
    """, (session["user_id"], today_str())).fetchall()

    today_map = {row["medicine_id"]: row["status"] for row in check_rows}

    medicine_data = []
    for med in meds:
        d = dict(med)
        d["stock_days"] = stock_days(med)
        d["visit_days"] = days_left(med["visit_date"])
        d["today_status"] = today_map.get(med["id"], "pending")
        medicine_data.append(d)

    total = len(medicine_data)
    done = sum(1 for m in medicine_data if m["today_status"] == "done")
    missed = sum(1 for m in medicine_data if m["today_status"] == "missed")
    pending = total - done - missed
    warning_count = sum(1 for m in medicine_data if m["stock_days"] <= m["threshold"])
    nearest_visit = min([m["visit_days"] for m in medicine_data], default=0)
    adherence = round(done / total * 100) if total else 0

    # 最近 7 天记录
    records = []
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        d_str = d.isoformat()
        rows = conn.execute("""
            SELECT status, COUNT(*) AS c FROM checkins
            WHERE user_id = ? AND check_date = ?
            GROUP BY status
        """, (session["user_id"], d_str)).fetchall()
        stat = {r["status"]: r["c"] for r in rows}
        records.append({
            "date": d.strftime("%m-%d"),
            "total": total,
            "done": stat.get("done", 0),
            "missed": stat.get("missed", 0),
            "rate": round(stat.get("done", 0) / total * 100) if total else 0
        })

    conn.close()

    ai_advice = build_ai_advice(medicine_data, pending, warning_count)

    return render_template(
        "index.html",
        user=user,
        medicines=medicine_data,
        total=total,
        done=done,
        pending=pending,
        missed=missed,
        warning_count=warning_count,
        nearest_visit=nearest_visit,
        adherence=adherence,
        records=records,
        ai_advice=ai_advice,
        today=today_str()
    )


def build_ai_advice(medicines, pending, warning_count):
    if not medicines:
        return "你还没有建立用药计划。建议先录入长期服用的慢病药品、库存和复诊日期。"

    pending_names = [m["name"] for m in medicines if m["today_status"] == "pending"]
    risky = [m["name"] for m in medicines if m["stock_days"] <= m["threshold"]]
    near_visit = [m["name"] for m in medicines if m["visit_days"] <= 7]

    parts = []
    if pending_names:
        parts.append("今天还有 {} 个用药任务未完成，建议优先完成：{}。".format(
            len(pending_names), "、".join(pending_names)
        ))
    else:
        parts.append("今天的用药任务已经全部完成，继续保持稳定用药习惯。")

    if risky:
        parts.append("{} 库存偏低，请尽快复购或联系医生续方。".format("、".join(risky)))

    if near_visit:
        parts.append("{} 的复诊日期临近，建议提前准备近期指标记录和用药打卡情况。".format("、".join(near_visit)))

    parts.append("如出现头晕、低血糖、皮疹等异常情况，请及时咨询医生，不要自行增减药量。")
    return "".join(parts)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        nickname = request.form.get("nickname", "").strip()
        age = request.form.get("age", "0").strip()
        diseases = request.form.get("diseases", "").strip()

        if not username or not password:
            flash("账号和密码不能为空。")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("密码至少需要 6 位。")
            return redirect(url_for("register"))

        try:
            age_int = int(age) if age else 0
        except ValueError:
            age_int = 0

        conn = get_db()
        try:
            cur = conn.execute("""
                INSERT INTO users (username, password_hash, nickname, age, diseases, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                username,
                generate_password_hash(password),
                nickname,
                age_int,
                diseases,
                datetime.now().isoformat(timespec="seconds")
            ))
            conn.commit()
            session["user_id"] = cur.lastrowid
            flash("注册成功，欢迎使用慢病用药小管家。")
            return redirect(url_for("index"))
        except sqlite3.IntegrityError:
            flash("这个账号已经被注册，请换一个账号。")
            return redirect(url_for("register"))
        finally:
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if not user or not check_password_hash(user["password_hash"], password):
            flash("账号或密码错误。")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        flash("登录成功。")
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("你已退出登录。")
    return redirect(url_for("login"))


@app.route("/medicine/add", methods=["POST"])
@login_required
def add_medicine():
    name = request.form.get("name", "").strip()
    disease = request.form.get("disease", "").strip()
    dose = request.form.get("dose", "").strip()
    take_time = request.form.get("take_time", "").strip()
    relation_to_meal = request.form.get("relation_to_meal", "").strip()
    stock = request.form.get("stock", "0").strip()
    daily_use = request.form.get("daily_use", "1").strip()
    threshold = request.form.get("threshold", "7").strip()
    visit_date = request.form.get("visit_date", "").strip()
    doctor_note = request.form.get("doctor_note", "").strip()

    if not all([name, disease, dose, take_time, stock, daily_use, threshold, visit_date]):
        flash("请完整填写药品名称、疾病、剂量、时间、库存和复诊日期。")
        return redirect(url_for("index"))

    try:
        stock = int(stock)
        daily_use = int(daily_use)
        threshold = int(threshold)
    except ValueError:
        flash("库存、每日消耗和提醒阈值必须是数字。")
        return redirect(url_for("index"))

    if stock < 0 or daily_use <= 0 or threshold <= 0:
        flash("库存不能为负，每日消耗和提醒阈值必须大于 0。")
        return redirect(url_for("index"))

    conn = get_db()
    conn.execute("""
        INSERT INTO medicines
        (user_id, name, disease, dose, take_time, relation_to_meal, stock, daily_use, threshold, visit_date, doctor_note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session["user_id"], name, disease, dose, take_time, relation_to_meal,
        stock, daily_use, threshold, visit_date, doctor_note,
        datetime.now().isoformat(timespec="seconds")
    ))
    conn.commit()
    conn.close()

    flash("新的用药计划已添加。")
    return redirect(url_for("index"))


@app.route("/medicine/<int:medicine_id>/delete", methods=["POST"])
@login_required
def delete_medicine(medicine_id):
    conn = get_db()
    conn.execute("DELETE FROM checkins WHERE user_id = ? AND medicine_id = ?", (session["user_id"], medicine_id))
    conn.execute("DELETE FROM medicines WHERE user_id = ? AND id = ?", (session["user_id"], medicine_id))
    conn.commit()
    conn.close()
    flash("用药计划已删除。")
    return redirect(url_for("index"))


@app.route("/medicine/<int:medicine_id>/checkin", methods=["POST"])
@login_required
def checkin(medicine_id):
    status = request.form.get("status", "done")
    if status not in ("done", "missed"):
        status = "done"

    conn = get_db()
    med = conn.execute(
        "SELECT * FROM medicines WHERE user_id = ? AND id = ?",
        (session["user_id"], medicine_id)
    ).fetchone()

    if not med:
        conn.close()
        flash("没有找到该药品。")
        return redirect(url_for("index"))

    old = conn.execute("""
        SELECT * FROM checkins
        WHERE user_id = ? AND medicine_id = ? AND check_date = ?
    """, (session["user_id"], medicine_id, today_str())).fetchone()

    conn.execute("""
        INSERT INTO checkins (user_id, medicine_id, check_date, status, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, medicine_id, check_date)
        DO UPDATE SET status = excluded.status, created_at = excluded.created_at
    """, (
        session["user_id"], medicine_id, today_str(), status,
        datetime.now().isoformat(timespec="seconds")
    ))

    # 只有从“未完成/漏服”变为“已服用”时才扣库存，避免重复点击多次扣库存
    if status == "done" and (old is None or old["status"] != "done"):
        new_stock = max(0, med["stock"] - 1)
        conn.execute("""
            UPDATE medicines SET stock = ?
            WHERE user_id = ? AND id = ?
        """, (new_stock, session["user_id"], medicine_id))

    conn.commit()
    conn.close()

    flash("已记录：{}。".format("已服用" if status == "done" else "漏服"))
    return redirect(url_for("index"))


@app.route("/medicine/<int:medicine_id>/refill", methods=["POST"])
@login_required
def refill(medicine_id):
    add_count = request.form.get("add_count", "30")
    try:
        add_count = int(add_count)
    except ValueError:
        add_count = 30

    if add_count <= 0:
        add_count = 30

    new_visit_date = request.form.get("new_visit_date", "").strip()
    if not new_visit_date:
        new_visit_date = (date.today() + timedelta(days=30)).isoformat()

    conn = get_db()
    conn.execute("""
        UPDATE medicines
        SET stock = stock + ?, visit_date = ?
        WHERE user_id = ? AND id = ?
    """, (add_count, new_visit_date, session["user_id"], medicine_id))
    conn.commit()
    conn.close()

    flash("复购/续方已更新，库存已增加。")
    return redirect(url_for("index"))


@app.route("/api/visit_note/<int:medicine_id>")
@login_required
def api_visit_note(medicine_id):
    conn = get_db()
    med = conn.execute(
        "SELECT * FROM medicines WHERE user_id = ? AND id = ?",
        (session["user_id"], medicine_id)
    ).fetchone()
    conn.close()

    if not med:
        return jsonify({"error": "not found"}), 404

    note = (
        "医生您好，我长期服用「{}」，用于管理「{}」。目前预计还剩 {} 天药量，"
        "距离原计划复诊还有 {} 天。近期我会带上服药打卡记录、血压/血糖等指标记录和身体反应情况，"
        "希望医生帮我评估是否需要续方或调整用药。"
    ).format(
        med["name"],
        med["disease"],
        stock_days(med),
        days_left(med["visit_date"])
    )
    return jsonify({"note": note})


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
