from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from extensions import mongo
from bson import ObjectId

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def index():
    # ── ADMIN ────────────────────────────────────────────────
    if current_user.role == 'admin':
        return redirect(url_for('admin.dashboard'))

    # ── STUDENT / ALUMNI ─────────────────────────────────────
    alumni_count  = mongo.db.users.count_documents({'role': 'alumni', 'is_approved': True})
    jobs_count    = mongo.db.jobs.count_documents({})
    events_count  = mongo.db.events.count_documents({})

    mentorships_count = 0
    if current_user.role == 'student':
        mentorships_count = mongo.db.mentorship_requests.count_documents(
            {'student_id': ObjectId(current_user.id)}
        )
    elif current_user.role == 'alumni':
        mentorships_count = mongo.db.mentorship_requests.count_documents(
            {'alumni_id': ObjectId(current_user.id), 'status': 'pending'}
        )

    latest_jobs      = list(mongo.db.jobs.find().sort('created_at', -1).limit(4))
    upcoming_events  = list(mongo.db.events.find().sort('date', 1).limit(4))

    stats = {
        'total_alumni':   alumni_count,
        'active_jobs':    jobs_count,
        'upcoming_events': events_count,
        'mentorships':    mentorships_count,
    }

    return render_template(
        'dashboard.html',
        stats=stats,
        jobs=latest_jobs,
        events=upcoming_events,
    )
