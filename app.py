from flask import Flask, render_template, request, redirect, session, jsonify, flash, url_for

import json, os, datetime, requests, smtplib
from email.mime.text import MIMEText

import secrets
import random
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_url_path='/static')
app.secret_key = 'shopolia_secret_key'
# ---------- FORGET PASSWORD ----------
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        users = load_json(USERS_FILE)

        for user in users:
            if user['email'] == email:
                token = secrets.token_urlsafe(32)

                user['reset_token'] = token
                user['reset_expire'] = (
                    datetime.datetime.now() + datetime.timedelta(minutes=15)
                ).isoformat()

                save_json(USERS_FILE, users)

                reset_link = request.headers.get("X-Forwarded-Host", request.host)
                reset_link = f"https://{reset_link}" + url_for('reset_password', token=token)


                send_email(
                    email,
                    "إعادة تعيين كلمة المرور - Shopolia",
                    f"اضغط على الرابط لتغيير كلمة المرور:\n\n{reset_link}\n\nالرابط صالح لمدة 15 دقيقة."
                )

                flash("📩 تم إرسال رابط إعادة التعيين إلى بريدك")
                return redirect('/login')

        flash("❌ البريد غير مسجل")

    return render_template('forgot_password.html')
# ---------- RESET PASSWORD ----------
@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    users = load_json(USERS_FILE)

    for user in users:
        if user.get('reset_token') == token:
            expire_time = datetime.datetime.fromisoformat(user['reset_expire'])

            if datetime.datetime.now() > expire_time:
                flash("⏰ انتهت صلاحية الرابط")
                return redirect('/login')

            if request.method == 'POST':
                new_password = request.form['password']
                user['password'] = generate_password_hash(new_password)
                user.pop('reset_token', None)
                user.pop('reset_expire', None)
                save_json(USERS_FILE, users)

                flash("✅ تم تغيير كلمة المرور بنجاح")
                return redirect('/login')

            return render_template('reset_password.html')

    flash("❌ رابط غير صالح")
    return redirect('/login')

# ================= PATHS (FIXED) =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, 'data')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
PRODUCTS_FILE = os.path.join(DATA_DIR, 'products.json')
ORDERS_FILE = os.path.join(DATA_DIR, 'orders.json')
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

