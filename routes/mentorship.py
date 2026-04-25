from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from extensions import mongo
from bson import ObjectId
from datetime import datetime

mentorship_bp = Blueprint('mentorship', __name__)

@mentorship_bp.route('/mentorship')
@login_required
def index():
    if current_user.role == 'student':
        # Fetch pre-selected alumni ID if navigated from directory
        req_id = request.args.get('req', '')
        alumni_list = list(mongo.db.users.find({'role': 'alumni', 'is_approved': True}))
        requests_list = list(mongo.db.mentorship_requests.find({'student_id': ObjectId(current_user.id)}).sort('created_at', -1))
        
        # Hydrate alumni details for the student's requests
        for req in requests_list:
            alumni = mongo.db.users.find_one({'_id': req['alumni_id']})
            req['alumni_name'] = alumni['name'] if alumni else 'Unknown'
            
        return render_template('mentorship.html', alumni_list=alumni_list, requests=requests_list, req_id=req_id)
        
    elif current_user.role == 'alumni':
        requests_list = list(mongo.db.mentorship_requests.find({'alumni_id': ObjectId(current_user.id)}).sort('created_at', -1))
        
        # Hydrate student details for the alumni's inbox
        for req in requests_list:
            student = mongo.db.users.find_one({'_id': req['student_id']})
            req['student_name'] = student['name'] if student else 'Unknown'
            req['student_email'] = student['email'] if student else 'Unknown'
            req['student_dept'] = student['department'] if student else 'Unknown'
            
        return render_template('mentorship.html', requests=requests_list)
        
    else:
        # Admin view - optionally show all mentorship activity
        all_requests = list(mongo.db.mentorship_requests.find().sort('created_at', -1).limit(50))
        return render_template('mentorship.html', requests=all_requests)

@mentorship_bp.route('/mentorship/request', methods=['POST'])
@login_required
def create_request():
    if current_user.role != 'student':
        flash('Only students can request mentorship.', 'warning')
        return redirect(url_for('mentorship.index'))
        
    alumni_id = request.form.get('alumni_id')
    message = request.form.get('message')
    
    # Check if a pending or accepted request already exists
    existing = mongo.db.mentorship_requests.find_one({
        'student_id': ObjectId(current_user.id),
        'alumni_id': ObjectId(alumni_id),
        'status': {'$in': ['pending', 'accepted']}
    })
    
    if existing:
        flash('You already have an active or pending request for this alumni.', 'info')
        return redirect(url_for('mentorship.index'))
        
    new_req = {
        'student_id': ObjectId(current_user.id),
        'alumni_id': ObjectId(alumni_id),
        'message': message,
        'status': 'pending',
        'created_at': datetime.utcnow()
    }
    
    mongo.db.mentorship_requests.insert_one(new_req)
    flash('Mentorship request sent successfully. You will be notified when they respond.', 'success')
    return redirect(url_for('mentorship.index'))

@mentorship_bp.route('/mentorship/respond/<request_id>', methods=['POST'])
@login_required
def respond(request_id):
    if current_user.role != 'alumni' and current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    data = request.get_json()
    action = data.get('action') # 'accepted' or 'rejected'
    
    if action not in ['accepted', 'rejected']:
        return jsonify({'error': 'Invalid action'}), 400
        
    result = mongo.db.mentorship_requests.update_one(
        {'_id': ObjectId(request_id)},
        {'$set': {'status': action}}
    )
    
    if result.modified_count:
        return jsonify({'success': True, 'status': action})
    return jsonify({'error': 'Failed to update request'}), 500
