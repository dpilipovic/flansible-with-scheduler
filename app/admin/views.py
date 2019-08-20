""" All flask admin routes/views defined in here. """
import re
import logging
import datetime
import json
from croniter import croniter

from flask import render_template, redirect, url_for, flash, request, Blueprint
from flask_login import current_user, login_required
# Needed to auto-generate password hash it and salt it
from werkzeug.security import generate_password_hash, check_password_hash

from app import app, buttons
from app.database.createdb import db
from app.conf.config import COMPANY_INFO
# Import Class/DB tables from Models
from app.database.models import Apiusers, Adminusers, PeriodicTask, CrontabSchedule


log = logging.getLogger('app')

admin_blueprint = Blueprint('admin', __name__, template_folder='templates/admin')


""" Declare ROUTES """
@admin_blueprint.route('/', methods=['GET', 'POST'])
@login_required
def admin_index():
        if request.method == 'GET':
            if request.referrer == None:
               return render_template("index.html", buttons=buttons, show_admin_modal=True)
            elif (request.referrer).split('/')[3] == 'admin':
               return redirect(url_for('admin.apiusers'))
        if request.method == 'POST':
            admin_login = request.form['username']
            admin_pwd = request.form['password']
            valid_admin = db.session.query(Adminusers).filter_by(username=admin_login).first()
            try:
                if check_password_hash(valid_admin.password_hash, admin_pwd) == True:
                    log.info('%s has logged in as %s into Admin page', str(current_user).split(',')[0][3:], admin_login)
                    apiusers = Apiusers.query.all()
                    return render_template("apiusers.html", apiusers=apiusers)
                else:
                    flash('Invalid admin credentials!', 'danger')
                    return render_template("index.html", buttons=buttons)
            except Exception as e:
                flash('Invalid admin credentials!', 'danger')
                log.error('Invalid admin login attempt error: %s', e)
                return render_template("index.html", buttons=buttons)

@admin_blueprint.route('/apiusers', methods=['GET', 'POST'])
@login_required
def apiusers():
    if request.referrer == None:
        return render_template("index.html", buttons=buttons, show_admin_modal=True)
    elif (request.referrer).split('/')[3] == 'admin':
        apiusers = Apiusers.query.all()
        return render_template("apiusers.html", apiusers=apiusers)
    else:
        return render_template("index.html", buttons=buttons, show_admin_modal=True)

@admin_blueprint.route('/delete_user', methods=['POST'])
@login_required
def delete_user():
    if request.referrer == None:
        return render_template("index.html", buttons=buttons, show_admin_modal=True)
    # This is only to allow post coming from one of the admin URL's otherwise redirect to admin login modal.
    elif (request.referrer).split('/')[3] == 'admin':
        uid = request.form['pass_value']
        to_delete = str(Apiusers.query.get(uid))
        try:
            Apiusers.query.filter(Apiusers.id == uid).delete()
            db.session.commit()
            log.info('%s has deleted an API user %s in Admin page', str(current_user).split(',')[0][3:], to_delete)
            flash('Record succesfully deleted!', 'info')
            return redirect(url_for('admin.apiusers'))
        except Exception as e:
            db.session.rollback()
            log.error('ERROR: %s ', str(e))
            flash('{}'.format(str(e)), 'danger')
            return redirect(url_for('admin.apiusers'))
    else:
        return render_template("index.html", buttons=buttons, show_admin_modal=True)

@admin_blueprint.route('/edit_user', methods=['POST'])
@login_required
def edit_user():
    if request.referrer == None:
        return render_template("index.html", buttons=buttons, show_admin_modal=True)
    elif (request.referrer).split('/')[3] == 'admin':
        apiusers = Apiusers.query.all()
        _id = request.form['pass_id_value']
        _username = request.form['pass_username']
        _email = request.form['pass_email']
        _notify = request.form['pass_notify']
        _notify = int(_notify == 'True')
        item = Apiusers.query.get(_id)
        try:
            item.username = _username
            item.email = _email
            item.notify = _notify
            db.session.commit()
            flash('Record succesfully edited!', 'info')
            return redirect(url_for('admin.apiusers'))
        except Exception as e:
            db.session.rollback()
            log.error('ERROR: %s ', str(e))
            flash('{}'.format(str(e)), 'danger')
            return redirect(url_for('admin.apiusers'))
    else:
        return render_template("index.html", buttons=buttons, show_admin_modal=True)

