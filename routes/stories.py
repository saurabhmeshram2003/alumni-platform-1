from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, abort
from flask_login import login_required, current_user
from extensions import mongo
from bson import ObjectId
from datetime import datetime

stories_bp = Blueprint('stories', __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serialize_story(s):
    """Convert a story document to a JSON-safe dict."""
    s['_id'] = str(s['_id'])
    s['author_id'] = str(s['author_id'])
    if isinstance(s.get('created_at'), datetime):
        s['created_at'] = s['created_at'].isoformat()
    return s


# ── Public feed ───────────────────────────────────────────────────────────────

@stories_bp.route('/success-stories')
@login_required
def index():
    """Public feed of approved stories."""
    approved = list(
        mongo.db.success_stories
        .find({'approved': True})
        .sort('created_at', -1)
        .limit(20)
    )
    for s in approved:
        s['_id'] = str(s['_id'])

    # Pending count for admin/HOD banner
    pending_count = 0
    if current_user.role in ('admin', 'hod'):
        pending_count = mongo.db.success_stories.count_documents({'approved': False, 'rejected': {'$ne': True}})

    return render_template('stories.html', stories=approved, pending_count=pending_count)


@stories_bp.route('/success-stories/<story_id>')
@login_required
def view(story_id):
    """View a single story and increment view count."""
    story = mongo.db.success_stories.find_one({'_id': ObjectId(story_id)})
    if not story:
        abort(404)
    if not story.get('approved') and current_user.role not in ('admin', 'hod'):
        abort(403)

    # Increment views
    mongo.db.success_stories.update_one(
        {'_id': ObjectId(story_id)},
        {'$inc': {'views': 1}}
    )
    story['_id'] = str(story['_id'])

    # Fetch comments
    comments = list(
        mongo.db.story_comments
        .find({'story_id': ObjectId(story_id)})
        .sort('created_at', -1)
    )
    for c in comments:
        c['_id'] = str(c['_id'])

    return render_template('story_detail.html', story=story, comments=comments)


# ── Submit (alumni only) ──────────────────────────────────────────────────────

@stories_bp.route('/success-stories/submit', methods=['GET', 'POST'])
@login_required
def submit():
    if current_user.role not in ('alumni', 'admin'):
        flash('Only alumni can submit success stories.', 'warning')
        return redirect(url_for('stories.index'))

    if request.method == 'POST':
        title   = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        tags    = request.form.get('tags', '').strip()
        media_url = request.form.get('media_url', '').strip()

        if not title or not content:
            flash('Title and story content are required.', 'danger')
            return redirect(url_for('stories.submit'))

        doc = {
            'author_id':   ObjectId(current_user.id),
            'author_name': current_user.name,
            'author_role': current_user.role,
            'author_dept': current_user.department,
            'author_company': current_user.company or '',
            'author_image': current_user.profile_image,
            'title':       title,
            'content':     content,
            'tags':        [t.strip() for t in tags.split(',') if t.strip()],
            'media_url':   media_url,
            'approved':    False,
            'rejected':    False,
            'views':       0,
            'likes':       0,
            'liked_by':    [],
            'created_at':  datetime.utcnow(),
        }
        mongo.db.success_stories.insert_one(doc)
        flash('Your story has been submitted for review! It will appear once approved.', 'success')
        return redirect(url_for('stories.index'))

    return render_template('story_submit.html')


# ── Like (toggle) ─────────────────────────────────────────────────────────────

@stories_bp.route('/success-stories/<story_id>/like', methods=['POST'])
@login_required
def like(story_id):
    story = mongo.db.success_stories.find_one({'_id': ObjectId(story_id)})
    if not story:
        return jsonify({'error': 'Not found'}), 404

    uid = ObjectId(current_user.id)
    liked_by = story.get('liked_by', [])

    if uid in liked_by:
        # Unlike
        mongo.db.success_stories.update_one(
            {'_id': ObjectId(story_id)},
            {'$pull': {'liked_by': uid}, '$inc': {'likes': -1}}
        )
        liked = False
    else:
        # Like
        mongo.db.success_stories.update_one(
            {'_id': ObjectId(story_id)},
            {'$push': {'liked_by': uid}, '$inc': {'likes': 1}}
        )
        liked = True

    updated = mongo.db.success_stories.find_one({'_id': ObjectId(story_id)})
    return jsonify({'liked': liked, 'likes': updated.get('likes', 0)})


# ── Comment ───────────────────────────────────────────────────────────────────

@stories_bp.route('/success-stories/<story_id>/comment', methods=['POST'])
@login_required
def comment(story_id):
    story = mongo.db.success_stories.find_one({'_id': ObjectId(story_id)})
    if not story or not story.get('approved'):
        return jsonify({'error': 'Not found or not published'}), 404

    text = (request.form.get('text') or request.get_json(silent=True, force=True) or {}).get('text', '')
    if isinstance(text, dict):
        text = ''
    text = str(text).strip()
    if not text:
        flash('Comment cannot be empty.', 'warning')
        return redirect(url_for('stories.view', story_id=story_id))

    c = {
        'story_id':    ObjectId(story_id),
        'author_id':   ObjectId(current_user.id),
        'author_name': current_user.name,
        'author_role': current_user.role,
        'text':        text,
        'created_at':  datetime.utcnow(),
    }
    mongo.db.story_comments.insert_one(c)
    flash('Comment posted!', 'success')
    return redirect(url_for('stories.view', story_id=story_id))


# ── Admin moderation ──────────────────────────────────────────────────────────

@stories_bp.route('/admin/stories')
@login_required
def admin_queue():
    if current_user.role not in ('admin', 'hod'):
        abort(403)
    pending = list(mongo.db.success_stories.find({'approved': False, 'rejected': {'$ne': True}}).sort('created_at', -1))
    approved = list(mongo.db.success_stories.find({'approved': True}).sort('created_at', -1))
    for s in pending + approved:
        s['_id'] = str(s['_id'])
    return render_template('story_admin.html', pending=pending, approved=approved)


@stories_bp.route('/admin/stories/<story_id>/approve', methods=['POST'])
@login_required
def approve(story_id):
    if current_user.role not in ('admin', 'hod'):
        abort(403)
    mongo.db.success_stories.update_one(
        {'_id': ObjectId(story_id)},
        {'$set': {'approved': True, 'rejected': False, 'approved_at': datetime.utcnow()}}
    )
    flash('Story approved and published!', 'success')
    return redirect(url_for('stories.admin_queue'))


@stories_bp.route('/admin/stories/<story_id>/reject', methods=['POST'])
@login_required
def reject(story_id):
    if current_user.role not in ('admin', 'hod'):
        abort(403)
    mongo.db.success_stories.update_one(
        {'_id': ObjectId(story_id)},
        {'$set': {'rejected': True, 'approved': False}}
    )
    flash('Story rejected.', 'info')
    return redirect(url_for('stories.admin_queue'))


# ── Analytics API ─────────────────────────────────────────────────────────────

@stories_bp.route('/api/analytics/stories')
@login_required
def analytics():
    if current_user.role not in ('admin', 'hod'):
        abort(403)
    total = mongo.db.success_stories.count_documents({'approved': True})
    total_views = list(mongo.db.success_stories.aggregate([
        {'$match': {'approved': True}},
        {'$group': {'_id': None, 'views': {'$sum': '$views'}, 'likes': {'$sum': '$likes'}}}
    ]))
    stats = total_views[0] if total_views else {'views': 0, 'likes': 0}
    return jsonify({
        'total_stories': total,
        'total_views':   stats.get('views', 0),
        'total_likes':   stats.get('likes', 0),
    })
