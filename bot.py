import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from flask import Flask, request
import os
import requests
import sqlite3
import uuid
from datetime import datetime

# توکن ربات، آیدی ادمین، و آدرس کیف پول TON
TOKEN = '8013359738:AAH8kXfUQvBCETE58KeNHlYK346GViQBG2s'
ADMIN_ID = 6875171696
ETEESAL_TON_ADDRESS = 'UQDtTqi7Y1RpfOCAnhSVLuB23KmmO7YoShIBoJAUkpyAntag'

# تنظیمات سرور Flask برای Webhook
app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# URL Webhook (پس از استقرار در Render جایگزین کنید)
WEBHOOK_URL = 'https://your-service.onrender.com/bot'

# دیکشنری برای ذخیره زبان و وضعیت کاربران
user_languages = {}
user_states = {}  # برای ردیابی وضعیت (فروش گیفت، برداشت، و غیره)

# اتصال به پایگاه داده SQLite
conn = sqlite3.connect('wallet.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance REAL DEFAULT 0,
    language TEXT DEFAULT 'en'
)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
    id TEXT PRIMARY KEY,
    user_id INTEGER,
    currency TEXT,
    amount REAL,
    wallet_address TEXT,
    status TEXT,
    timestamp TEXT
)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS gift_requests (
    id TEXT PRIMARY KEY,
    user_id INTEGER,
    gift_link TEXT,
    proposed_amount REAL,
    status TEXT,
    timestamp TEXT
)''')
conn.commit()

# دیکشنری پیام‌ها به زبان‌های مختلف
MESSAGES = {
    'fa': {
        'welcome': 'خوش آمدید! 🎉\nاز منوی زیر گزینه مورد نظر را انتخاب کنید:',
        'no_gifts': 'شما هیچ گیفتی در Fragment ندارید!',
        'transfer_success': '{} گیفت با موفقیت دریافت شد! موجودی شما: {} دلار',
        'transfer_error': 'خطایی در انتقال گیفت‌ها رخ داد. لطفاً به صورت دستی از کیف پول TON منتقل کنید: https://tonkeeper.com',
        'generic_error': 'خطایی رخ داد: {}',
        'choose_language': 'لطفاً زبان مورد نظر خود را انتخاب کنید:',
        'language_changed': 'زبان به فارسی تغییر کرد.',
        'balance': 'موجودی شما: {} دلار',
        'choose_currency': 'ارز دیجیتال برای برداشت را انتخاب کنید:',
        'enter_amount': 'مبلغ برداشت (به دلار) را وارد کنید (موجودی: {} دلار):',
        'enter_wallet': 'آدرس کیف پول {} را وارد کنید:',
        'withdrawal_success': 'درخواست برداشت ثبت شد!\nکد پیگیری: {}\nرسید:\nارز: {}\nمبلغ: {} دلار\nآدرس: {}\nوضعیت: در انتظار',
        'withdrawal_error': 'خطایی در ثبت درخواست برداشت رخ داد. دوباره امتحان کنید.',
        'insufficient_balance': 'موجودی کافی نیست! موجودی شما: {} دلار',
        'enter_gift_link': 'لطفاً لینک گیفت Fragment را ارسال کنید (مثال: https://fragment.com/gift/123):',
        'enter_proposed_amount': 'مبلغ پیشنهادی خود را برای فروش گیفت (به دلار) وارد کنید:',
        'gift_request_sent': 'درخواست فروش گیفت ارسال شد! منتظر تأیid ادمین باشید.',
        'gift_request_rejected': 'مبلغ پیشنهادی شما بیش از قیمت واقعی محصول است.\nلطفاً دوباره تلاش کنید.',
        'admin_gift_request': 'درخواست فروش گیفت جدید:\nکاربر: {}\nلینک گیفت: {}\nمبلغ پیشنهادی: {} دلار\nآیدی درخواست: {}\nزمان: {}'
    },
    'en': {
        'welcome': 'Welcome! 🎉\nChoose an option from the menu below:',
        'no_gifts': 'You have no gifts in Fragment!',
        'transfer_success': '{} gifts received successfully! Your balance: {} USD',
        'transfer_error': 'An error occurred during gift transfer. Please transfer manually via your TON wallet: https://tonkeeper.com',
        'generic_error': 'An error occurred: {}',
        'choose_language': 'Please select your preferred language:',
        'language_changed': 'Language changed to English.',
        'balance': 'Your balance: {} USD',
        'choose_currency': 'Select the cryptocurrency for withdrawal:',
        'enter_amount': 'Enter the withdrawal amount (in USD) (Balance: {} USD):',
        'enter_wallet': 'Enter your {} wallet address:',
        'withdrawal_success': 'Withdrawal request submitted!\nTracking code: {}\nReceipt:\nCurrency: {}\nAmount: {} USD\nAddress: {}\nStatus: Pending',
        'withdrawal_error': 'An error occurred while submitting the withdrawal request. Try again.',
        'insufficient_balance': 'Insufficient balance! Your balance: {} USD',
        'enter_gift_link': 'Please send the Fragment gift link (e.g., https://fragment.com/gift/123):',
        'enter_proposed_amount': 'Enter your proposed amount for selling the gift (in USD):',
        'gift_request_sent': 'Gift sale request sent! Waiting for admin approval.',
        'gift_request_rejected': 'Your proposed amount exceeds the actual value of the gift.\nPlease try again.',
        'admin_gift_request': 'New gift sale request:\nUser: {}\nGift link: {}\nProposed amount: {} USD\nRequest ID: {}\nTime: {}'
    },
    'ru': {
        'welcome': 'Добро пожаловать! 🎉\nВыберите опцию из меню ниже:',
        'no_gifts': 'У вас нет подарков в Fragment!',
        'transfer_success': '{} подарков успешно получено! Ваш баланс: {} USD',
        'transfer_error': 'Произошла ошибка при передаче подарков. Пожалуйста, выполните перевод вручную через кошелек TON: https://tonkeeper.com',
        'generic_error': 'Произошла ошибка: {}',
        'choose_language': 'Пожалуйста, выберите предпочитаемый язык:',
        'language_changed': 'Язык изменен на русский.',
        'balance': 'Ваш баланс: {} USD',
        'choose_currency': 'Выберите криптовалюту для вывода:',
        'enter_amount': 'Введите сумму вывода (в долларах) (Баланс: {} USD):',
        'enter_wallet': 'Введите адрес кошелька {}:',
        'withdrawal_success': 'Запрос на вывод отправлен!\nКод отслеживания: {}\nКвитанция:\nВалюта: {}\nСумма: {} USD\nАдрес: {}\nСтатус: В ожидании',
        'withdrawal_error': 'Произошла ошибка при отправке запроса на вывод. Попробуйте снова.',
        'insufficient_balance': 'Недостаточный баланс! Ваш баланс: {} USD',
        'enter_gift_link': 'Пожалуйста, отправьте ссылку на подарок Fragment (например, https://fragment.com/gift/123):',
        'enter_proposed_amount': 'Введите предложенную сумму для продажи подарка (в долларах):',
        'gift_request_sent': 'Запрос на продажу подарка отправлен! Ожидайте подтверждения администратора.',
        'gift_request_rejected': 'Ваша предложенная сумма превышает реальную стоимость подарка.\nПожалуйста, попробуйте снова.',
        'admin_gift_request': 'Новый запрос на продажу подарка:\nПользователь: {}\nСсылка на подарок: {}\nПредложенная сумма: {} USD\nID запроса: {}\nВремя: {}'
    },
    'ar': {
        'welcome': 'مرحبًا! 🎉\nاختر خيارًا من القائمة أدناه:',
        'no_gifts': 'ليس لديك هدايا في Fragment!',
        'transfer_success': 'تم استلام {} هدايا بنجاح! رصيدك: {} دولار',
        'transfer_error': 'حدث خطأ أثناء نقل الهدايا. يرجى النقل يدويًا عبر محفظة TON: https://tonkeeper.com',
        'generic_error': 'حدث خطأ: {}',
        'choose_language': 'يرجى اختيار اللغة المفضلة لديك:',
        'language_changed': 'تم تغيير اللغة إلى العربية.',
        'balance': 'رصيدك: {} دولار',
        'choose_currency': 'اختر العملة الرقمية للسحب:',
        'enter_amount': 'أدخل مبلغ السحب (بالدولار) (الرصيد: {} دولار):',
        'enter_wallet': 'أدخل عنوان محفظة {}:',
        'withdrawal_success': 'تم تقديم طلب السحب!\nرمز التتبع: {}\nالإيصال:\nالعملة: {}\nالمبلغ: {} دولار\nالعنوان: {}\nالحالة: قيد الانتظار',
        'withdrawal_error': 'حدث خطأ أثناء تقديم طلب السحب. حاول مرة أخرى.',
        'insufficient_balance': 'الرصيد غير كافٍ! رصيدك: {} دولار',
        'enter_gift_link': 'يرجى إرسال رابط هدية Fragment (مثال: https://fragment.com/gift/123):',
        'enter_proposed_amount': 'أدخل المبلغ المقترح لبيع الهدية (بالدولار):',
        'gift_request_sent': 'تم إرسال طلب بيع الهدية! في انتظار موافقة الإدارة.',
        'gift_request_rejected': 'المبلغ المقترح يتجاوز القيمة الفعلية للهدية.\nيرجى المحاولة مرة أخرى.',
        'admin_gift_request': 'طلب بيع هدية جديد:\nالمستخدم: {}\nرابط الهدية: {}\nالمبلغ المقترح: {} دولار\nمعرف الطلب: {}\nالوقت: {}'
    },
    'zh': {
        'welcome': '欢迎！🎉\n请从下面的菜单中选择一个选项：',
        'no_gifts': '您在Fragment中没有任何礼物！',
        'transfer_success': '{}个礼物已成功接收！您的余额：{}美元',
        'transfer_error': '礼物转移过程中出错。请通过您的TON钱包手动转移：https://tonkeeper.com',
        'generic_error': '发生错误：{}',
        'choose_language': '请选择您喜欢的语言：',
        'language_changed': '语言已更改为中文。',
        'balance': '您的余额：{}美元',
        'choose_currency': '选择用于提取的加密货币：',
        'enter_amount': '输入提取金额（美元）（余额：{}美元）：',
        'enter_wallet': '输入您的{}钱包地址：',
        'withdrawal_success': '提取请求已提交！\n跟踪代码：{}\n收据：\n货币：{}\n金额：{}美元\n地址：{}\n状态：待处理',
        'withdrawal_error': '提交提取请求时出错。请重试。',
        'insufficient_balance': '余额不足！您的余额：{}美元',
        'enter_gift_link': '请发送Fragment礼物链接（例如：https://fragment.com/gift/123）：',
        'enter_proposed_amount': '输入您提议的礼物出售金额（美元）：',
        'gift_request_sent': '礼物出售请求已发送！等待管理员批准。',
        'gift_request_rejected': '您提议的金额超过礼物的实际价值。\n请重试。',
        'admin_gift_request': '新的礼物出售请求：\n用户：{}\n礼物链接：{}\n提议金额：{}美元\n请求ID：{}\n时间：{}'
    },
    'ja': {
        'welcome': 'ようこそ！🎉\n以下のメニューからオプションを選択してください：',
        'no_gifts': 'Fragmentにギフトがありません！',
        'transfer_success': '{}個のギフトが正常に受信されました！あなたの残高：{} USD',
        'transfer_error': 'ギフトの転送中にエラーが発生しました。TONウォレット経由で手動で転送してください：https://tonkeeper.com',
        'generic_error': 'エラーが発生しました：{}',
        'choose_language': 'ご希望の言語を選択してください：',
        'language_changed': '言語が日本語に変更されました。',
        'balance': 'あなたの残高：{} USD',
        'choose_currency': '引き出し用の暗号通貨を選択してください：',
        'enter_amount': '引き出し金額（USD）を入力してください（残高：{} USD）：',
        'enter_wallet': '{}ウォレットのアドレスを入力してください：',
        'withdrawal_success': '引き出しリクエストが送信されました！\n追跡コード：{}\n領収書：\n通貨：{}\n金額：{} USD\nアドレス：{}\nステータス：保留中',
        'withdrawal_error': '引き出しリクエストの送信中にエラーが発生しました。もう一度お試しください。',
        'insufficient_balance': '残高不足！あなたの残高：{} USD',
        'enter_gift_link': 'Fragmentギフトのリンクを送信してください（例：https://fragment.com/gift/123）：',
        'enter_proposed_amount': 'ギフトの販売のための提案金額（USD）を入力してください：',
        'gift_request_sent': 'ギフト販売リクエストが送信されました！管理者の承認を待っています。',
        'gift_request_rejected': '提案金額がギフトの実際の価値を超えています。\nもう一度お試しください。',
        'admin_gift_request': '新しいギフト販売リクエスト：\nユーザー：{}\nギフトリンク：{}\n提案金額：{} USD\nリクエストID：{}\n時間：{}'
    }
}

# ارزهای دیجیتال پشتیبانی‌شده
CURRENCIES = ['BTC', 'TRX', 'USDT', 'TON', 'BNB', 'ETH', 'ADA', 'XRP']

# تابع برای دریافت زبان کاربر
def get_user_language(user_id):
    cursor.execute('SELECT language FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    if result:
        return result[0]
    return 'en'  # زبان پیش‌فرض

# تابع برای دریافت موجودی کاربر
def get_user_balance(user_id):
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result else 0

# تابع برای به‌روزرسانی موجودی کاربر
def update_user_balance(user_id, amount):
    cursor.execute('INSERT OR REPLACE INTO users (user_id, balance, language) VALUES (?, ?, ?)',
                  (user_id, amount, get_user_language(user_id)))
    conn.commit()

# تابع برای ایجاد منوی اصلی
def create_main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("💸 فروش گیفت"), KeyboardButton("💰 موجودی"))
    keyboard.row(KeyboardButton("🏧 برداشت"), KeyboardButton("🌐 تغییر زبان"))
    return keyboard

# تابع برای ایجاد کیبورد انتخاب زبان
def create_language_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("فارسی", callback_data="lang_fa"),
        InlineKeyboardButton("English", callback_data="lang_en")
    )
    keyboard.row(
        InlineKeyboardButton("Русский", callback_data="lang_ru"),
        InlineKeyboardButton("العربية", callback_data="lang_ar")
    )
    keyboard.row(
        InlineKeyboardButton("中文", callback_data="lang_zh"),
        InlineKeyboardButton("日本語", callback_data="lang_ja")
    )
    return keyboard

# تابع برای ایجاد کیبورد انتخاب ارز
def create_currency_keyboard():
    keyboard = InlineKeyboardMarkup()
    for i in range(0, len(CURRENCIES), 2):
        row = [InlineKeyboardButton(c, callback_data=f"currency_{c}") for c in CURRENCIES[i:i+2]]
        keyboard.row(*row)
    return keyboard

# تابع برای ایجاد کیبورد تأیید انتقال گیفت
def create_confirm_transfer_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("✅ تأیید", callback_data="confirm_transfer"),
        InlineKeyboardButton("❌ لغو", callback_data="cancel_transfer")
    )
    return keyboard

# تابع برای ایجاد کیبورد تأیید/رد درخواست گیفت توسط ادمین
def create_admin_gift_keyboard(request_id):
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("✅ تأیید", callback_data=f"admin_approve_{request_id}"),
        InlineKeyboardButton("❌ رد", callback_data=f"admin_reject_{request_id}")
    )
    return keyboard

# تابع فرضی برای دریافت گیفت‌های کاربر از Fragment
def get_user_gifts(user_id, gift_link):
    try:
        url = "https://api.fragment-api.net/gifts"
        headers = {"Content-Type": "application/json"}
        data = {"user_id": str(user_id), "gift_link": gift_link}
        response = requests.post(url, headers=headers, json=data)
        return response.json().get('gifts', [])
    except Exception:
        return None

# تابع فرضی برای انتقال گیفت به کیف پول TON
def transfer_gift_to_ton(gift_id, user_id, ton_address):
    try:
        url = "https://api.fragment-api.net/transferGift"
        headers = {"Content-Type": "application/json"}
        data = {
            "gift_id": gift_id,
            "from_user_id": str(user_id),
            "to_ton_address": ton_address
        }
        response = requests.post(url, headers=headers, json=data)
        return response.status_code == 200
    except Exception:
        return False

# هندلر برای دستور /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    bot.send_message(message.chat.id, MESSAGES[lang]['welcome'], reply_markup=create_main_menu())
    cursor.execute('INSERT OR IGNORE INTO users (user_id, balance, language) VALUES (?, ?, ?)',
                  (user_id, 0, lang))
    conn.commit()

# هندلر برای دستور /language
@bot.message_handler(commands=['language'])
def handle_language(message):
    lang = get_user_language(message.from_user.id)
    bot.send_message(message.chat.id, MESSAGES[lang]['choose_language'], reply_markup=create_language_keyboard())

# هندلر برای پیام‌های متنی (فروش گیفت، برداشت، و غیره)
@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    text = message.text

    if text == '💸 فروش گیفت':
        user_states[user_id] = {'state': 'awaiting_gift_link'}
        bot.send_message(message.chat.id, MESSAGES[lang]['enter_gift_link'], reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("لغو")))
    elif text == '💰 موجودی':
        balance = get_user_balance(user_id)
        bot.send_message(message.chat.id, MESSAGES[lang]['balance'].format(balance))
    elif text == '🏧 برداشت':
        user_states[user_id] = {'state': 'awaiting_currency'}
        bot.send_message(message.chat.id, MESSAGES[lang]['choose_currency'], reply_markup=create_currency_keyboard())
    elif text == 'لغو':
        user_states.pop(user_id, None)
        bot.send_message(message.chat.id, MESSAGES[lang]['welcome'], reply_markup=create_main_menu())
    elif user_id in user_states:
        state = user_states[user_id]['state']
        if state == 'awaiting_gift_link':
            if text.startswith('https://fragment.com/gift/'):
                user_states[user_id] = {'state': 'awaiting_proposed_amount', 'gift_link': text}
                bot.send_message(message.chat.id, MESSAGES[lang]['enter_proposed_amount'])
            else:
                bot.send_message(message.chat.id, MESSAGES[lang]['enter_gift_link'])
        elif state == 'awaiting_proposed_amount':
            try:
                amount = float(text)
                gift_link = user_states[user_id]['gift_link']
                request_id = str(uuid.uuid4())
                cursor.execute('INSERT INTO gift_requests (id, user_id, gift_link, proposed_amount, status, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
                              (request_id, user_id, gift_link, amount, 'pending', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()
                bot.send_message(message.chat.id, MESSAGES[lang]['gift_request_sent'], reply_markup=create_main_menu())
                bot.send_message(ADMIN_ID, MESSAGES[lang]['admin_gift_request'].format(user_id, gift_link, amount, request_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                                reply_markup=create_admin_gift_keyboard(request_id))
                user_states.pop(user_id, None)
            except ValueError:
                bot.send_message(message.chat.id, MESSAGES[lang]['enter_proposed_amount'])
        elif state == 'awaiting_withdrawal_amount':
            try:
                amount = float(text)
                balance = get_user_balance(user_id)
                if amount > balance:
                    bot.send_message(message.chat.id, MESSAGES[lang]['insufficient_balance'].format(balance))
                    return
                user_states[user_id]['amount'] = amount
                user_states[user_id]['state'] = 'awaiting_wallet_address'
                bot.send_message(message.chat.id, MESSAGES[lang]['enter_wallet'].format(user_states[user_id]['currency']))
            except ValueError:
                bot.send_message(message.chat.id, MESSAGES[lang]['enter_amount'].format(balance))
        elif state == 'awaiting_wallet_address':
            wallet_address = text
            currency = user_states[user_id]['currency']
            amount = user_states[user_id]['amount']
            request_id = str(uuid.uuid4())
            cursor.execute('INSERT INTO withdrawals (id, user_id, currency, amount, wallet_address, status, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)',
                          (request_id, user_id, currency, amount, wallet_address, 'pending', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            new_balance = get_user_balance(user_id) - amount
            update_user_balance(user_id, new_balance)
            conn.commit()
            bot.send_message(message.chat.id, MESSAGES[lang]['withdrawal_success'].format(request_id, currency, amount, wallet_address))
            bot.send_message(ADMIN_ID, MESSAGES[lang]['admin_notification'].format(user_id, currency, amount, wallet_address, request_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            user_states.pop(user_id, None)
            bot.send_message(message.chat.id, MESSAGES[lang]['welcome'], reply_markup=create_main_menu())

# هندلر برای دکمه‌های inline
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    lang = get_user_language(user_id)
    
    if call.data.startswith('lang_'):
        lang = call.data.split('_')[1]
        cursor.execute('UPDATE users SET language = ? WHERE user_id = ?', (lang, user_id))
        conn.commit()
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            MESSAGES[lang]['language_changed'],
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=create_language_keyboard()
        )
    elif call.data == 'confirm_transfer':
        gift_link = user_states.get(user_id, {}).get('gift_link')
        if not gift_link:
            bot.send_message(call.message.chat.id, MESSAGES[lang]['generic_error'].format('No gift link found'))
            return
        gifts = get_user_gifts(user_id, gift_link)
        if not gifts:
            bot.send_message(call.message.chat.id, MESSAGES[lang]['no_gifts'])
            return
        success_count = 0
        for gift in gifts:
            if transfer_gift_to_ton(gift['id'], user_id, ETEESAL_TON_ADDRESS):
                success_count += 1
        if success_count > 0:
            proposed_amount = user_states[user_id]['proposed_amount']
            current_balance = get_user_balance(user_id)
            new_balance = current_balance + proposed_amount
            update_user_balance(user_id, new_balance)
            bot.send_message(call.message.chat.id, MESSAGES[lang]['transfer_success'].format(success_count, new_balance))
        else:
            bot.send_message(call.message.chat.id, MESSAGES[lang]['transfer_error'])
        user_states.pop(user_id, None)
    elif call.data == 'cancel_transfer':
        user_states.pop(user_id, None)
        bot.send_message(call.message.chat.id, "انتقال لغو شد.", reply_markup=create_main_menu())
    elif call.data.startswith('currency_'):
        currency = call.data.split('_')[1]
        user_states[user_id] = {'state': 'awaiting_withdrawal_amount', 'currency': currency}
        balance = get_user_balance(user_id)
        bot.send_message(call.message.chat.id, MESSAGES[lang]['enter_amount'].format(balance))
    elif call.data.startswith('admin_approve_'):
        request_id = call.data.split('_')[2]
        cursor.execute('SELECT user_id, gift_link, proposed_amount FROM gift_requests WHERE id = ?', (request_id,))
        result = cursor.fetchone()
        if result:
            user_id, gift_link, proposed_amount = result
            user_states[user_id] = {'state': 'awaiting_transfer', 'gift_link': gift_link, 'proposed_amount': proposed_amount}
            bot.send_message(user_id, MESSAGES[get_user_language(user_id)]['confirm_transfer'], reply_markup=create_confirm_transfer_keyboard())
            cursor.execute('UPDATE gift_requests SET status = ? WHERE id = ?', ('approved', request_id))
            conn.commit()
            bot.answer_callback_query(call.id, "درخواست تأیید شد.")
    elif call.data.startswith('admin_reject_'):
        request_id = call.data.split('_')[2]
        cursor.execute('SELECT user_id FROM gift_requests WHERE id = ?', (request_id,))
        result = cursor.fetchone()
        if result:
            user_id = result[0]
            lang = get_user_language(user_id)
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("تلاش مجدد", callback_data="retry_gift"),
                InlineKeyboardButton("بازگشت به منوی اصلی", callback_data="back_to_main")
            )
            bot.send_message(user_id, MESSAGES[lang]['gift_request_rejected'], reply_markup=keyboard)
            cursor.execute('UPDATE gift_requests SET status = ? WHERE id = ?', ('rejected', request_id))
            conn.commit()
            bot.answer_callback_query(call.id, "درخواست رد شد.")
    elif call.data == 'retry_gift':
        user_states[user_id] = {'state': 'awaiting_gift_link'}
        bot.send_message(call.message.chat.id, MESSAGES[lang]['enter_gift_link'], reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("لغو")))
    elif call.data == 'back_to_main':
        user_states.pop(user_id, None)
        bot.send_message(call.message.chat.id, MESSAGES[lang]['welcome'], reply_markup=create_main_menu())

# مسیر Flask برای Webhook
@app.route('/bot', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    else:
        return 'Invalid content type', 403

# تنظیم Webhook
def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

# اجرای سرور Flask
if __name__ == '__main__':
    set_webhook()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))