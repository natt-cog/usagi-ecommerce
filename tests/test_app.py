from conftest import login


def test_top_page_lists_products(client):
    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "にんじんクッキー" in html
    assert "うさぎのぬいぐるみ" in html


def test_search_products(client):
    html = client.get("/?q=だんご").get_data(as_text=True)
    assert "月見だんご" in html
    assert "にんじんクッキー" not in html


def test_product_detail(client):
    res = client.get("/products/2")
    assert res.status_code == 200
    assert "ロップイヤー" in res.get_data(as_text=True)


def test_product_not_found(client):
    assert client.get("/products/999").status_code == 404


def test_manual(client):
    res = client.get("/manual?file=cookie.txt")
    assert res.status_code == 200
    assert "取扱説明書" in res.get_data(as_text=True)


def test_login_success_and_failure(client):
    assert login(client).status_code == 302
    html = client.get("/").get_data(as_text=True)
    assert "田中 太郎 さん" in html

    client.get("/logout")
    res = login(client, password="wrong")
    assert "正しくありません" in res.get_data(as_text=True)


def test_post_review(client):
    login(client)
    client.post("/products/3/reviews", data={"rating": "4", "comment": "もちもちでした"})
    assert "もちもちでした" in client.get("/products/3").get_data(as_text=True)


def test_cart_and_checkout(client):
    login(client)
    client.post("/cart/add/1", data={"quantity": "2"})
    client.post("/cart/add/5", data={"quantity": "1"})
    html = client.get("/cart").get_data(as_text=True)
    assert "¥2,610" in html

    res = client.post("/checkout", data={"address": "神奈川県横浜市1-2-3"})
    assert res.status_code == 302
    html = client.get(res.headers["Location"]).get_data(as_text=True)
    assert "神奈川県横浜市1-2-3" in html
    assert "カート (0)" in html


def test_orders_requires_login(client):
    res = client.get("/orders")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_order_history(client):
    login(client)
    html = client.get("/orders").get_data(as_text=True)
    assert "#1" in html
    assert "¥3,460" in html


def test_admin_forbidden_for_normal_user(client):
    login(client)
    assert client.get("/admin").status_code == 403


def test_admin_dashboard(client):
    login(client, "admin", "admin123")
    html = client.get("/admin").get_data(as_text=True)
    assert "売上合計" in html
    assert "¥4,740" in html
