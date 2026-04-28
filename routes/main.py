"""
routes/main.py
──────────────────────────────────────────────────────────────────
Homepage + Coming Soon routes.

LAUNCH_MODE=0  →  Pre-launch: index renders as registration portal.
LAUNCH_MODE=1  →  Full platform: normal homepage with stats + alumni.
──────────────────────────────────────────────────────────────────
"""
import os
from flask import Blueprint, render_template
from extensions import mongo

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    # Read LAUNCH_MODE per-request so .env changes take effect without restart
    launch_mode = os.getenv('LAUNCH_MODE', '1').strip() == '1'

    alumni_count  = mongo.db.users.count_documents({'role': 'alumni', 'is_approved': True})
    jobs_count    = mongo.db.jobs.count_documents({})
    events_count  = mongo.db.events.count_documents({})

    stats = {
        'alumni_count': alumni_count,
        'jobs_count':   jobs_count,
        'events_count': events_count,
    }

    pipeline = [
        {'$match': {'role': 'alumni', 'is_approved': True}},
        {'$sample': {'size': 4}},
    ]
    featured_alumni = list(mongo.db.users.aggregate(pipeline))

    return render_template('index.html', stats=stats, featured_alumni=featured_alumni,
                           launch_mode=launch_mode)


@main_bp.route('/coming-soon')
def coming_soon():
    """Post-registration landing page shown during pre-launch period."""
    return render_template('coming_soon.html')
