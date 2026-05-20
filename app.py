import os
import tempfile
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

PRICE_PER_GRAM = 1.5
EXTRA_PER_COLOR = 20
SHIPPING = 70

def estimate_from_file_size(file_path):
    """Dosya boyutuna göre ağırlık tahmini (asla 0 değil)"""
    try:
        size_bytes = os.path.getsize(file_path)
        size_mb = size_bytes / (1024 * 1024)
        # 1 MB -> 5 gram (daha gerçekçi bir tahmin)
        weight_g = max(0.5, size_mb * 5)
    except:
        weight_g = 5.0
    return weight_g

@app.route('/')
def index():
    return send_file('index.html')

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

        # Dosya boyutuna göre ağırlık tahmini
        weight_g = estimate_from_file_size(tmp_path)

        # Diğer hesaplamalar
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
            'warning': True  # Tahmini değer olduğunu belirt
        }
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5050)