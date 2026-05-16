from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from flask_login import login_required, current_user
from extensions import mongo
from bson import ObjectId
from datetime import datetime

mentorship_bp = Blueprint('mentorship', __name__)

# ── Static message templates per topic ───────────────────────────────────────
_TEMPLATES = {
    'Resume Review': [
        "Hi {name}, I'm a {dept} student and I'd love your feedback on my resume before I start applying. Could you spare 15 minutes for a quick review?",
        "Hello {name}, your journey at {company} is inspiring! Could you help me tailor my resume for a similar role? I want to make it industry-ready.",
    ],
    'Interview Prep': [
        "Hi {name}, I have an upcoming technical interview and would really appreciate mock-interview tips from someone with your experience. Could we connect?",
        "Hello {name}, I've seen how you cracked interviews at top companies. Could you share preparation strategies and common pitfalls to avoid?",
    ],
    'Career Guidance': [
        "Hi {name}, I'm unsure which career path to choose after graduation. Your experience in {company} sounds exactly what I aspire to. Could we have a 20-minute chat?",
        "Hello {name}, as a {dept} student I want to explore roles beyond the obvious. Could you guide me based on your real-world experience?",
    ],
    'Placement Help': [
        "Hi {name}, placement season is approaching and I'm feeling overwhelmed. Could you share your strategy for campus placements and what companies look for?",
        "Hello {name}, I would love tips on aptitude rounds, group discussions, and HR interviews. Would you be open to a short mentorship session?",
    ],
    'Project Help': [
        "Hi {name}, I'm working on a project related to {domain} and I'm stuck on the architecture. Could you review my approach and suggest improvements?",
        "Hello {name}, your background in {company} is very relevant to my project. Would you be willing to spend 30 minutes guiding me through technical challenges?",
    ],
    'Other': [
        "Hi {name}, I am a student from the {dept} department and I admire your career journey. I'd love to connect for some general mentorship and advice.",
        "Hello {name}, I believe your experience and perspective could really help me navigate my early career. Could we have a brief conversation?",
    ],
}


@mentorship_bp.route('/mentorship')
@login_required
def index():
    if current_user.role == 'student':
        req_id = request.args.get('req', '')
        alumni_list = list(mongo.db.users.find({'role': 'alumni', 'is_approved': True}))
        requests_list = list(mongo.db.mentorship_requests.find(
            {'student_id': ObjectId(current_user.id)}).sort('created_at', -1))

        for req in requests_list:
            alumni = mongo.db.users.find_one({'_id': req['alumni_id']})
            req['alumni_name'] = alumni['name'] if alumni else 'Unknown'

        return render_template(
            'mentorship.html',
            alumni_list=alumni_list,
            requests=requests_list,
            req_id=req_id,
            topics=list(_TEMPLATES.keys()),
        )

    elif current_user.role == 'alumni':
        requests_list = list(mongo.db.mentorship_requests.find(
            {'alumni_id': ObjectId(current_user.id)}).sort('created_at', -1))

        for req in requests_list:
            student = mongo.db.users.find_one({'_id': req['student_id']})
            req['student_name']  = student['name']       if student else 'Unknown'
            req['student_email'] = student['email']      if student else 'Unknown'
            req['student_dept']  = student['department'] if student else 'Unknown'

        return render_template('mentorship.html', requests=requests_list)

    else:
        all_requests = list(mongo.db.mentorship_requests.find().sort('created_at', -1).limit(50))
        return render_template('mentorship.html', requests=all_requests)


@mentorship_bp.route('/mentorship/request', methods=['POST'])
@login_required
def create_request():
    if current_user.role != 'student':
        flash('Only students can request mentorship.', 'warning')
        return redirect(url_for('mentorship.index'))

    alumni_id = request.form.get('alumni_id')
    message   = request.form.get('message', '').strip()
    topic     = request.form.get('topic', 'Other')
    urgency   = request.form.get('urgency', 'normal')   # 'normal' | 'urgent'

    if not message:
        flash('Please write a message to the mentor.', 'danger')
        return redirect(url_for('mentorship.index'))

    # Deduplicate active requests
    existing = mongo.db.mentorship_requests.find_one({
        'student_id': ObjectId(current_user.id),
        'alumni_id':  ObjectId(alumni_id),
        'status':     {'$in': ['pending', 'accepted']},
    })
    if existing:
        flash('You already have an active request for this alumni.', 'info')
        return redirect(url_for('mentorship.index'))

    mongo.db.mentorship_requests.insert_one({
        'student_id': ObjectId(current_user.id),
        'alumni_id':  ObjectId(alumni_id),
        'message':    message,
        'topic':      topic,
        'urgency':    urgency,
        'status':     'pending',
        'created_at': datetime.utcnow(),
    })

    # Notify the alumnus
    try:
        from routes.notifications import push_notification
        push_notification(
            alumni_id,
            title=f'New mentorship request – {topic}',
            body=f'{current_user.name} sent you a mentorship request.',
            link='/mentorship',
            ntype='mentorship',
        )
    except Exception:
        pass

    flash('Mentorship request sent! You will be notified when they respond.', 'success')
    return redirect(url_for('mentorship.index'))


