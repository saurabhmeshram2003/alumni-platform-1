"""
Notification helpers + route for the bell-icon feed.

Design: lightweight in-process notifications stored in MongoDB's
`notifications` collection.  No external queue required.
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from extensions import mongo
from bson import ObjectId
from datetime import datetime

notifications_bp = Blueprint('notifications', __name__)


# ─────────────────────────────────────────────────────────────────────────────
# Public helper (import this from other routes)
# ─────────────────────────────────────────────────────────────────────────────

def push_notification(user_id, title, body, link='/', ntype='info'):
    """Insert a single notification document."""
    mongo.db.notifications.insert_one({
        'user_id': ObjectId(user_id),
        'title':   title,
        'body':    body,
        'link':    link,
        'type':    ntype,          # 'job' | 'mentorship' | 'story' | 'info'
        'read':    False,
        'created_at': datetime.utcnow(),
    })


def broadcast_to_students(title, body, link='/', ntype='job'):
    """Create one notification per active student."""
    students = mongo.db.users.find(
        {'role': 'student', 'is_approved': True},
        {'_id': 1}
    )
    docs = [
        {
            'user_id':    s['_id'],
            'title':      title,
            'body':       body,
            'link':       link,
            'type':       ntype,
            'read':       False,
            'created_at': datetime.utcnow(),
        }
        for s in students
    ]
    if docs:
        mongo.db.notifications.insert_many(docs)


# ─────────────────────────────────────────────────────────────────────────────
# API routes
# ─────────────────────────────────────────────────────────────────────────────

@notifications_bp.route('/api/notifications')
@login_required
def get_notifications():
    """Return latest 15 notifications for the current user."""
    docs = list(
        mongo.db.notifications
        .find({'user_id': ObjectId(current_user.id)})
        .sort('created_at', -1)
        .limit(15)
    )
    unread = 0
    result = []
    for d in docs:
        if not d.get('read'):
            unread += 1
        result.append({
            'id':         str(d['_id']),
            'title':      d.get('title', ''),
            'body':       d.get('body', ''),
            'link':       d.get('link', '/'),
            'type':       d.get('type', 'info'),
            'read':       d.get('read', False),
            'created_at': d['created_at'].isoformat() if d.get('created_at') else '',
        })
    return jsonify({'notifications': result, 'unread': unread})


@notifications_bp.route('/api/notifications/mark-read', methods=['POST'])
@login_required
def mark_read():
    """Mark all (or specific) notifications as read."""
    data = request.get_json(silent=True) or {}
    nid  = data.get('id')
    if nid:
        mongo.db.notifications.update_one(
            {'_id': ObjectId(nid), 'user_id': ObjectId(current_user.id)},
            {'$set': {'read': True}}
        )
    else:
        mongo.db.notifications.update_many(
            {'user_id': ObjectId(current_user.id), 'read': False},
            {'$set': {'read': True}}
        )
    return jsonify({'success': True})


@notifications_bp.route('/api/notifications/unread-count')
@login_required
def unread_count():
    count = mongo.db.notifications.count_documents(
        {'user_id': ObjectId(current_user.id), 'read': False}
    )
    return jsonify({'count': count})

def broadcast_to_all(title, body, link='/', ntype='info'):
    """Create one notification per active user (alumni and students)."""
    users = mongo.db.users.find(
        {'is_approved': True, 'verified': True},
        {'_id': 1}
    )
    docs = [
        {
            'user_id':    u['_id'],
            'title':      title,
            'body':       body,
            'link':       link,
            'type':       ntype,
            'read':       False,
            'created_at': datetime.utcnow(),
        }
        for u in users
    ]
    if docs:
        mongo.db.notifications.insert_many(docs)

def broadcast_to_classmates(department, graduation_year, title, body, link='/', ntype='info'):
    """Create one notification per student/alumni in the same class/department."""
    if not department or not graduation_year:
        return
        
    classmates = mongo.db.users.find(
        {
            'is_approved': True, 
            'verified': True,
            'department': department,
            'graduation_year': graduation_year
        },
        {'_id': 1}
    )
    docs = [
        {
            'user_id':    c['_id'],
            'title':      title,
            'body':       body,
            'link':       link,
            'type':       ntype,
            'read':       False,
            'created_at': datetime.utcnow(),
        }
        for c in classmates
    ]
    if docs:
        mongo.db.notifications.insert_many(docs)
