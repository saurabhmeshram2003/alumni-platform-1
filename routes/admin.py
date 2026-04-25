from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from extensions import mongo
from bson import ObjectId
from datetime import datetime, timedelta
from collections import OrderedDict

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.before_request
@login_required
def check_admin():
    if current_user.role != 'admin':
        flash('Unauthorized Access. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard.index'))

@admin_bp.route('/dashboard')
def dashboard():
    # ── Basic counts ─────────────────────────────────────────
    users_count     = mongo.db.users.count_documents({})
    jobs_count      = mongo.db.jobs.count_documents({})
    events_count    = mongo.db.events.count_documents({})
    pending_alumni  = mongo.db.users.count_documents({'role': 'alumni', 'is_approved': False})

    # ── User Role Breakdown (for pie chart) ──────────────────
    role_pipeline = [
        {"$group": {"_id": "$role", "count": {"$sum": 1}}}
    ]
    role_results = list(mongo.db.users.aggregate(role_pipeline))
    role_map = {r['_id']: r['count'] for r in role_results}
    role_chart = {
        'labels': ['Admin', 'Alumni', 'Students'],
        'data': [
            role_map.get('admin', 0),
            role_map.get('alumni', 0),
            role_map.get('student', 0),
        ]
    }

    # ── Jobs Posted Per Month (last 6 months, bar chart) ─────
    now = datetime.utcnow()
    month_labels = []
    month_counts = []
    for i in range(5, -1, -1):
        target = now - timedelta(days=i * 30)
        label  = target.strftime('%b %Y')
        month_start = datetime(target.year, target.month, 1)
        if target.month == 12:
            month_end = datetime(target.year + 1, 1, 1)
        else:
            month_end = datetime(target.year, target.month + 1, 1)
        count = mongo.db.jobs.count_documents({
            'created_at': {'$gte': month_start, '$lt': month_end}
        })
        month_labels.append(label)
        month_counts.append(count)

    jobs_chart = {'labels': month_labels, 'data': month_counts}

    # ── Recent Registrations ─────────────────────────────────
    recent_users = list(mongo.db.users.find().sort('created_at', -1).limit(5))

    return render_template(
        'admin_dashboard.html',
        stats={
            'users':         users_count,
            'jobs':          jobs_count,
            'events':        events_count,
            'pending_alumni': pending_alumni,
            'alumni':        role_map.get('alumni', 0),
            'students':      role_map.get('student', 0),
        },
        role_chart=role_chart,
        jobs_chart=jobs_chart,
        recent_users=recent_users,
    )

@admin_bp.route('/manage/users')
def manage_users():
    all_users = list(mongo.db.users.find().sort([('role', 1), ('created_at', -1)]))
    return render_template('manage-users.html', users=all_users)

@admin_bp.route('/api/approve/<user_id>', methods=['POST'])
def approve_user(user_id):
    result = mongo.db.users.update_one({'_id': ObjectId(user_id)}, {'$set': {'is_approved': True}})
    if result.modified_count:
        return jsonify({'success': True})
    return jsonify({'error': 'User not found'}), 404

@admin_bp.route('/api/delete/user/<user_id>', methods=['POST'])
def delete_user(user_id):
    if str(current_user.id) == user_id:
        return jsonify({'error': 'Cannot delete yourself'}), 400
    result = mongo.db.users.delete_one({'_id': ObjectId(user_id)})
    if result.deleted_count:
        mongo.db.jobs.delete_many({'posted_by': ObjectId(user_id)})
        mongo.db.mentorship_requests.delete_many({
            '$or': [
                {'student_id': ObjectId(user_id)},
                {'alumni_id':  ObjectId(user_id)}
            ]
        })
        return jsonify({'success': True})
    return jsonify({'error': 'Failed to delete'}), 500