# ================= TELEGRAM =================
TELEGRAM_BOT_TOKEN = '8169052200:AAGhOMWV8On5Cs3gdaumxDFT77zEzdGemfA'
TELEGRAM_CHAT_ID = '6893702360'
# OpenRouter AI
OPENROUTER_API_KEY = "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"
AI_MODEL = "openai/gpt-4o-mini"
AI_PROMPT_FILE = "shopolia_ai.txt"
# ================= HELPERS =================
def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def send_email(to_email, subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = 'shopoliastore1@gmail.com'
        msg['To'] = to_email

        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()
            smtp.login('shopoliastore1@gmail.com', 'gxadwtwoaxkqftkw')
            smtp.send_message(msg)

        print("✅ Email sent")
    except Exception as e:
        print(f"❌ Email error: {e}")
# ---------- CHANGE PASSWORD ----------
@app.route('/change_password', methods=['POST'])
def change_password():
    if 'user' not in session:
        return redirect('/login')

    current = request.form['current_password']
    new = request.form['new_password']

    users = load_json(USERS_FILE)

    for user in users:
        if user['email'] == session['email']:
            # check old password
            if check_password_hash(user['password'], current):
                user['password'] = generate_password_hash(new)
                save_json(USERS_FILE, users)
                flash("✅ تم تغيير كلمة المرور بنجاح")
            else:
                flash("❌ كلمة المرور الحالية غير صحيحة")
            break

    return redirect('/account')
# ================= ROUTES =================
@app.route('/')
def home():
    return redirect('/login') if 'user' not in session else redirect('/store')

# ---------- LOGIN WITH 2FA ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        users = load_json(USERS_FILE)

        for user in users:
            if user['email'] == email and check_password_hash(user['password'], password):

                # generate OTP
                otp = str(random.randint(100000, 999999))

                session['2fa_user'] = {
                    "name": user['name'],
                    "email": user['email'],
                    "otp": otp
                }

                send_email(
                    email,
                    "رمز تسجيل الدخول - Shopolia",
                    f"رمز تسجيل الدخول الخاص بك هو:\n\n{otp}\n\nصالح لمدة 5 دقائق."
                )

                return redirect('/verify_2fa')

        flash('❌ البريد الإلكتروني أو كلمة السر غير صحيحة')

    return render_template('login.html')
# ---------- VERIFY 2FA ----------
@app.route('/verify_2fa', methods=['GET', 'POST'])
def verify_2fa():
    if '2fa_user' not in session:
        return redirect('/login')

    if request.method == 'POST':
        code = request.form['code']
        user_data = session['2fa_user']

        if code == user_data['otp']:
            session['user'] = user_data['name']
            session['email'] = user_data['email']
            session['cart'] = []

            session.pop('2fa_user')
            return redirect('/store')
        else:
            flash("❌ الكود غير صحيح")

    return render_template('verify_2fa.html')


# ---------- SIGNUP WITH EMAIL OTP ----------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        users = load_json(USERS_FILE)

        # check if email exists
        for user in users:
            if user['email'] == email:
                flash('❌ البريد الإلكتروني مسجل مسبقاً')
                return render_template('signup.html')

        # generate 6-digit code
        otp = str(random.randint(100000, 999999))

        # save temp data in session
        session['temp_user'] = {
            'name': name,
            'email': email,
            'password': generate_password_hash(password),
            'otp': otp
        }

        # send email
        send_email(
            email,
            "رمز تأكيد الحساب - Shopolia",
            f"رمز تأكيد حسابك هو:\n\n{otp}\n\nصالح لمدة 10 دقائق."
        )

        return redirect('/verify_email')

    return render_template('signup.html')
# ---------- VERIFY EMAIL ----------
@app.route('/verify_email', methods=['GET', 'POST'])
def verify_email():
    if 'temp_user' not in session:
        return redirect('/signup')

    if request.method == 'POST':
        entered_code = request.form['code']
        temp_user = session['temp_user']

        if entered_code == temp_user['otp']:
            users = load_json(USERS_FILE)

            users.append({
                'name': temp_user['name'],
                'email': temp_user['email'],
                'password': temp_user['password'],
                'verified': True
            })

            save_json(USERS_FILE, users)
            session.pop('temp_user')

            flash("✅ تم إنشاء الحساب بنجاح")
            return redirect('/login')
        else:
            flash("❌ الكود غير صحيح")

    return render_template('verify_email.html')

# ---------- STORE ----------
@app.route('/store')
def store():
    if 'user' not in session:
        return redirect('/login')

    products = load_json(PRODUCTS_FILE)
    config = load_json(CONFIG_FILE)
    return render_template(
        'store.html',
        products=products,
        user=session['user'],
        config_admin_email=config.get('admin_email')
    )

# ---------- CART ----------
@app.route('/add_to_cart/<product_name>', methods=['POST'])
def add_to_cart(product_name):
    if 'user' not in session:
        return redirect('/login')

    products = load_json(PRODUCTS_FILE)
    product = next((p for p in products if p['name'] == product_name), None)
    if not product:
        return "Product not found", 404

    cart = session.get('cart', [])
    for item in cart:
        if item['name'] == product_name:
            item['quantity'] += 1
            break
    else:
        cart.append({
            'name': product_name,
            'price': int(product['price']),
            'quantity': 1
        })

    session['cart'] = cart
    return redirect('/store')

@app.route('/cart')
def view_cart():
    if 'user' not in session:
        return redirect('/login')

    cart = session.get('cart', [])
    total = sum(item['price'] * item['quantity'] for item in cart)
    return render_template('cart.html', cart=cart, total=total, user=session['user'])

# ---------- CHECKOUT ----------
@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user' not in session:
        return redirect('/login')

    phone = request.form['phone']
    email = request.form['email']
    message = request.form['message']

    cart = session.get('cart', [])
    total = sum(item['price'] * item['quantity'] for item in cart)

    order = {
        "user": session['user'],
        "email": email,
        "phone": phone,
        "message": message,
        "cart": cart,
        "total": total,
        "status": "pending",
        "date": datetime.datetime.now().isoformat()
    }

    orders = load_json(ORDERS_FILE)
    orders.append(order)
    save_json(ORDERS_FILE, orders)

    order_text = f"🛒 طلب جديد من {session['user']}\n📧 {email}\n📱 {phone}\n📝 {message}\n"
    for item in cart:
        order_text += f"- {item['name']} x{item['quantity']} = {item['price'] * item['quantity']} MAD\n"
    order_text += f"\n💰 المجموع: {total} MAD"

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={'chat_id': TELEGRAM_CHAT_ID, 'text': order_text}
    )

    session['cart'] = []
    flash("✅ تم إرسال الطلب بنجاح")
    return redirect('/store')

