
import sqlite3
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, g
)

app = Flask(__name__)
app.secret_key = "music-playlist-secret-key"

DATABASE = "music.db"


# 取得資料庫連線
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


# 每次請求結束後關閉資料庫
@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# 建立資料表與預設資料
def init_db():
    with app.app_context():
        db = get_db()

        db.executescript("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                source TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                FOREIGN KEY (category_id)
                    REFERENCES categories(id)
                    ON DELETE RESTRICT
            );
        """)

        default_categories = [
            "動漫歌曲", "流行歌曲", "遊戲歌曲", "其他"
        ]

        for name in default_categories:
            db.execute(
                "INSERT OR IGNORE INTO categories (name) VALUES (?)",
                (name,)
            )

        # 第一次執行時加入範例歌曲
        song_count = db.execute(
            "SELECT COUNT(*) FROM songs"
        ).fetchone()[0]

        if song_count == 0:
            category = db.execute(
                "SELECT id FROM categories WHERE name = ?",
                ("動漫歌曲",)
            ).fetchone()

            db.execute("""
                INSERT INTO songs
                    (title, artist, source, category_id)
                VALUES (?, ?, ?, ?)
            """, ("紅蓮華", "LiSA", "鬼滅之刃", category["id"]))

        db.commit()



# 首頁：搜尋歌曲與分類篩選
@app.route("/")
def index():
    db = get_db()

    # 取得搜尋條件
    artist_keyword = request.args.get("artist", "").strip()
    source_keyword = request.args.get("source", "").strip()
    selected_category = request.args.get(
        "category_id", type=int
    )

    # 取得所有分類
    categories = db.execute(
        "SELECT * FROM categories ORDER BY name"
    ).fetchall()

    # 建立基本 SQL 查詢
    sql = """
        SELECT songs.*, categories.name AS category_name
        FROM songs
        JOIN categories ON songs.category_id = categories.id
        WHERE 1 = 1
    """

    params = []

    # 依照歌手搜尋
    if artist_keyword:
        sql += " AND songs.artist LIKE ?"
        params.append(f"%{artist_keyword}%")

    # 依照出處搜尋
    if source_keyword:
        sql += " AND songs.source LIKE ?"
        params.append(f"%{source_keyword}%")

    # 依照歌曲分類篩選
    if selected_category is not None:
        sql += " AND songs.category_id = ?"
        params.append(selected_category)

    # 最新新增的歌曲優先顯示
    sql += " ORDER BY songs.id DESC"

    songs = db.execute(sql, params).fetchall()

    print("目前搜尋條件：", artist_keyword, source_keyword, selected_category)
    print("首頁查詢結果：", [dict(song) for song in songs])

    return render_template(
        "index.html",
        songs=songs,
        categories=categories,
        selected_category=selected_category,
        artist_keyword=artist_keyword,
        source_keyword=source_keyword
    )


# 新增歌曲
@app.route("/add", methods=["GET", "POST"])
def add_song():
    db = get_db()

    categories = db.execute(
        "SELECT * FROM categories ORDER BY name"
    ).fetchall()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        artist = request.form.get("artist", "").strip()
        source = request.form.get("source", "").strip()
        category_id = request.form.get(
            "category_id", type=int
        )

        if not title or not artist or not source:
            flash("請填寫所有歌曲欄位。")
        elif not any(c["id"] == category_id for c in categories):
            flash("請選擇有效的歌曲分類。")
        else:
            db.execute("""
                INSERT INTO songs
                    (title, artist, source, category_id)
                VALUES (?, ?, ?, ?)
            """, (title, artist, source, category_id))
            db.commit()

            flash("歌曲新增成功！")
            return redirect(url_for("index"))

    return render_template(
        "song_form.html",
        song=None,
        categories=categories,
        page_title="新增歌曲"
    )


# 修改歌曲
@app.route("/edit/<int:song_id>", methods=["GET", "POST"])
def edit_song(song_id):
    db = get_db()

    song = db.execute(
        "SELECT * FROM songs WHERE id = ?", (song_id,)
    ).fetchone()

    if song is None:
        flash("找不到這首歌曲。")
        return redirect(url_for("index"))

    categories = db.execute(
        "SELECT * FROM categories ORDER BY name"
    ).fetchall()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        artist = request.form.get("artist", "").strip()
        source = request.form.get("source", "").strip()
        category_id = request.form.get(
            "category_id", type=int
        )

        if not title or not artist or not source:
            flash("請填寫所有歌曲欄位。")
        elif not any(c["id"] == category_id for c in categories):
            flash("請選擇有效的歌曲分類。")
        else:
            db.execute("""
                UPDATE songs
                SET title = ?, artist = ?, source = ?,
                    category_id = ?
                WHERE id = ?
            """, (
                title, artist, source, category_id, song_id
            ))
            db.commit()

            flash("歌曲修改成功！")
            return redirect(url_for("index"))

    return render_template(
        "song_form.html",
        song=song,
        categories=categories,
        page_title="修改歌曲"
    )


# 刪除歌曲：只接受 POST 請求
@app.route("/delete/<int:song_id>", methods=["POST"])
def delete_song(song_id):
    db = get_db()

    db.execute(
        "DELETE FROM songs WHERE id = ?", (song_id,)
    )
    db.commit()

    flash("歌曲已刪除。")
    return redirect(url_for("index"))


# 分類管理：新增分類
@app.route("/categories", methods=["GET", "POST"])
def manage_categories():
    db = get_db()

    if request.method == "POST":
        name = request.form.get("name", "").strip()

        if not name:
            flash("分類名稱不能空白。")
        else:
            try:
                db.execute(
                    "INSERT INTO categories (name) VALUES (?)",
                    (name,)
                )
                db.commit()
                flash("分類新增成功！")
                return redirect(url_for("manage_categories"))
            except sqlite3.IntegrityError:
                flash("這個分類已經存在。")

    categories = db.execute("""
        SELECT categories.*,
               COUNT(songs.id) AS song_count
        FROM categories
        LEFT JOIN songs
            ON categories.id = songs.category_id
        GROUP BY categories.id
        ORDER BY categories.name
    """).fetchall()

    return render_template(
        "categories.html", categories=categories
    )


# 刪除分類：分類內仍有歌曲時不允許刪除
@app.route("/categories/delete/<int:category_id>", methods=["POST"])
def delete_category(category_id):
    db = get_db()

    category = db.execute(
        "SELECT * FROM categories WHERE id = ?",
        (category_id,)
    ).fetchone()

    if category is None:
        flash("找不到這個分類。")
    else:
        try:
            db.execute(
                "DELETE FROM categories WHERE id = ?",
                (category_id,)
            )
            db.commit()
            flash("分類已刪除。")
        except sqlite3.IntegrityError:
            flash("此分類還有歌曲，請先移動或刪除歌曲。")

    return redirect(url_for("manage_categories"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