@admin_blueprint.route('/multidelete', methods=['POST'])
@login_required
def multidelete():
    if request.referrer == None:
        return render_template("index.html", buttons=buttons, show_admin_modal=True)
    elif (request.referrer).split('/')[3] == 'admin':
        apiusers = Apiusers.query.all()
        multi_delete = request.form['pass_checkedvalue'].split(",")
        multideletenames = str(Apiusers.query.filter(Apiusers.id.in_(multi_delete)).all()).strip("[]")
        try:
            Apiusers.query.filter(Apiusers.id.in_(multi_delete)).delete(synchronize_session=False)
            db.session.commit()
            log.info('%s has deleted an API users: %s in Admin page', str(current_user).split(',')[0][3:], multideletenames)
            flash('Records succesfully deleted!', 'info')
            return redirect(url_for('admin.apiusers'))
        except Exception as e:
            db.session.rollback()
            log.error('ERROR: %s ', str(e))
            flash('{}'.format(str(e)), 'danger')
            return redirect(url_for('admin.apiusers'))
    else:
        return render_template("index.html", buttons=buttons, show_admin_modal=True)

@admin_blueprint.route('/admin_reset', methods=['POST'])
@login_required
def admin_reset():
    if request.referrer == None:
        return render_template("index.html", buttons=buttons, show_admin_modal=True)
    elif (request.referrer).split('/')[3] == 'admin':
        admin_login = 'admin'
        current_pwd = request.form['current_pwd']
        new_pwd = request.form['pass1']
        confirm_pwd = request.form['pass2']
        # Validation section:
        if not new_pwd:
            flash('Password not provided.', 'danger')
            log.error('Reset admin credentials attempt failed - password not provided by user %s', str(current_user).split(',')[0][3:])
            return redirect(url_for('admin.apiusers'))
        if not re.match('\d.*[A-Z]|[A-Z].*\d', new_pwd):
            flash('Password must contain 1 capital letter and 1 number.', 'danger')
            log.error('Reset admin credentials attempt failed by user %s - password must contain 1 capital letter and 1 number', str(current_user).split(',')[0][3:])
            return redirect(url_for('admin.apiusers'))
        if len(new_pwd) < 8 or len(new_pwd) > 50:
            flash('Password must be between 8 and 50 characters.', 'danger')
            log.error('Reset admin credentials attempt failed by user %s - password must be between 8 and 50 characters.', str(current_user).split(',')[0][3:])
            return redirect(url_for('admin.apiusers'))
        # Reset Admin password if everything is ok.
        _password_hash = generate_password_hash(new_pwd)
        valid_admin = db.session.query(Adminusers).filter_by(username=admin_login).first()
        if check_password_hash(valid_admin.password_hash, current_pwd) == True:
            try:
                item = Adminusers.query.filter_by(username='admin').one()
                item.password_hash = _password_hash
                db.session.commit()
                log.info('%s has reset an admin credentials!', str(current_user).split(',')[0][3:])
                flash('Admin credentials have been reset!', 'info')
                return redirect(url_for('admin.apiusers'))
            except Exception as e:
                db.session.rollback()
                log.error('ERROR: %s ', str(e))
                flash('{}'.format(str(e)), 'danger')
                return redirect(url_for('admin.apiusers'))
        else:
            flash('Invalid admin credentials!', 'danger')
            return redirect(url_for('admin.apiusers'))
    else:
        return render_template("index.html", buttons=buttons, show_admin_modal=True)

#### Schedules Admin views

@admin_blueprint.route('/schedules', methods=['GET', 'POST'])
@login_required
def schedules():
    if request.referrer == None:
        return render_template("index.html", buttons=buttons, show_admin_modal=True)
    elif (request.referrer).split('/')[3] == 'admin':
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
        return render_template('schedules.html', schedules=schedules)
    else:
        return render_template("index.html", buttons=buttons, show_admin_modal=True)

