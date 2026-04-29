from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from extensions import mongo
from bson import ObjectId
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

alumni_bp = Blueprint('alumni', __name__)

@alumni_bp.route('/alumni')
@login_required
def directory():
    # Server-render initial set — Alpine.js takes over for live search/filter
    alumni_members = list(mongo.db.users.find({'role': 'alumni', 'is_approved': True}).limit(50))

    # Collect distinct graduation years for the filter dropdown
    years = sorted(set(
        str(m.get('graduation_year', '') or m.get('class_batch', ''))
        for m in mongo.db.users.find({'role': 'alumni', 'is_approved': True}, {'graduation_year': 1, 'class_batch': 1})
        if m.get('graduation_year') or m.get('class_batch')
    ), reverse=True)

    for member in alumni_members:
        member['_id'] = str(member['_id'])
        if member.get('created_at'):
            member['created_at'] = member['created_at'].isoformat()
        skills = member.get('skills')
        if not skills:
            member['skills'] = []
        elif isinstance(skills, str):
            member['skills'] = [s.strip() for s in skills.split(',') if s.strip()]
        member.setdefault('current_working_company', member.get('company', ''))
        member.setdefault('class_batch', str(member.get('graduation_year', '')))
        member.setdefault('past_experience', [])
        member.setdefault('education', [])
        member.setdefault('certificates', [])

    return render_template('alumni-directory.html', alumni=alumni_members, years=years)

@alumni_bp.route('/api/alumni/search')
@login_required
def search_api():
    query  = request.args.get('q', '')
    dept   = request.args.get('dept', '')
    year   = request.args.get('year', '')   # NEW: passing/graduation year filter

    match = {'role': 'alumni', 'is_approved': True}
    if query:
        match['$or'] = [
            {'name':                    {'$regex': query, '$options': 'i'}},
            {'company':                 {'$regex': query, '$options': 'i'}},
            {'current_working_company': {'$regex': query, '$options': 'i'}},
            {'skills':                  {'$regex': query, '$options': 'i'}},
        ]
    if dept:
        match['department'] = {'$regex': dept, '$options': 'i'}
    if year:
        # Match either graduation_year (int or str) or class_batch
        try:
            yr_int = int(year)
            match['$or'] = match.get('$or', []) + [
                {'graduation_year': yr_int},
                {'graduation_year': str(yr_int)},
                {'class_batch':     str(yr_int)},
            ]
        except ValueError:
            match['class_batch'] = {'$regex': year, '$options': 'i'}

    skip  = int(request.args.get('skip',  0))
    limit = int(request.args.get('limit', 12))

    results = list(mongo.db.users.find(match, {'password': 0}).skip(skip).limit(limit))
    for r in results:
        r['_id']        = str(r['_id'])
        r['created_at'] = r['created_at'].isoformat() if r.get('created_at') else None
        skills = r.get('skills')
        if not skills:
            r['skills'] = []
        elif isinstance(skills, str):
            r['skills'] = [s.strip() for s in skills.split(',') if s.strip()]
        r.setdefault('current_working_company', r.get('company', ''))
        r.setdefault('class_batch', str(r.get('graduation_year', '')))
        r.setdefault('past_experience', [])
        r.setdefault('education', [])
        r.setdefault('certificates', [])

    return jsonify(results)

@alumni_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    jobs_posted = list(mongo.db.jobs.find({'posted_by': ObjectId(current_user.id)}))
    events_attending = list(mongo.db.events.find({'attendees': ObjectId(current_user.id)}))
    return render_template('profile.html', user=current_user, jobs=jobs_posted, events=events_attending, is_owner=True)

@alumni_bp.route('/profile/<user_id>', methods=['GET'])
@login_required
def view_profile(user_id):
    if str(current_user.id) == user_id:
        return redirect(url_for('alumni.profile'))
        
    user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if not user_data:
        flash('User not found', 'danger')
        return redirect(url_for('alumni.directory'))
        
    from models import UserMixin
    viewed_user = UserMixin(user_data)
    
    jobs_posted = list(mongo.db.jobs.find({'posted_by': ObjectId(user_id)}))
    events_attending = list(mongo.db.events.find({'attendees': ObjectId(user_id)}))
    
    return render_template('profile.html', user=viewed_user, jobs=jobs_posted, events=events_attending, is_owner=False)

@alumni_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    update_data = {
        'name': request.form.get('name'),
        'department': request.form.get('department'),
        'bio': request.form.get('bio'),
        'linkedin': request.form.get('linkedin')
    }
    
    if current_user.role == 'alumni':
        update_data['company'] = request.form.get('company')
        update_data['position'] = request.form.get('position')
        
    skills_raw = request.form.get('skills', '')
    if skills_raw:
        update_data['skills'] = [s.strip() for s in skills_raw.split(',')]
        
    mongo.db.users.update_one({'_id': ObjectId(current_user.id)}, {'$set': update_data})
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('alumni.profile'))

@alumni_bp.route('/profile/upload', methods=['POST'])
@login_required
def upload_image():
    logger.info(f"Profile upload attempt by user ID: {current_user.id}")
    
    if 'profile_image' not in request.files:
        logger.warning("No profile_image in request.files")
        flash('No image provided', 'danger')
        return redirect(url_for('alumni.profile'))
        
    file = request.files['profile_image']
    logger.info(f"File received: {file.filename}, size: {file.content_length}")
    
    if file.filename == '':
        logger.warning("Empty filename")
        flash('No file selected', 'danger')
        return redirect(url_for('alumni.profile'))
    
    from utils import save_profile_image
    
    filename = save_profile_image(file, current_user.id)
    if filename:
        logger.info(f"Image saved successfully: {filename}")
        mongo.db.users.update_one(
            {'_id': ObjectId(current_user.id)}, 
            {'$set': {'profile_image': filename}}
        )
        logger.info(f"MongoDB updated for user {current_user.id}")
        flash('Profile image updated successfully!', 'success')
    else:
        logger.error(f"Failed to save image for user {current_user.id}: invalid format")
        flash('Invalid image format. Please use JPG, PNG, or GIF (max 16MB).', 'danger')
        
    return redirect(url_for('alumni.profile'))
