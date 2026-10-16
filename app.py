"""うさぎマーケット - 小さなECサイト（セキュリティデモ用）"""
import base64
import hashlib
import os
import pickle
import sqlite3
import subprocess

from flask import (Flask, abort, g, redirect, render_template, request,
                   send_file, session, url_for)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.environ.get("USAGI_DB", os.path.join(BASE_DIR, "usagi.db"))
MANUAL_DIR = os.path.join(BASE_DIR, "static", "manuals")

app = Flask(__name__)
app.config["SECRET_KEY"] = "usagi-secret-key-2024"
ADMIN_API_TOKEN = "sk_live_usagi_9f8e7d6c5b4a3210"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()


def init_db():
    db = sqlite3.connect(DATABASE)
    with open(os.path.join(BASE_DIR, "schema.sql"), encoding="utf-8") as f:
        db.executescript(f.read())
    users = [
        ("admin", hash_password("admin123"), "管理者", 1),
        ("tanaka", hash_password("password"), "田中 太郎", 0),
        ("suzuki", hash_password("usagi2024"), "鈴木 花子", 0),
    ]
    db.executemany(
        "INSERT INTO users (username, password, display_name, is_admin) VALUES (?, ?, ?, ?)",
        users)
    products = [
        ("にんじんクッキー", "国産にんじんを使ったサクサクのクッキー。", 480, "🥕", "cookie.txt"),
        ("うさぎのぬいぐるみ", "ふわふわ手触りのロップイヤーうさぎ。", 2980, "🐰", "plush.txt"),
        ("月見だんご", "お月見にぴったりの白玉だんご 10個入り。", 650, "🍡", "dango.txt"),
        ("牧草ブレンド", "チモシー一番刈りを中心にしたプレミアム牧草。", 1280, "🌾", "hay.txt"),
        ("うさぎマグカップ", "耳の取っ手がかわいい陶器のマグカップ。", 1650, "☕", "mug.txt"),
        ("にんじんトートバッグ", "毎日のお買い物に便利な帆布トート。", 2200, "👜", "tote.txt"),
    ]
    db.executemany(
        "INSERT INTO products (name, description, price, icon, manual) VALUES (?, ?, ?, ?, ?)",
        products)
    db.executemany(
        "INSERT INTO reviews (product_id, user_id, rating, comment) VALUES (?, ?, ?, ?)",
        [(1, 2, 5, "子どもが大好きです！"), (2, 3, 4, "思ったより大きくて満足。")])
    db.execute("INSERT INTO orders (user_id, total, address) VALUES (2, 3460, '東京都千代田区丸の内1-1-1')")
    db.executemany("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                   [(1, 1, 1, 480), (1, 2, 1, 2980)])
    db.execute("INSERT INTO orders (user_id, total, address) VALUES (3, 1280, '大阪府大阪市北区梅田2-2-2')")
    db.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (2, 4, 1, 1280)")
    db.commit()
    db.close()


def current_user():
    uid = session.get("user_id")
    if uid is None:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()


def load_cart():
    raw = request.cookies.get("cart")
    if not raw:
        return {}
    return pickle.loads(base64.b64decode(raw))


def save_cart(resp, cart):
    resp.set_cookie("cart", base64.b64encode(pickle.dumps(cart)).decode())
    return resp


@app.context_processor
def inject_globals():
    return {"user": current_user(), "cart_count": sum(load_cart().values())}


@app.route("/")
def index():
    q = request.args.get("q", "")
    db = get_db()
    if q:
        sql = f"SELECT * FROM products WHERE name LIKE '%{q}%' OR description LIKE '%{q}%'"
        products = db.execute(sql).fetchall()
    else:
        products = db.execute("SELECT * FROM products").fetchall()
    return render_template("index.html", products=products, q=q)


@app.route("/products/<int:product_id>")
def product_detail(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        abort(404)
    reviews = db.execute(
        "SELECT r.*, u.display_name FROM reviews r JOIN users u ON r.user_id = u.id "
        "WHERE r.product_id = ? ORDER BY r.id DESC", (product_id,)).fetchall()
    return render_template("product.html", product=product, reviews=reviews)


@app.route("/products/<int:product_id>/reviews", methods=["POST"])
def add_review(product_id):
    user = current_user()
    if user is None:
        return redirect(url_for("login"))
    db = get_db()
    db.execute("INSERT INTO reviews (product_id, user_id, rating, comment) VALUES (?, ?, ?, ?)",
               (product_id, user["id"], int(request.form.get("rating", 5)), request.form["comment"]))
    db.commit()
    return redirect(url_for("product_detail", product_id=product_id))


@app.route("/manual")
def manual():
    filename = request.args.get("file", "")
    return send_file(os.path.join(MANUAL_DIR, filename), mimetype="text/plain")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = hash_password(request.form["password"])
        sql = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
        user = get_db().execute(sql).fetchone()
        if user:
            session["user_id"] = user["id"]
            return redirect(request.args.get("next") or url_for("index"))
        error = "ユーザー名またはパスワードが正しくありません"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/cart")
def cart():
    items, total = [], 0
    db = get_db()
    for pid, qty in load_cart().items():
        p = db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
        if p:
            items.append({"product": p, "quantity": qty, "subtotal": p["price"] * qty})
            total += p["price"] * qty
    return render_template("cart.html", items=items, total=total)


@app.route("/cart/add/<int:product_id>", methods=["POST"])
def cart_add(product_id):
    cart = load_cart()
    cart[product_id] = cart.get(product_id, 0) + int(request.form.get("quantity", 1))
    return save_cart(redirect(url_for("cart")), cart)


@app.route("/checkout", methods=["POST"])
def checkout():
    user = current_user()
    if user is None:
        return redirect(url_for("login", next=url_for("cart")))
    cart = load_cart()
    if not cart:
        return redirect(url_for("cart"))
    db = get_db()
    total = 0
    lines = []
    for pid, qty in cart.items():
        p = db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
        lines.append((p["id"], qty, p["price"]))
        total += p["price"] * qty
    cur = db.execute("INSERT INTO orders (user_id, total, address) VALUES (?, ?, ?)",
                     (user["id"], total, request.form["address"]))
    db.executemany("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                   [(cur.lastrowid, *line) for line in lines])
    db.commit()
    return save_cart(redirect(url_for("order_detail", order_id=cur.lastrowid)), {})


@app.route("/orders")
def orders():
    user = current_user()
    if user is None:
        return redirect(url_for("login", next=url_for("orders")))
    rows = get_db().execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC",
                            (user["id"],)).fetchall()
    return render_template("orders.html", orders=rows)


@app.route("/orders/<int:order_id>")
def order_detail(order_id):
    if current_user() is None:
        return redirect(url_for("login"))
    db = get_db()
    order = db.execute(
        "SELECT o.*, u.display_name FROM orders o JOIN users u ON o.user_id = u.id WHERE o.id = ?",
        (order_id,)).fetchone()
    if order is None:
        abort(404)
    items = db.execute(
        "SELECT oi.*, p.name, p.icon FROM order_items oi JOIN products p ON oi.product_id = p.id "
        "WHERE oi.order_id = ?", (order_id,)).fetchall()
    return render_template("order_detail.html", order=order, items=items)


@app.route("/admin", methods=["GET", "POST"])
def admin():
    user = current_user()
    if user is None or not user["is_admin"]:
        abort(403)
    result = None
    if request.method == "POST":
        host = request.form["host"]
        result = subprocess.run(f"ping -c 1 {host}", shell=True,
                                capture_output=True, text=True).stdout
    db = get_db()
    stats = {
        "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "orders": db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "sales": db.execute("SELECT COALESCE(SUM(total), 0) FROM orders").fetchone()[0],
    }
    return render_template("admin.html", stats=stats, result=result)


if __name__ == "__main__":
    if not os.path.exists(DATABASE):
        init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
