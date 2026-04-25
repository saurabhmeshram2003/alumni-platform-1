"""
routes/main.py
──────────────────────────────────────────────────────────────────
Homepage route.

When REGISTRATION_ONLY=1 the index page renders as a clean
"Alumni Registration Portal" landing page (no stats DB queries needed).

When REGISTRATION_ONLY=0 (full mode) the existing stats + featured alumni
queries still run so the normal homepage works as before.
──────────────────────────────────────────────────────────────────
"""
import os
from flask import Blueprint, render_template
from extensions import mongo

main_bp = Blueprint('main', __name__)

REGISTRATION_ONLY = os.getenv('REGISTRATION_ONLY', '0').strip() == '1'


@main_bp.route('/')
def index():
    if REGISTRATION_ONLY:
        # Minimal render — no DB queries, no alumni cards, no stats
        return render_template('index.html', stats={}, featured_alumni=[])

    # ── Full mode: original logic preserved ──────────────────────────
    alumni_count  = mongo.db.users.count_documents({'role': 'alumni', 'is_approved': True})
    jobs_count    = mongo.db.jobs.count_documents({})
    events_count  = mongo.db.events.count_documents({})

    stats = {
        'alumni_count': alumni_count,
        'jobs_count':   jobs_count,
        'events_count': events_count,
    }

    # Fetch 4 random featured alumni
    pipeline = [
        {'$match': {'role': 'alumni', 'is_approved': True}},
        {'$sample': {'size': 4}},
    ]
    featured_alumni = list(mongo.db.users.aggregate(pipeline))

    return render_template('index.html', stats=stats, featured_alumni=featured_alumni)
