from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import os

# logic code - functions
app = Flask(__name__)
app.secret_key = "my_key"

# create files and make sure they exist
user_file = "users.csv"
product_file = "products.csv"
carts_file = "carts.csv"
orders_file = "orders.csv"
product_history_file = "product_history.csv"
favorites_file = "favorites.csv"

def ensure_files_exist():
    if not os.path.exists(user_file):
        pd.DataFrame([["admin", "1234", "manager"]],columns=["username","password","role"]).to_csv(user_file, index = False)

    if not os.path.exists(product_file):
        pd.DataFrame(columns=["category","name","weight","price","status", "stock"]).to_csv(product_file, index = False)

    if not os.path.exists(carts_file):
        pd.DataFrame(columns=["username","product_name","quantity"]).to_csv(carts_file, index = False)

    if not os.path.exists(orders_file):
        pd.DataFrame(columns=["username", "product_name", "weight", "total"]).to_csv(orders_file, index = False)

    if not os.path.exists(product_history_file):
        pd.DataFrame(columns=["name"]).to_csv(product_history_file, index=False)

    if not os.path.exists(favorites_file):
        pd.DataFrame(columns=["username", "product_name"]).to_csv(favorites_file, index=False)

ensure_files_exist()

def require_login():
    return "username" in session

def require_manager():
    return require_login() and session.get("role") == "manager"

def require_customer():
    return require_login() and session.get("role") == "customer"

def load_users():
    return pd.read_csv(user_file, dtype = str)

def save_users(df):
    df.to_csv(user_file, index=False)

def add_user(df_users, username, password):
    username = username.strip()
    password = password.strip()

    matches = df_users.loc[df_users["username"] == username]
    if not matches.empty:
        print("Account with this username already exists.")
        return df_users, False

    new_row = pd.DataFrame([{
        "username": username,
        "password": password,
        "role": "customer"
    }])

    df_users = pd.concat([df_users, new_row], ignore_index=True)
    return df_users, True

def validate_login(username, password):
    username = username.strip().lower()
    password = password.strip()

    users_df = load_users()
    users_df["username"] = users_df["username"].str.strip().str.lower()
    users_df["role"] = users_df["role"].str.strip().str.lower()

    matches = users_df.loc[
        (users_df["username"] == username) &
        (users_df["password"] == password)
    ]

    if not matches.empty:
        return matches.iloc[0]["role"]
    return None
    


def load_products():
    return pd.read_csv(product_file, dtype={"category": str, "name": str, "weight": str, "price": float, "status": str, "stock": int})

def get_product_by_name(product_name):
    products_df = load_products()

    matches = products_df.loc[products_df["name"] == product_name]

    if matches.empty:
        return None

    return matches.iloc[0].to_dict()

def save_all_products(df_products):
    df_products.to_csv(product_file, index=False)

def load_carts():
    df = pd.read_csv(carts_file, dtype={"username": str, "product_name": str, "quantity": int})
    df["username"] = df["username"].str.strip().str.lower()
    df["product_name"] = df["product_name"].str.strip()
    return df

def load_favorites():
    df = pd.read_csv(favorites_file, dtype={"username": str, "product_name": str})
    df["username"] = df["username"].str.strip().str.lower()
    df["product_name"] = df["product_name"].str.strip()
    return df

def add_to_cart(username, product_name, quantity):
    quantity = int(quantity)
    username = username.strip().lower()
    product_name = product_name.strip()

    products_df = load_products()
    product = products_df.loc[products_df["name"] == product_name]

    if product.empty:
        return False, "Product not found."

    product_row = product.iloc[0]
    stock = int(product_row["stock"])
    status = str(product_row["status"])

    if status.lower() == "out of stock" or stock <= 0:
        return False, "This product is out of stock."

    carts_df = load_carts()

    existing = carts_df.loc[
        (carts_df["username"] == username) &
        (carts_df["product_name"] == product_name)]

    current_quantity = 0
    if not existing.empty:
        current_quantity = int(existing.iloc[0]["quantity"])

    if current_quantity + quantity > stock:
        return False, "You cannot add more than the available stock."

    if existing.empty:
        new_row = pd.DataFrame([{
            "username": username,
            "product_name": product_name,
            "quantity": quantity }])
        carts_df = pd.concat([carts_df, new_row], ignore_index=True)
    else:
        idx = existing.index[0]
        carts_df.loc[idx, "quantity"] = current_quantity + quantity

    carts_df.to_csv(carts_file, index=False)
    return True, "Added to cart."

