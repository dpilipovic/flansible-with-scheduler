""" All flask routes/views defined in here. """
import datetime
import time
import os
import re
import logging
import random
from croniter import croniter
import json
from threading import Timer
import tzlocal

from sqlalchemy import text
from flask import redirect, url_for, render_template, flash, request, Blueprint
from flask_login import current_user, login_required

from app import app, buttons
from app.database.createdb import db
from app.database.models import PeriodicTask, PeriodicTasks, CrontabSchedule, IntervalSchedule
from app.conf.config import COMPANY_INFO
from app.schedule.connect_ssh_scheduler import test_ssh, run_ssh_scheduler
from app.conf.config import APP_PATH, MAX_SCHEDULED_JOBS

log = logging.getLogger('app')

schedule_blueprint = Blueprint('schedule', __name__, template_folder='templates/schedule')

@schedule_blueprint.route('/listschedule', methods=['GET', 'POST'])
@login_required
def list_schedule():
    query = db.session.query(PeriodicTask.id, PeriodicTask.name, CrontabSchedule.minute, CrontabSchedule.hour, CrontabSchedule.day_of_month,  \
    CrontabSchedule.month_of_year, CrontabSchedule.day_of_week, PeriodicTask.ldap_user, PeriodicTask.email, \
    PeriodicTask.notify, PeriodicTask.is_enabled, PeriodicTask.task_kwargs)

    join_query = query.join(CrontabSchedule).all()
    resultlist = [item._asdict() for item in join_query]
    result = [i for i in resultlist if not (i['name'] == 'celery.backend_cleanup' or i['name'] == 'flansible.backend_cleanup')]
    base = datetime.datetime.now()
    for cron_dic in result:
        kw = (cron_dic.get('task_kwargs', '{}'))
        kwid = (kw.get('_op_id', None))
        eb = (cron_dic.get('is_enabled', '0'))
        if eb==0:
            next_run=datetime.datetime(datetime.MAXYEAR, 1, 1, 1)
        else:
            cl = [cron_dic[x] for x in ['minute', 'hour', 'day_of_month', 'month_of_year', 'day_of_week', ]]
            cs =  str('{} {} {} {} {}'.format(*cl))
            iter = croniter(cs, base)
            next_run=(iter.get_next(datetime.datetime))
        cron_dic.update( {'playbook_id' : kwid, 'next_run' : next_run} )
    schedules = (sorted(result, key = lambda i: i['next_run']))
    for task_dic in schedules:
        eb = (task_dic.get('is_enabled', '0'))
        if eb==0:
            task_dic['next_run'] = 'None'
    return render_template('listschedule.html', company_info=COMPANY_INFO, schedules=schedules)

@schedule_blueprint.route('/createschedule', methods=['GET', 'POST'])
@login_required
def create_schedule():
    idlist = [item.get("button_name") for item in buttons]
    return render_template('createschedule.html', company_info=COMPANY_INFO, idlist=idlist)

