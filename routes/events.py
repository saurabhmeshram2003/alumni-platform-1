from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from extensions import mongo
from bson import ObjectId
from datetime import datetime

events_bp = Blueprint('events', __name__)

@events_bp.route('/events')
def index():
    # Publicly visible array of events (or login required, depends on preference)
    events_list = list(mongo.db.events.find().sort('date', 1))
    return render_template('events.html', events=events_list)

@events_bp.route('/events/create', methods=['POST'])
@login_required
def create():
    if current_user.role != 'admin':
        flash('Unauthorized. Only Admins can create events.', 'danger')
        return redirect(url_for('events.index'))
        
    date_str = request.form.get('date')
    time_str = request.form.get('time', '00:00')
    dt_str = f"{date_str} {time_str}"
    
    try:
        event_date = datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
    except ValueError:
        event_date = datetime.strptime(date_str, '%Y-%m-%d')
        
    new_event = {
        'title': request.form.get('title'),
        'date': event_date,
        'location': request.form.get('location'),
        'description': request.form.get('description'),
        'type': request.form.get('type', 'General'),
        'created_by': ObjectId(current_user.id),
        'attendees': []
    }
    
    mongo.db.events.insert_one(new_event)
    
    try:
        from routes.notifications import broadcast_to_all
        broadcast_to_all(
            title="New event added",
            body=f"A new event '{new_event['title']}' has been scheduled.",
            link='/events',
            ntype='info'
        )
    except Exception:
        pass
        
    flash('Event created successfully!', 'success')
    return redirect(url_for('events.index'))

@events_bp.route('/events/register/<event_id>', methods=['POST'])
@login_required
def register(event_id):
    result = mongo.db.events.update_one(
        {'_id': ObjectId(event_id)},
        {'$addToSet': {'attendees': ObjectId(current_user.id)}}
    )
    
    if request.is_json:
        if result.modified_count:
            return jsonify({'success': True, 'message': 'Successfully registered'})
        return jsonify({'success': False, 'message': 'Already registered'})
        
    if result.modified_count:
        flash('Successfully registered for the event!', 'success')
    else:
        flash('You are already registered for this event.', 'info')
    return redirect(url_for('events.index'))