def get_cart(username):
    username = username.strip()
    cart_df = load_carts()

    user_cart = cart_df.loc[cart_df["username"] == username]

    if user_cart.empty:
        return [], 0.0
    
    products_df = load_products()

    merged = user_cart.merge(
        products_df,
        left_on="product_name",
        right_on="name",
        how="left"
    )

    merged = merged.dropna(subset=["price"])

    merged["quantity"] = merged["quantity"].astype(int)
    merged["price"] = merged["price"].astype(float)

    merged["line_total"] = merged["quantity"] * merged["price"]
    total = float(merged["line_total"].sum())

    cart_items = merged[["product_name", "weight", "quantity", "price", "line_total", "status"]].to_dict("records")
    return cart_items, total


def remove_from_cart(username, product_name):
    username = username.strip()
    product_name = product_name.strip()
    cart_df = load_carts()

    matches = cart_df.loc[
        (cart_df["username"] == username) &
        (cart_df["product_name"] == product_name)
    ]
    if matches.empty:
        return False, "Product not found in cart."
    
    idx = matches.index[0]

    if cart_df.loc[idx, "quantity"] > 1:
        cart_df.loc[idx, "quantity"] -= 1
    else:
        cart_df = cart_df.drop(idx)

    cart_df.to_csv(carts_file, index=False)

    return True, "Product removed from cart."

def clear_cart(username):
    username = username.strip()
    cart_df = load_carts()
    cart_df = cart_df.loc[cart_df["username"] != username]

    cart_df.to_csv(carts_file, index=False)

def load_product_history():
    return pd.read_csv(product_history_file)

def save_product_history(df):
    df.to_csv(product_history_file, index=False)

def add_to_product_history(name):
    name = name.strip()
    df = load_product_history()

    # avoid duplicates
    if df.loc[df["name"] == name].empty:
        df = pd.concat([df, pd.DataFrame([{"name": name}])], ignore_index=True)
        save_product_history(df)

def checkout(username):
    username = username.strip()
    cart_items, total = get_cart(username)
    if len(cart_items) == 0:
        return False, "Check out not possible. Your cart is empty."
    
    products_df = load_products()

    for item in cart_items:
        name = item["product_name"]
        quantity = int(item["quantity"])

        match = products_df.loc[products_df["name"] == name]
        if match.empty:
            return False, f'Order cannot be purchased. "{name}" no longer exists.'

        idx = match.index[0]
        stock = int(products_df.loc[idx, "stock"])
        status = str(products_df.loc[idx, "status"])

        if status.lower() == "out of stock" or stock < quantity:
            return False, f'Order cannot be purchased. Not enough stock for "{name}".'

    for item in cart_items:
        name = item["product_name"]
        quantity = int(item["quantity"])

        idx = products_df.loc[products_df["name"] == name].index[0]
        products_df.loc[idx, "stock"] = int(products_df.loc[idx, "stock"]) - quantity

        if int(products_df.loc[idx, "stock"]) <= 0:
            products_df.loc[idx, "stock"] = 0
            products_df.loc[idx, "status"] = "Out of stock"
        else:
            products_df.loc[idx, "status"] = "Available"

    save_all_products(products_df)

    orders_df = load_orders()
    for item in cart_items:
        new_order = pd.DataFrame([{
            "username": username,
            "product_name": item["product_name"],
            "weight": item["weight"],
            "total": float(item["line_total"])
        }])
        orders_df = pd.concat([orders_df, new_order], ignore_index=True)
    save_orders(orders_df)

    clear_cart(username)

    return True, f"Payment successful. Total: €{total:.2f}"


def save_favorites(df):
    df.to_csv(favorites_file, index=False)

def is_favorite(username, product_name):
    df = load_favorites()
    match = df.loc[
        (df["username"] == username) &
        (df["product_name"] == product_name)
    ]
    return not match.empty

def get_cart_quantity(username, product_name):
    carts_df = load_carts()
    match = carts_df.loc[
        (carts_df["username"] == username) &
        (carts_df["product_name"] == product_name)
    ]
    if match.empty:
        return 0
    return int(match.iloc[0]["quantity"])

def load_orders():
    return pd.read_csv(orders_file)

def save_orders(df):
    df.to_csv(orders_file, index=False)