# ---------- ADMIN ----------
@app.route('/admin/add_json', methods=['POST'])
def add_products_from_json():
    config = load_json(CONFIG_FILE)
    if session.get('email') != config.get('admin_email'):
        return "Unauthorized"

    json_text = request.form['json_data']

    try:
        new_products = json.loads(json_text)
        if not isinstance(new_products, list):
            return "JSON must be a list"

        products = load_json(PRODUCTS_FILE)

        for product in new_products:
            products.append({
                "name": product["name"],
                "price": product["price"],
                "stock": product["stock"],
                "image": product["image"]
            })

        save_json(PRODUCTS_FILE, products)
        return redirect('/admin')

    except Exception as e:
        return f"JSON Error: {e}"

@app.route('/admin')
def admin_panel():
    if 'user' not in session:
        return redirect('/login')

    config = load_json(CONFIG_FILE)
    if session['email'] != config.get('admin_email'):
        return 'Unauthorized'

    products = load_json(PRODUCTS_FILE)
    orders = load_json(ORDERS_FILE)
    users = load_json(USERS_FILE)

    stats = {
        "products": len(products),
        "orders": len(orders),
        "users": len(users)
    }

    return render_template('admin.html', products=products, orders=orders, stats=stats , support=support)

@app.route('/admin/add', methods=['POST'])
def add_product():
    products = load_json(PRODUCTS_FILE)
    products.append({
        "name": request.form['name'],
        "price": request.form['price'],
        "stock": request.form['stock'],
        "image": request.form['image']
    })
    save_json(PRODUCTS_FILE, products)
    return redirect('/admin')

@app.route('/admin/delete', methods=['POST'])
def delete_product():
    name = request.form['name']
    products = [p for p in load_json(PRODUCTS_FILE) if p['name'] != name]
    save_json(PRODUCTS_FILE, products)
    return redirect('/admin')

@app.route('/admin/edit', methods=['POST'])
def edit_product():
    original_name = request.form['original_name']
    products = load_json(PRODUCTS_FILE)

    for product in products:
        if product['name'] == original_name:
            product['name'] = request.form['name']
            product['price'] = request.form['price']
            product['stock'] = request.form['stock']
            product['image'] = request.form['image']
            break

    save_json(PRODUCTS_FILE, products)
    return redirect('/admin')

@app.route('/admin/order_action', methods=['POST'])
def handle_order_action():
    orders = load_json(ORDERS_FILE)
    order_index = int(request.form['order_index'])
    action = request.form['action']
    order = orders[order_index]

    if action == 'accept':
        order['status'] = 'accepted'
        message = f"""✅ تم قبول طلبك بنجاح
المجموع: {order['total']} MAD
شكراً لتسوقك معنا في Shopolia"""
    elif action == 'reject':
        order['status'] = 'rejected'
        message = "❌ تم رفض طلبك."
    elif action == 'delete':
        orders.pop(order_index)
        save_json(ORDERS_FILE, orders)
        return redirect('/admin')
    else:
        return "Invalid action"

    save_json(ORDERS_FILE, orders)
    send_email(order['email'], "تحديث حالة الطلب", message)
    return redirect('/admin')