# From here coppied routes from schedule Blueprint
@admin_blueprint.route("/resumejob", methods=['GET', 'POST'])
@login_required
def resume_job():
    if request.referrer == None:
        return render_template("index.html", buttons=buttons, show_admin_modal=True)
    elif (request.referrer).split('/')[3] == 'admin':
      _id = request.form['pass_resumeid']
      check2 = PeriodicTask.query.filter_by(id=_id, is_enabled=0).all()
      record = PeriodicTask.query.get(_id)
      _ldap_user = str(current_user).split(',')[0][3:]
      if not check2:
          flash("Scheduled task is already active.", 'danger')
          log.error("Invalid Scheduled task resume attempt. Scheduled task with id: %s is already active.", _id)
          return redirect(url_for('admin.schedules'))
      try:
          cronrecord = CrontabSchedule.query.get(record.crontab_id)
          cronjob_schedule = str('{} {} {} {} {}'.format(cronrecord.minute, cronrecord.hour, cronrecord.day_of_month, cronrecord.month_of_year, cronrecord.day_of_week))
          base = datetime.datetime.now()
          iter = croniter(cronjob_schedule, base)
          prev_run =(iter.get_prev(datetime.datetime))
          record.last_run_at = prev_run # we update last_run_at to a previous runtime and so prevent scheduler from running any extra jobs it has missed since disabled!
          record.is_enabled = 1
          db.session.commit()
          log.info('Scheduled task with name %s was re-enabled by user: %s in Admin mode.', str(record.name), _ldap_user)
      except Exception as e:
          log.error('Failed to resume a job id: %s because of error: %s', _id, (str(e)))
          flash('Failed: {}'.format(str(e)), 'danger')
          db.session.rollback()
      flash("Scheduled task has been resumed.", 'info')
      return redirect(url_for('admin.schedules'))
    else:
        return render_template("index.html", buttons=buttons, show_admin_modal=True)

@admin_blueprint.route("/pausejob", methods=['GET', 'POST'])
@login_required
def pause_job():
    if request.referrer == None:
       return render_template("index.html", buttons=buttons, show_admin_modal=True)
    elif (request.referrer).split('/')[3] == 'admin':
      _id = request.form['pass_pausedid']
      check2 = PeriodicTask.query.filter_by(id=_id, is_enabled=1).all()
      record = PeriodicTask.query.get(_id)
      _ldap_user = str(current_user).split(',')[0][3:]
      if not check2:
          flash("Scheduled task is already paused.", 'danger')
          log.error("Invalid Scheduled task pause attempt. Scheduled task with id: %s is already paused.", _id)
          return redirect(url_for('admin.schedules'))
      try:
          record.is_enabled = 0
          db.session.commit()
          log.info('Scheduled task with name %s was disabled by user: %s in Admin mode.', str(record.name), _ldap_user)
      except Exception as e:
          log.error('Failed to pause a job id: %s because of error: %s', _id, (str(e)))
          flash('Failed: {}'.format(str(e)), 'danger')
          db.session.rollback()
          return redirect(url_for('admin.schedules'))
      flash("Scheduled task has been paused.", 'info')
      return redirect(url_for('admin.schedules'))
    else:
      return render_template("index.html", buttons=buttons, show_admin_modal=True)

