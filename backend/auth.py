import jwt
from functools import wraps
from flask import request, jsonify
from config import Config
from models import User

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
            
        try:
            token = token.split(" ")[1] # Bearer <token>
            data = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
            current_user = User.query.filter_by(id=data['user_id']).first()
        except Exception as e:
            return jsonify({'message': 'Token is invalid!', 'error': str(e)}), 401

        return f(current_user, *args, **kwargs)
    
    return decorated

def roles_required(*roles):
    def wrapper(f):
        @wraps(f)
        def decorated(current_user, *args, **kwargs):
            if current_user.role not in roles:
                return jsonify({'message': 'Insufficient permissions for this action!'}), 403
            return f(current_user, *args, **kwargs)
        return decorated
    return wrapper
