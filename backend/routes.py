import os
import uuid
import csv
import io
from datetime import datetime, timedelta
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify, current_app, Response

from models import db, User, Recognition
from auth import token_required, roles_required
from ml_inference import ANPR_Model

api_bp = Blueprint('api', __name__)

ml_model = None

def get_model():
    global ml_model
    if ml_model is not None:
        return ml_model
    try:
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'best.onnx')
        if os.path.exists(model_path):
            ml_model = ANPR_Model(model_path)
            return ml_model
    except Exception as e:
        print("Model error:", e)
    return None

# ================= AUTHENTICATION =================

@api_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    requested_role = data.get('role', 'user')

    if not username or not email or not password:
        return jsonify({'message': 'All fields are required.'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'message': 'Username already taken.'}), 400

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    new_user = User(username=username, email=email, password_hash=hashed_password, role=requested_role)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'Registered successfully.'}), 201

@api_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data.get('username')).first()

    if not user or not check_password_hash(user.password_hash, data.get('password')):
        return jsonify({'message': 'Invalid credentials.'}), 401

    token = jwt.encode({
        'user_id': user.id,
        'role': user.role,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }, current_app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({'token': token, 'role': user.role, 'username': user.username})

# ================= 1. DETECTION MODULE (All Roles) =================

@api_bp.route('/upload', methods=['POST'])
@token_required
def upload_image(current_user):
    model = get_model()
    if not model:
        return jsonify({'message': 'ONNX Model currently unavailable. Finish local training.'}), 503

    if 'image' not in request.files:
        return jsonify({'message': 'No image part provided!'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'message': 'No selected image.'}), 400

    # Ensure unique filename
    filename = secure_filename(f"{uuid.uuid4().hex}_{file.filename}")
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        # Process from the saved file
        plate_text, conf = model.process_upload(filepath)

        # Store in DB
        rec = Recognition(
            user_id=current_user.id,
            image_url=filename,  # filename for the static route
            plate_text=plate_text,
            detection_confidence=conf
        )
        db.session.add(rec)
        db.session.commit()

        return jsonify({
            'message': 'Processed successfully',
            'plate_text': plate_text,
            'confidence': conf,
            'image_url': filename  # for frontend to display
        }), 200

    except Exception as e:
        return jsonify({'message': f'Error processing: {str(e)}'}), 500

@api_bp.route('/my-history', methods=['GET'])
@token_required
def my_history(current_user):
    records = Recognition.query.filter_by(user_id=current_user.id).order_by(Recognition.timestamp.desc()).all()
    results = [{'id': r.id, 'image': r.image_url, 'text': r.plate_text, 'conf': r.detection_confidence, 'date': r.timestamp} for r in records]
    return jsonify(results)

@api_bp.route('/my-stats', methods=['GET'])
@token_required
def my_stats(current_user):
    total = Recognition.query.filter_by(user_id=current_user.id).count()
    records = Recognition.query.filter_by(user_id=current_user.id).all()
    avg_conf = sum(r.detection_confidence for r in records) / total if total > 0 else 0
    return jsonify({'total_scans': total, 'average_confidence': round(avg_conf, 2)})

# ================= 2. TEAM MODULE (Admin, Subadmin) =================

@api_bp.route('/team-history', methods=['GET'])
@token_required
@roles_required('admin', 'subadmin')
def team_history(current_user):
    records = Recognition.query.order_by(Recognition.timestamp.desc()).all()
    results = [{'id': r.id, 'user': r.user.username, 'image': r.image_url, 'text': r.plate_text, 'conf': r.detection_confidence, 'date': r.timestamp} for r in records]
    return jsonify(results)

@api_bp.route('/export-csv', methods=['GET'])
@token_required
@roles_required('admin', 'subadmin')
def export_csv(current_user):
    records = Recognition.query.order_by(Recognition.timestamp.desc()).all()

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Username', 'Plate Text', 'Confidence', 'Timestamp', 'Original Filename'])

    for r in records:
        cw.writerow([r.id, r.user.username, r.plate_text, r.detection_confidence, r.timestamp.strftime("%Y-%m-%d %H:%M:%S"), r.image_url])

    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=team_recognitions.csv"}
    )

# ================= 3. ADMIN MODULE (Admin Only) =================

@api_bp.route('/admin/dashboard', methods=['GET'])
@token_required
@roles_required('admin')
def admin_dashboard(current_user):
    total_users = User.query.count()
    total_scans = Recognition.query.count()
    subadmins = User.query.filter_by(role='subadmin').count()
    return jsonify({
        'total_users': total_users,
        'total_scans': total_scans,
        'subadmins': subadmins
    })

@api_bp.route('/admin/users', methods=['GET'])
@token_required
@roles_required('admin')
def get_all_users(current_user):
    users = User.query.all()
    results = [{'id': u.id, 'username': u.username, 'email': u.email, 'role': u.role, 'created_at': u.created_at} for u in users]
    return jsonify(results)

@api_bp.route('/admin/users/<int:user_id>/role', methods=['PUT'])
@token_required
@roles_required('admin')
def update_user_role(current_user, user_id):
    data = request.get_json()
    new_role = data.get('role')

    if new_role not in ['user', 'subadmin', 'admin']:
        return jsonify({'message': 'Invalid role assignment.'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found.'}), 404

    user.role = new_role
    db.session.commit()

    return jsonify({'message': f'User {user.username} role updated to {new_role}.'})