# ---------- LOGOUT ----------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')
@app.route('/support', methods=['GET', 'POST'])
def support():
    if 'user' not in session:
        return redirect('/login')

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        issue_type = request.form['type']
        message = request.form['message']

        ticket = {
            "user": session['user'],
            "name": name,
            "email": email,
            "type": issue_type,
            "message": message,
            "date": datetime.datetime.now().isoformat(),
            "status": "open"
        }

        SUPPORT_FILE = os.path.join(DATA_DIR, 'support.json')
        tickets = load_json(SUPPORT_FILE)
        tickets.append(ticket)
        save_json(SUPPORT_FILE, tickets)

        flash("✅ تم إرسال طلب الدعم بنجاح")
        return redirect('/store')

    return render_template('support.html')

    # Telegram message
    text = f"""🧑‍💻 SUPPORT REQUEST – SHOPOLIA

👤 User: {session['user']}
📛 Name: {name}
📧 Email: {email}
📌 Type: {issue_type}

📝 Message:
{message}
"""

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text
        }
    )

    flash("✅ تم إرسال طلب الدعم بنجاح، غادي نتواصلو معاك قريباً")
    return redirect('/store')
#
support = load_json(os.path.join(DATA_DIR, 'support.json'))
# ---------- ACCOUNT ----------
@app.route('/account')
def account():
    if 'user' not in session:
        return redirect('/login')

    return render_template(
        'account.html',
        name=session['user'],
        email=session['email']
    )
@app.route('/apply_manager', methods=['POST'])
def apply_manager():
    if 'user' not in session:
        return redirect('/login')

    requests_list = load_json("data/manager_requests.json")

    requests_list.append({
        "name": session['user'],
        "email": session['email'],
        "status": "pending",
        "date": datetime.datetime.now().isoformat()
    })

    save_json("data/manager_requests.json", requests_list)
    flash("تم إرسال طلبك للإدارة")
    return redirect('/store')

# ---------- APPROVE MANAGER ----------
@app.route('/admin/approve_manager', methods=['POST'])
def approve_manager():
    email = request.form['email']

    users = load_json(USERS_FILE)
    for u in users:
        if u['email'] == email:
            u['role'] = 'manager'
            u['balance'] = 0

    save_json(USERS_FILE, users)

    reqs = load_json("data/manager_requests.json")
    reqs = [r for r in reqs if r['email'] != email]
    save_json("data/manager_requests.json", reqs)

    return redirect('/admin')

# ---------- DELETE SELECTED PRODUCTS ----------
@app.route('/admin/delete_selected', methods=['POST'])
def delete_selected_products():
    selected = request.form.getlist('selected_products')
    products = load_json(PRODUCTS_FILE)
    products = [p for p in products if p['name'] not in selected]
    save_json(PRODUCTS_FILE, products)
    return redirect('/admin')
# ================= AI CHAT =================
@app.route('/ai', methods=['POST'])
def ai_chat():
    if 'user' not in session:
        return {"reply": "المرجو تسجيل الدخول أولاً."}

    user_message = request.json.get('message', '')

    # قراءة prompt
    try:
        with open(AI_PROMPT_FILE, "r", encoding="utf-8") as f:
            system_prompt = f.read()
    except:
        system_prompt = "أنت مساعد لموقع Shopolia."

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": AI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        }
    )

    try:
        data = response.json()
        reply = data["choices"][0]["message"]["content"]
    except:
        reply = "⚠️ وقع مشكل فـ AI."

    return {"reply": reply}

# ================= RUN =================
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)