@admin_blueprint.route("/reschedulejob", methods=['GET', 'POST'])
@login_required
def reschedule_job():
    if request.referrer == None:
       return render_template("index.html", buttons=buttons, show_admin_modal=True)
    elif (request.referrer).split('/')[3] == 'admin':
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
      record = PeriodicTask.query.get(_id)
      _op_id = (record.task_kwargs).get('_op_id', None)
      exists = PeriodicTask.query.filter(PeriodicTask.id !=_id).filter(PeriodicTask.name == _name).first()
      # Validation section
      # validation of name
      if not _name:
          flash('No name provided.', 'danger')
          return redirect(url_for('admin.schedules'))
      if exists:
          flash('Task name %s is already in use, please choose another name.' % _name, 'danger')
          log.error('Task name is already in use %s' % _name)
          return redirect(url_for('admin.schedules'))
      # Validation of email
      if not _email:
          flash('No email provided.', 'danger')
          return redirect(url_for('admin.schedules'))
      if not re.match(r"^((([a-z]|\d|[!#\$%&'\*\+\-\/=\?\^_`{\|}~]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])+(\.([a-z]|\d|[!#\$%&'\*\+\-\/=\?\^_`{\|}~]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])+)*)|((\x22)((((\x20|\x09)*(\x0d\x0a))?(\x20|\x09)+)?(([\x01-\x08\x0b\x0c\x0e-\x1f\x7f]|\x21|[\x23-\x5b]|[\x5d-\x7e]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(\\([\x01-\x09\x0b\x0c\x0d-\x7f]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF]))))*(((\x20|\x09)*(\x0d\x0a))?(\x20|\x09)+)?(\x22)))@((([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))\.)+(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))\.?$", _email):
          flash('Provided email is not an email address', 'danger')
          return redirect(url_for('admin.schedules'))
      # Validation of cron entry - we are using croniter for this.
      if croniter.is_valid(cronjob_schedule) == False:
          flash('Invalid cronjob format: %s' % cronjob_schedule, 'danger')
          log.error('Invalid cronjob format: %s' % cronjob_schedule)
          return redirect(url_for('admin.schedules'))
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
          log.info('Scheduled task with name %s was rescheduled by user: %s in Admin mode.', str(_name), _ldap_user)
      except Exception as e:
          log.error('Failed to reschedule a job id: %s because of error: %s', _id, (str(e)))
          flash('Failed: {}'.format(str(e)), 'danger')
          db.session.rollback()
          return redirect(url_for('admin.schedules'))
      flash("Scheduled task has been rescheduled.", 'info')
      return redirect(url_for('admin.schedules'))

    else:
      return render_template("index.html", buttons=buttons, show_admin_modal=True)

@admin_blueprint.route("/deletejob", methods=['GET', 'POST'])
@login_required
def delete_job():
    if request.referrer == None:
       return render_template("index.html", buttons=buttons, show_admin_modal=True)
    elif (request.referrer).split('/')[3] == 'admin':
      _id = request.form['pass_deleteid']
      _ldap_user = str(current_user).split(',')[0][3:]
      try:
          record = PeriodicTask.query.get(_id)
          cronrecord = CrontabSchedule.query.get(record.crontab_id)
          db.session.delete(record)
          db.session.delete(cronrecord)
          db.session.commit()
          log.info('Scheduled task with name %s was deleted by user: %s in Admin mode.', str(record.name), _ldap_user)
      except Exception as e:
          log.error('Failed to delete a job id: %s because of error: %s', _id, (str(e)))
          flash('Failed: {}'.format(str(e)), 'danger')
          db.session.rollback()
          return redirect(url_for('admin.schedules'))
      flash("Scheduled task has been deleted.", 'info')
      return redirect(url_for('admin.schedules'))
    else:
      return render_template("index.html", buttons=buttons, show_admin_modal=True)

@admin_blueprint.route('/multideleteschedule', methods=['POST'])
@login_required
def multideleteschedule():
    if request.referrer == None:
        return render_template("index.html", buttons=buttons, show_admin_modal=True)
    elif (request.referrer).split('/')[3] == 'admin':
        multi_delete_schedule = request.form['pass_checkedvalue'].split(",")
        multideletenames = str(db.session.query(PeriodicTask.name).filter(PeriodicTask.id.in_(multi_delete_schedule)).all()).strip("[]").replace("(","").replace(",)","").replace("'", "")
        cids =[]
        for i in multi_delete_schedule:
            cr_id = db.session.query(PeriodicTask.crontab_id).filter(PeriodicTask.id == i).all()
            for i in cr_id:
                for c in i:
                    cids.append(c)
        delete_cronjobs = [str(i) for i in cids]
        try:
            CrontabSchedule.query.filter(CrontabSchedule.id.in_(delete_cronjobs)).delete(synchronize_session=False)
            PeriodicTask.query.filter(PeriodicTask.id.in_(multi_delete_schedule)).delete(synchronize_session=False)
            db.session.commit()
            log.info('%s has deleted Scheduled tasks with ids: %s in Admin mode.', str(current_user).split(',')[0][3:], multideletenames)
            flash('Records succesfully deleted!', 'info')
            return redirect(url_for('admin.schedules'))
        except Exception as e:
            db.session.rollback()
            log.error('ERROR: %s ', str(e))
            flash('{}'.format(str(e)), 'danger')
        return redirect(url_for('admin.schedules'))
    else:
        return render_template("index.html", buttons=buttons, show_admin_modal=True)