@schedule_blueprint.route("/scheduleresult", methods=['GET', 'POST'])
@login_required
def scheduleresult():
    idlist = [item.get("button_name") for item in buttons]
    if request.method == 'POST':
        operation_id = request.form.get('op_id')
        _op_id = [b['_id'] for b in buttons if b['button_name'] == operation_id][0]
        cmd = [b['_cmd'] for b in buttons if b['button_name'] == operation_id][0]
        _name = request.form['name']
        _minute = request.form['minute']
        _hour = request.form['hour']
        _dayofmonth = request.form['dayofmonth']
        _month = request.form['month']
        _dayofweek = request.form['dayofweek']
        _email = request.form['emails']
        shouldinotify = request.form['notify']
        _notify = (str(shouldinotify) == 'true')
        _ldap_user = str(current_user).split(',')[0][3:]
        cronjob_schedule = str('{} {} {} {} {}'.format(_minute, _hour, _dayofmonth, _month, _dayofweek))
        ### Validation section
        # Validation that task name is not already in use and whether user has created more than MAX_SCHEDULED_JOBS already
        exists = PeriodicTask.query.filter(PeriodicTask.name == _name).first()
        user_count = PeriodicTask.query.filter_by(ldap_user=str(current_user).split(',')[0][3:]).count()
        if not _name:
            flash('No name provided.', 'danger')
            return render_template('createschedule.html', company_info=COMPANY_INFO, idlist=idlist)
        if exists:
            flash('Task name is already in use %s , please choose another name.' % _name, 'danger')
            log.error('Task name is already in use %s' % _name)
            return render_template('createschedule.html', company_info=COMPANY_INFO, idlist=idlist)
        elif user_count >= int(app.config['MAX_SCHEDULED_JOBS']):
            flash('User %s has already created a maximum number of allowed Scheduled jobs.' % str(current_user).split(',')[0][3:], 'danger')
            log.error('User %s has already created a maximum number of allowed Scheduled jobs.' % str(current_user).split(',')[0][3:])
            return render_template('createschedule.html', company_info=COMPANY_INFO, idlist=idlist)
        # Validation of email
        if not _email:
            flash('No email provided.', 'danger')
            return render_template('createschedule.html', company_info=COMPANY_INFO, idlist=idlist)
        if not re.match(r"^((([a-z]|\d|[!#\$%&'\*\+\-\/=\?\^_`{\|}~]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])+(\.([a-z]|\d|[!#\$%&'\*\+\-\/=\?\^_`{\|}~]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])+)*)|((\x22)((((\x20|\x09)*(\x0d\x0a))?(\x20|\x09)+)?(([\x01-\x08\x0b\x0c\x0e-\x1f\x7f]|\x21|[\x23-\x5b]|[\x5d-\x7e]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(\\([\x01-\x09\x0b\x0c\x0d-\x7f]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF]))))*(((\x20|\x09)*(\x0d\x0a))?(\x20|\x09)+)?(\x22)))@((([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))\.)+(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))\.?$", _email):
            flash('Provided email is not an email address', 'danger')
            return render_template('createschedule.html', company_info=COMPANY_INFO, idlist=idlist)
        # Validation of cron entry - we are using croniter for this
        if croniter.is_valid(cronjob_schedule) == False:
            flash('Invalid cronjob format: %s' % cronjob_schedule, 'danger')
            log.error('Invalid cronjob format: %s' % cronjob_schedule)
            return render_template('createschedule.html', company_info=COMPANY_INFO, idlist=idlist)
        else:
            base = datetime.datetime.now()
            iter = croniter(cronjob_schedule, base)
            next_run=(iter.get_next(datetime.datetime))
        ### End validation section

            try:
                record = PeriodicTask(name=_name, task_name = 'app.schedule.task.exec_scheduled_job', ldap_user =_ldap_user, email=_email, notify =_notify)
                record.crontab = CrontabSchedule(minute=_minute, hour =_hour,  day_of_month=_dayofmonth, month_of_year=_month, day_of_week=_dayofweek)
                db.session.add(record)
                db.session.flush()
                tkw = { '_name' :  record.name, '_op_id' : _op_id, 'email' : record.email, 'ldap_user' : record.ldap_user}
                tkw1 = json.dumps(tkw)
                record.task_kwargs = json.loads(tkw1)
                db.session.commit()
                log.info('Created new Scheduled run: %s with email address %s and notification set to %s. It belongs to User: %s, next scheduled run is at: %s', _op_id, _email, bool(_notify), str(current_user).split(',')[0][3:], str(next_run))
            except Exception as e:
                log.error('ERROR: %s ', str(e))
                flash('{}'.format(str(e)), 'danger')
                db.session.rollback()
                return render_template("create_schedule.html", company_info=COMPANY_INFO, idlist=idlist)
            return redirect(url_for('schedule.list_schedule'))

