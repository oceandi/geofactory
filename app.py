import os
import tempfile
import json
import secrets
import logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from twilio.rest import Client

# ----- KONFİGÜRASYON -----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB

# ----- FİYAT SABİTLERİ -----
PRICE_PER_GRAM = 1.5      # TL/gram
EXTRA_PER_COLOR = 20      # TL (1 renk hariç)
SHIPPING = 70             # TL

# ----- TWILIO YAPILANDIRMASI (SENİN VERDİĞİN BİLGİLER) -----
TWILIO_ACCOUNT_SID = 'ACb3449a1320e96eb49678962c1f2475dc'
TWILIO_AUTH_TOKEN = '0376fc50593509a6afa7ce0bf8d05ff6'
TWILIO_WHATSAPP_NUMBER = 'whatsapp:+14155238886'
ADMIN_WHATSAPP_NUMBER = 'whatsapp:+905555541898'
CONTENT_SID = 'HXe5536d67b0198cf458e1bb4e140be80f'   # 9 değişkenli şablon

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# ----- YARDIMCI FONKSİYONLAR -----
def estimate_from_file_size(file_path):
    """Dosya boyutundan ağırlık tahmini (1 MB = 10 gram)"""
    try:
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        weight_g = max(0.5, size_mb * 10)
    except:
        weight_g = 5.0
    return weight_g

def send_whatsapp_template(order_data):
    """
    9 değişkenli Twilio şablonu ile sipariş bildirimi.
    Şablon:
    Yeni sipariş aldın.
    📦 Sipariş No: {{1}}
    👤 Müşteri: {{2}}
    📞 Telefon: {{3}}
    ✉️ E-posta: {{4}}
    🛠️ Malzeme: {{5}}
    🎨 Renk: {{6}}
    🔢 Adet: {{7}}
    💰 Toplam: {{8}} TL
    📝 Notlar: {{9}}
    """
    try:
        content_vars = json.dumps({
            "1": order_data['order_number'],
            "2": order_data['customer_name'],
            "3": order_data['phone'],
            "4": order_data['email'],
            "5": order_data['material'],
            "6": order_data['color_desc'],
            "7": order_data['quantity'],
            "8": f"{order_data['total_price']} TL",
            "9": order_data['notes']
        })
        message = twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            content_sid=CONTENT_SID,
            content_variables=content_vars,
            to=ADMIN_WHATSAPP_NUMBER
        )
        logger.info(f"WhatsApp mesajı gönderildi. SID: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"WhatsApp hatası: {e}")
        return False

# ----- ANA SAYFA -----
@app.route('/')
def index():
    return send_file('index.html')

# ----- FİYAT TEKLİFİ API’Sİ -----
@app.route('/quote', methods=['POST'])
def quote():
    if 'file' not in request.files:
        return jsonify({'error': 'Dosya gönderilmedi'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Dosya seçilmedi'}), 400

    material = request.form.get('material', 'pla')
    try:
        color_count = int(request.form.get('color_count', 1))
        quantity = int(request.form.get('quantity', 1))
    except ValueError:
        return jsonify({'error': 'Renk sayısı ve adet sayı olmalıdır'}), 400

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        weight_g = estimate_from_file_size(tmp_path)

        volume_cm3 = round(weight_g / 1.24, 2)
        print_minutes = round(weight_g * 4.5)
        filament_meters = round(weight_g / 1.24 * 0.35, 2)
        base_price = weight_g * PRICE_PER_GRAM
        color_fee = (color_count - 1) * EXTRA_PER_COLOR if color_count > 1 else 0
        total_price = (base_price + color_fee) * quantity + SHIPPING

        result = {
            'success': True,
            'weight_g': round(weight_g, 2),
            'volume_cm3': volume_cm3,
            'print_minutes': print_minutes,
            'filament_meters': filament_meters,
            'price_tl': round(total_price, 2),
            'breakdown': {
                'material_tl': round(base_price, 2),
                'color_fee_tl': round(color_fee, 2),
                'shipping_tl': SHIPPING,
                'quantity': quantity
            },
            'warning': True
        }
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

# ----- SİPARİŞ ONAYLA – WHATSAPP BİLDİRİMİ (9 DEĞİŞKENLİ) -----
@app.route('/send-order', methods=['POST'])
def send_order():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Geçersiz veri'}), 400

    order_number = f"SPK-{secrets.token_hex(4).upper()}"
    order_data = {
        'order_number': order_number,
        'customer_name': data.get('name', 'İsim yok'),
        'phone': data.get('phone', '-'),
        'email': data.get('email', '-'),
        'material': data.get('material', 'PLA'),
        'color_desc': data.get('color', '-'),
        'quantity': str(data.get('quantity', '1')),
        'total_price': data.get('total_price'),
        'notes': data.get('notes', '-')
    }

    if send_whatsapp_template(order_data):
        return jsonify({
            'success': True,
            'order_number': order_number,
            'message': 'Siparişiniz alındı! WhatsApp bildirimi gönderildi.'
        })
    else:
        return jsonify({'error': 'WhatsApp bildirimi gönderilemedi.'}), 500

# ----- BAŞLAT -----
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5050)