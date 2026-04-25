from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from extensions import mongo
from bson import ObjectId
from datetime import datetime

jobs_bp = Blueprint('jobs', __name__)

@jobs_bp.route('/jobs')
@login_required
def index():
    jobs_list = list(mongo.db.jobs.find().sort('created_at', -1))
    return render_template('jobs.html', jobs=jobs_list)

@jobs_bp.route('/jobs/post', methods=['GET', 'POST'])
@login_required
def post_job():
    if current_user.role != 'alumni' and current_user.role != 'admin':
        flash('Only alumni and admins can post jobs.', 'warning')
        return redirect(url_for('jobs.index'))
        
    if request.method == 'POST':
        new_job = {
            'title': request.form.get('title'),
            'company': request.form.get('company'),
            'location': request.form.get('location'),
            'description': request.form.get('description'),
            'requirements': request.form.get('requirements'),
            'application_link': request.form.get('application_link'),
            'posted_by': ObjectId(current_user.id),
            'poster_name': current_user.name,
            'created_at': datetime.utcnow()
        }
        mongo.db.jobs.insert_one(new_job)
        flash('Job posted successfully!', 'success')
        return redirect(url_for('jobs.index'))
        
    return render_template('post_job.html')

@jobs_bp.route('/jobs/edit/<job_id>', methods=['GET', 'POST'])
@login_required
def edit_job(job_id):
    job = mongo.db.jobs.find_one({'_id': ObjectId(job_id)})
    if not job:
        flash('Job not found.', 'danger')
        return redirect(url_for('jobs.index'))

    # Only the poster or an admin can edit
    if str(job['posted_by']) != current_user.id and current_user.role != 'admin':
        flash('You do not have permission to edit this job.', 'danger')
        return redirect(url_for('jobs.index'))

    if request.method == 'POST':
        updated = {
            'title': request.form.get('title'),
            'company': request.form.get('company'),
            'location': request.form.get('location'),
            'description': request.form.get('description'),
            'requirements': request.form.get('requirements'),
            'application_link': request.form.get('application_link'),
            'updated_at': datetime.utcnow()
        }
        mongo.db.jobs.update_one({'_id': ObjectId(job_id)}, {'$set': updated})
        flash('Job updated successfully!', 'success')
        return redirect(url_for('jobs.index'))

    # Convert ObjectId for template
    job['_id'] = str(job['_id'])
    return render_template('edit_job.html', job=job)

@jobs_bp.route('/jobs/delete/<job_id>', methods=['POST'])
@login_required
def delete_job(job_id):
    job = mongo.db.jobs.find_one({'_id': ObjectId(job_id)})
    if job and (str(job['posted_by']) == current_user.id or current_user.role == 'admin'):
        mongo.db.jobs.delete_one({'_id': ObjectId(job_id)})
        flash('Job removed.', 'success')
    else:
        flash('Permission denied.', 'danger')
    return redirect(request.referrer or url_for('jobs.index'))

@jobs_bp.route('/api/charts/jobs')
@login_required
def jobs_chart_api():
    """Real jobs-per-month aggregation from MongoDB."""
    from datetime import timedelta
    now = datetime.utcnow()
    labels, data = [], []
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
        labels.append(label)
        data.append(count)
    return jsonify({'labels': labels, 'data': data})

@jobs_bp.route('/api/jobs')
@login_required
def api_jobs():
    skip = int(request.args.get('skip', 0))
    limit = int(request.args.get('limit', 10))
    location = request.args.get('location', '')
    remote = request.args.get('remote', 'false')

    match = {}
    if location:
        match['location'] = {'$regex': location, '$options': 'i'}
    if remote == 'true':
        match['location'] = {'$regex': 'remote', '$options': 'i'}

    jobs = list(mongo.db.jobs.find(match).sort('created_at', -1).skip(skip).limit(limit))
    for j in jobs:
        j['_id'] = str(j['_id'])
        j['posted_by'] = str(j['posted_by'])
        j['created_at'] = j['created_at'].isoformat() if 'created_at' in j else None
        
    return jsonify(jobs)