@schedule_blueprint.route("/resumejob", methods=['GET', 'POST'])
@login_required
def resume_job():
    _id = request.form['pass_resumeid']
    _ldap_user = str(current_user).split(',')[0][3:]
    check1 = PeriodicTask.query.filter_by(id=_id, ldap_user=_ldap_user).all()
    check2 = PeriodicTask.query.filter_by(id=_id, is_enabled=0).all()
    record = PeriodicTask.query.get(_id)
    if not check1:
        flash("Scheduled task doesn't belong to you. Only user who created it or admin can make changes.", 'danger')
        log.error("Invalid Scheduled task resume attempt. Scheduled task with id: %s doesn't belong to %s", _id, _ldap_user)
        return redirect(url_for('schedule.list_schedule'))
    if not check2:
        flash("Scheduled task is already active.", 'danger')
        log.error("Invalid Scheduled task resume attempt. Scheduled task with id: %s is already active.", _id)
        return redirect(url_for('schedule.list_schedule'))
    try:
        cronrecord = CrontabSchedule.query.get(record.crontab_id)
        cronjob_schedule = str('{} {} {} {} {}'.format(cronrecord.minute, cronrecord.hour, cronrecord.day_of_month, cronrecord.month_of_year, cronrecord.day_of_week))
        base = datetime.datetime.now()
        iter = croniter(cronjob_schedule, base)
        prev_run =(iter.get_prev(datetime.datetime))
        record.last_run_at = prev_run # we update last_run_at to a previous runtime and so prevent scheduler from running any extra jobs it has missed since disabled!
        record.is_enabled = 1
        db.session.commit()
        log.info('Scheduled task with name %s was re-enabled by user: %s', str(record.name), _ldap_user)
    except Exception as e:
        log.error('Failed to resume a job id: %s because of error: %s', _id, (str(e)))
        flash('Failed: {}'.format(str(e)), 'danger')
        db.session.rollback()
    flash("Scheduled task has been resumed.", 'info')
    return redirect(url_for('schedule.list_schedule'))

@schedule_blueprint.route("/pausejob", methods=['GET', 'POST'])
@login_required
def pause_job():
    _id = request.form['pass_pausedid']
    _ldap_user = str(current_user).split(',')[0][3:]
    check1 = PeriodicTask.query.filter_by(id=_id, ldap_user=_ldap_user).all()
    check2 = PeriodicTask.query.filter_by(id=_id, is_enabled=1).all()
    record = PeriodicTask.query.get(_id)
    if not check1:
        flash("Scheduled task doesn't belong to you. Only user who created it or admin can make changes.", 'danger')
        log.error("Invalid Scheduled task resume attempt. Scheduled task with id: %s doesn't belong to %s", _id, _ldap_user)
        return redirect(url_for('schedule.list_schedule'))
    if not check2:
        flash("Scheduled task is already paused.", 'danger')
        log.error("Invalid Scheduled task pause attempt. Scheduled task with id: %s is already paused.", _id)
        return redirect(url_for('schedule.list_schedule'))
    try:
        record.is_enabled = 0
        db.session.commit()
        log.info('Scheduled task with name %s was disabled by user: %s', str(record.name), _ldap_user)
    except Exception as e:
        log.error('Failed to pause a job id: %s because of error: %s', _id, (str(e)))
        flash('Failed: {}'.format(str(e)), 'danger')
        db.session.rollback()
        return redirect(url_for('schedule.list_schedule'))
    flash("Scheduled task has been paused.", 'info')
    return redirect(url_for('schedule.list_schedule'))