@mentorship_bp.route('/mentorship/respond/<request_id>', methods=['POST'])
@login_required
def respond(request_id):
    if current_user.role not in ('alumni', 'admin'):
        return jsonify({'error': 'Unauthorized'}), 403

    # Use silent=True so missing/malformed JSON returns None instead of 400
    data = request.get_json(silent=True) or {}
    action = data.get('action', '').strip().lower()

    # Normalize: frontend may send 'rejected' or 'declined' — treat both as 'rejected'
    if action == 'declined':
        action = 'rejected'

    if action not in ('accepted', 'rejected'):
        current_app.logger.warning(f"[Mentorship] Invalid action '{action}' from user {current_user.id}")
        return jsonify({'error': f"Invalid action '{action}'. Must be 'accepted' or 'rejected'."}), 400

    try:
        result = mongo.db.mentorship_requests.update_one(
            {'_id': ObjectId(request_id)},
            {'$set': {'status': action}},
        )
    except Exception as exc:
        current_app.logger.error(f"[Mentorship] DB error updating request {request_id}: {exc}")
        return jsonify({'error': 'Database error. Please try again.'}), 500

    if result.matched_count == 0:
        return jsonify({'error': 'Request not found.'}), 404

    # Notify the student even if status was already set (matched but not modified)
    req_doc = mongo.db.mentorship_requests.find_one({'_id': ObjectId(request_id)})
    if req_doc and result.modified_count:
        verb = 'accepted' if action == 'accepted' else 'declined'
        try:
            from routes.notifications import push_notification
            push_notification(
                str(req_doc['student_id']),
                title=f'Mentorship request {verb}',
                body=f'{current_user.name} has {verb} your mentorship request.',
                link='/mentorship',
                ntype='mentorship',
            )
        except Exception as exc:
            current_app.logger.warning(f"[Mentorship] Notification failed: {exc}")

    return jsonify({'success': True, 'status': action})


# ── API: message templates ────────────────────────────────────────────────────
@mentorship_bp.route('/api/mentorship/templates')
@login_required
def get_templates():
    topic = request.args.get('topic', 'Other')
    alumnus_id = request.args.get('alumni_id', '')

    # Resolve alumnus name / company for placeholder substitution
    alum_name    = 'there'
    alum_company = 'your company'
    if alumnus_id:
        alum = mongo.db.users.find_one({'_id': ObjectId(alumnus_id)})
        if alum:
            alum_name    = alum.get('name', 'there').split()[0]
            alum_company = alum.get('company') or alum.get('current_working_company') or 'your company'

    raw = _TEMPLATES.get(topic, _TEMPLATES['Other'])
    filled = [
        t.format(
            name=alum_name,
            company=alum_company,
            dept=current_user.department or 'Engineering',
            domain='technology',
        )
        for t in raw
    ]
    return jsonify({'templates': filled, 'topic': topic})


# ── API: profile completion ───────────────────────────────────────────────────
@mentorship_bp.route('/api/profile/completion')
@login_required
def profile_completion():
    return _compute_completion(current_user.id)


def _compute_completion(user_id):
    """Compute profile completeness for any user_id and return JSON."""
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        return jsonify({'pct': 0, 'tips': []})

    checks = [
        ('profile_image',  user.get('profile_image') not in (None, '', 'default.png'),  10, 'Upload a profile photo (+10%)'),
        ('bio',            bool(user.get('bio') or user.get('biography_summary')),        15, 'Add a short biography (+15%)'),
        ('skills',         bool(user.get('skills')),                                      15, 'Add at least one skill (+15%)'),
        ('linkedin',       bool(user.get('linkedin')),                                    10, 'Add your LinkedIn URL (+10%)'),
        ('department',     bool(user.get('department')),                                  10, 'Fill in your department (+10%)'),
        ('graduation_year',bool(user.get('graduation_year')),                             10, 'Add your graduation year (+10%)'),
        ('company',        bool(user.get('company') or user.get('current_working_company')), 15, 'Add your current company/internship (+15%)'),
        ('education',      bool(user.get('education')),                                   15, 'Add your education details (+15%)'),
    ]

    earned = sum(w for _, done, w, _ in checks if done)
    tips   = [tip for _, done, _, tip in checks if not done]

    return jsonify({'pct': earned, 'tips': tips[:3]})  # max 3 tips at a time