# html form
# shop page
@app.route("/shop", methods=["GET"])
def shop():
    products_df = load_products()

    fruits_veg = products_df.loc[products_df["category"] == "Fruits & Vegetables"].to_dict("records")
    meat = products_df.loc[products_df["category"] == "Meat"].to_dict("records")

    username = session.get("username")

    if username:
        for p in fruits_veg:
            p["in_cart"] = get_cart_quantity(username, p["name"])
        for p in meat:
            p["in_cart"] = get_cart_quantity(username, p["name"])

    username = session.get("username")
    if username:
        fav_df = load_favorites()
        fav_set = set(fav_df.loc[fav_df["username"] == username, "product_name"].tolist())

        for p in fruits_veg:
            p["is_favorite"] = (p["name"] in fav_set)
        for p in meat:
            p["is_favorite"] = (p["name"] in fav_set)

    return render_template(
        "shop.html",
        fruits_veg=fruits_veg,
        meat=meat,
        logged_in=("username" in session),
        role=session.get("role")
    )

# signup page
@app.route("/signup", methods = ["GET", "POST"])
def signup():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        df_users = load_users()
        df_users, success = add_user(df_users, username, password)

        if not success:
            error = "Account with this username already exists."
        else:
            save_users(df_users)
            return redirect(url_for("login"))

    return render_template(
        "signup.html",
        logged_in = ("username" in session),
        role = session.get("role"),
        error = error)

# login page
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        role = validate_login(username, password)

        if role is None:
            error = "Username or password is incorrect."
        else:
            session["username"] = username.lower()
            session["role"] = role

            if role == "manager":
                return redirect(url_for("manager"))
            else:
                return redirect(url_for("shop"))

    return render_template(
        "login.html",
        logged_in=("username" in session),
        role=session.get("role"),
        error=error
    )

# logout page
@app.route("/logout", methods = ["GET"])
def logout():
    session.clear()       
    return render_template("logout.html")


# cart page
@app.route("/cart", methods=["GET"])
def cart():
    if not require_customer():
        return redirect(url_for("shop"))

    cart_items, total = get_cart(session["username"])
    return render_template(
        "cart.html",
        cart_items=cart_items,
        total=total,
        logged_in=True,
        role=session.get("role"))

# add to cart page
@app.route("/cart/add", methods=["POST"])
def cart_add():
    if not require_login():
        return redirect(url_for("login"))

    product_name = request.form.get("product_name", "").strip()
    quantity = request.form.get("quantity", "1")

    success, message = add_to_cart(session["username"], product_name, quantity)

    return redirect(url_for("shop"))

# remove from cart page
@app.route("/cart/remove", methods=["POST"])
def cart_remove():
    if not require_customer():
        return redirect(url_for("shop"))

    product_name = request.form.get("product_name", "").strip()
    mode = request.form.get("mode", "one")

    cart_df = load_carts()
    username = session["username"]

    matches = cart_df.loc[
        (cart_df["username"] == username) &
        (cart_df["product_name"] == product_name)
    ]

    if matches.empty:
        return redirect(url_for("cart"))

    idx = matches.index[0]

    if mode == "all":
        cart_df = cart_df.drop(idx)
    else:
        if cart_df.loc[idx, "quantity"] > 1:
            cart_df.loc[idx, "quantity"] -= 1
        else:
            cart_df = cart_df.drop(idx)

    cart_df.to_csv(carts_file, index=False)
    return redirect(url_for("cart"))

# checkout page
# checkout page
@app.route("/checkout", methods=["POST"])
def do_checkout():
    if not require_customer():
        return redirect(url_for("shop"))

    username = session["username"]

    cart_items, total = get_cart(username)
    if not cart_items:
        return redirect(url_for("cart"))

    success, message = checkout(username)  # logic function
    if not success:
        return redirect(url_for("cart"))

    session["last_order"] = cart_items
    session["last_total"] = total

    return redirect(url_for("checkout_confirmation"))


@app.route("/checkout/confirmation", methods=["GET"])
def checkout_confirmation():
    if "last_order" not in session:
        return redirect(url_for("shop"))

    order = session.pop("last_order")
    total = session.pop("last_total")

    return render_template(
        "checkout_confirmation.html",
        order=order,
        total=total,
        logged_in=("username" in session),
        role=session.get("role")
    )

@app.route("/manager", methods=["GET"])
def manager():
    if not require_manager():
        return redirect(url_for("login"))

    products = load_products().to_dict("records")
    return render_template(
        "manager.html",
        products=products,
        logged_in=("username" in session),
        role=session.get("role")
    )


@app.route("/manager/add", methods=["POST"])
def manager_add():
    if not require_manager():
        return redirect(url_for("login"))

    category = request.form.get("category", "").strip()
    name = request.form.get("name", "").strip()
    add_to_product_history(name)
    weight = request.form.get("weight", "").strip()
    price = float(request.form.get("price", "0"))
    stock = int(request.form.get("stock", "0"))

    status = "Available" if stock > 0 else "Out of stock"

    df = load_products()

    if not df.loc[df["name"] == name].empty:
        return redirect(url_for("manager"))

    new_row = pd.DataFrame([{
        "category": category,
        "name": name,
        "weight": weight,
        "price": price,
        "status": status,
        "stock": stock
    }])

    df = pd.concat([df, new_row], ignore_index=True)
    save_all_products(df)

    return redirect(url_for("manager"))