@schedule_blueprint.route("/reschedulejob", methods=['GET', 'POST'])
@login_required
def reschedule_job():
    _id = request.form['pass_rescheduleid']
    _name = request.form['pass_name']
    _email = request.form['pass_email']
    shouldinotify = request.form['pass_notify']
    _notify = (str(shouldinotify) == 'True')
    _minute = request.form['pass_minute']
    _hour = request.form['pass_hour']
    _dayofmonth = request.form['pass_day']
    _month = request.form['pass_month']
    _dayofweek = request.form['pass_dayofweek']
    _ldap_user = str(current_user).split(',')[0][3:]
    cronjob_schedule = str('{} {} {} {} {}'.format(_minute, _hour, _dayofmonth, _month, _dayofweek))
    check1 = PeriodicTask.query.filter_by(id=_id, ldap_user=_ldap_user).all()
    record = PeriodicTask.query.get(_id)
    _op_id = (record.task_kwargs).get('_op_id', None)
    exists = PeriodicTask.query.filter(PeriodicTask.id !=_id).filter(PeriodicTask.name == _name).first()
    # Validation section
    # Validate if scheduled task belongs to current user.
    if not check1:
        flash("Scheduled task doesn't belong to you. Only user who created it or admin can make changes.", 'danger')
        log.error("Invalid Scheduled task resume attempt. Scheduled task with id: %s doesn't belong to %s", _id, _ldap_user)
        return redirect(url_for('schedule.list_schedule'))
    # validation of name
    if not _name:
        flash('No name provided.', 'danger')
        return render_template('createschedule.html', company_info=COMPANY_INFO, idlist=idlist)
    if exists:
        flash('Task name %s is already in use, please choose another name.' % _name, 'danger')
        log.error('Task name is already in use %s' % _name)
        return render_template('createschedule.html', company_info=COMPANY_INFO, idlist=idlist)
    # Validation of email
    if not _email:
        flash('No email provided.', 'danger')
        return redirect(url_for('schedule.list_schedule'))
    if not re.match(r"^((([a-z]|\d|[!#\$%&'\*\+\-\/=\?\^_`{\|}~]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])+(\.([a-z]|\d|[!#\$%&'\*\+\-\/=\?\^_`{\|}~]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])+)*)|((\x22)((((\x20|\x09)*(\x0d\x0a))?(\x20|\x09)+)?(([\x01-\x08\x0b\x0c\x0e-\x1f\x7f]|\x21|[\x23-\x5b]|[\x5d-\x7e]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(\\([\x01-\x09\x0b\x0c\x0d-\x7f]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF]))))*(((\x20|\x09)*(\x0d\x0a))?(\x20|\x09)+)?(\x22)))@((([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))\.)+(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))\.?$", _email):
        flash('Provided email is not an email address', 'danger')
        return redirect(url_for('schedule.list_schedule'))
    # Validation of cron entry - we are using croniter for this.
    if croniter.is_valid(cronjob_schedule) == False:
        flash('Invalid cronjob format: %s' % cronjob_schedule, 'danger')
        log.error('Invalid cronjob format: %s' % cronjob_schedule)
        return redirect(url_for('schedule.list_schedule'))
    # End validation section

    try:
        record.name = _name
        record.email = _email
        record.notify = _notify
        db.session.query(CrontabSchedule).filter(CrontabSchedule.id==record.crontab_id).delete()
        record.crontab = CrontabSchedule(minute=_minute, hour =_hour, day_of_month=_dayofmonth, month_of_year=_month, day_of_week=_dayofweek)
        db.session.add(record)
        db.session.flush()
        tkw = { '_name' :  record.name, '_op_id' : _op_id, 'email' : record.email, 'ldap_user' : record.ldap_user}
        tkw1 = json.dumps(tkw)
        record.task_kwargs = json.loads(tkw1)
        db.session.commit()
        log.info('Scheduled task with name %s was rescheduled by user: %s', str(_name), _ldap_user)
    except Exception as e:
        log.error('Failed to reschedule a job id: %s because of error: %s', _id, (str(e)))
        flash('Failed: {}'.format(str(e)), 'danger')
        db.session.rollback()
        return redirect(url_for('schedule.list_schedule'))
    flash("Scheduled task has been rescheduled.", 'info')
    return redirect(url_for('schedule.list_schedule'))

@schedule_blueprint.route("/deletejob", methods=['GET', 'POST'])
@login_required
def delete_job():
    _id = request.form['pass_deleteid']
    _ldap_user = str(current_user).split(',')[0][3:]
    check1 = PeriodicTask.query.filter_by(id=_id, ldap_user=_ldap_user).all()
    if not check1:
        flash("Scheduled task doesn't belong to you. Only user who created it or admin can make changes.", 'danger')
        log.error("Invalid Scheduled task deletion attempt. Scheduled task with id: %s doesn't belong to %s", _id, _ldap_user)
        return redirect(url_for('schedule.list_schedule'))
    try:
        record = PeriodicTask.query.get(_id)
        cronrecord = CrontabSchedule.query.get(record.crontab_id)
        db.session.delete(record)
        db.session.delete(cronrecord)
        db.session.commit()
        log.info('Scheduled task with name %s was deleted by user: %s.', str(record.name), _ldap_user)
    except Exception as e:
        log.error('Failed to delete a job id: %s because of error: %s', _id, (str(e)))
        flash('Failed: {}'.format(str(e)), 'danger')
        db.session.rollback()
        return redirect(url_for('schedule.list_schedule'))
    flash("Scheduled task has been deleted.", 'info')
    return redirect(url_for('schedule.list_schedule'))