@app.route("/manager/delete", methods=["POST"])
def manager_delete():
    if not require_manager():
        return redirect(url_for("login"))

    name = request.form.get("name", "").strip()

    df = load_products()
    df = df.loc[df["name"] != name]
    save_all_products(df)

    # Optional but good: remove deleted product from all carts
    carts_df = load_carts()
    carts_df = carts_df.loc[carts_df["product_name"] != name]
    carts_df.to_csv(carts_file, index=False)

    return redirect(url_for("manager"))


@app.route("/manager/update_price", methods=["POST"])
def manager_update_price():
    if not require_manager():
        return redirect(url_for("login"))

    name = request.form.get("name", "").strip()
    new_price = float(request.form.get("price", "0"))

    df = load_products()
    match = df.loc[df["name"] == name]
    if not match.empty:
        idx = match.index[0]
        df.loc[idx, "price"] = new_price
        save_all_products(df)

    return redirect(url_for("manager"))


@app.route("/manager/update_stock", methods=["POST"])
def manager_update_stock():
    if not require_manager():
        return redirect(url_for("login"))

    name = request.form.get("name", "").strip()
    new_stock = int(request.form.get("stock", "0"))

    df = load_products()
    match = df.loc[df["name"] == name]
    if not match.empty:
        idx = match.index[0]
        df.loc[idx, "stock"] = new_stock
        df.loc[idx, "status"] = "Available" if new_stock > 0 else "Out of stock"
        save_all_products(df)

    return redirect(url_for("manager"))


@app.route("/manager/add_stock", methods=["POST"])
def manager_add_stock():
    if not require_manager():
        return redirect(url_for("login"))

    name = request.form.get("name")

    df = load_products()
    match = df.loc[df["name"] == name]

    if not match.empty:
        idx = match.index[0]
        df.loc[idx, "stock"] = int(df.loc[idx, "stock"]) + 1
        df.loc[idx, "status"] = "Available"

        save_all_products(df)

    return redirect(url_for("manager"))

@app.route("/", methods=["GET"])
def home():
    return render_template(
        "homepage.html",
        logged_in=("username" in session),
        role=session.get("role"))



@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        df_users = load_users()
        df_users, success = add_user(df_users, username, password)

        if not success:
            error = "That username is already taken."
        else:
            save_users(df_users)
            return redirect(url_for("login"))

    return render_template(
        "register.html",
        logged_in=("username" in session),
        role=session.get("role"),
        error=error)

@app.route("/favorites", methods=["GET"])
def favorites():
    if not require_customer():
        return redirect(url_for("shop"))

    username = session["username"]

    fav_df = load_favorites()
    user_favs = fav_df.loc[fav_df["username"] == username]

    if user_favs.empty:
        favorite_items = []
    else:
        products_df = load_products()
        merged = user_favs.merge(products_df, left_on="product_name", right_on="name", how="left")
        merged = merged.dropna(subset=["price"])
        favorite_items = merged[["name", "weight", "price", "status", "stock", "category"]].to_dict("records")

    return render_template(
        "favorites.html",
        favorites=favorite_items,
        logged_in=True,
        role=session.get("role")
    )


@app.route("/favorites/add", methods=["POST"])
def favorites_add():
    if not require_customer():
        return redirect(url_for("shop"))

    username = session["username"].strip().lower()
    product_name = request.form.get("product_name", "").strip()

    df = load_favorites()

    exists = df.loc[
        (df["username"] == username) &
        (df["product_name"] == product_name)
    ]

    if exists.empty:
        df = pd.concat([df, pd.DataFrame([{"username": username, "product_name": product_name}])], ignore_index=True)
        save_favorites(df)

    return redirect(request.referrer or url_for("shop"))


@app.route("/favorites/remove", methods=["POST"])
def favorites_remove():
    if not require_customer():
        return redirect(url_for("shop"))

    username = session["username"].strip().lower()
    product_name = request.form.get("product_name", "").strip()

    df = load_favorites()
    df = df.loc[~((df["username"] == username) & (df["product_name"] == product_name))]
    save_favorites(df)

    return redirect(request.referrer or url_for("favorites"))


@app.route("/about")
def about():
    return render_template(
        "about.html",
        logged_in=("username" in session),
        role=session.get("role"))



if __name__ == "__main__":
    app.run(debug=True)

