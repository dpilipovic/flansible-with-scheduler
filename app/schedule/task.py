""" All celery scheduled task handler functions define here """
import os
import time
import sys
import fnmatch
import logging
import datetime
from datetime import timedelta
import tzlocal
import celery
from sqlalchemy import text
from app import app,buttons
from app.database.createdb import db
from app.database.models import Runhistory
from app.schedule.connect_ssh_scheduler import test_ssh, run_ssh_scheduler
from app.conf.config import APP_PATH, RETENTION_DAYS

log = logging.getLogger('app')

@celery.task()
def flansible_cleanup():
    """ Function that cleans up old runlogs and old entries in Runhistory table """
    remove_old_runlogs()
    purge_runhistory()


@celery.task()
def exec_scheduled_job(_name, _op_id, email, ldap_user):
    """ Function that executes a scheduled run """
    # Lookup command from _op_id
    cmd = None
    for btn in buttons:
           if btn['_id'] == _op_id:
                cmd = (btn['_cmd'])
                print('Command is {}'.format(cmd))
    if cmd == None:
           log.error('ERROR: Command does not exist! ')
    else:

            try:
                test_ssh(cmd)
            except ValueError as e:
                log.error('ERROR: %s ', str(e))
            else:
                tz = datetime.datetime.now(tzlocal.get_localzone())
                runlog = os.path.join("sched-runlog-" + str(_op_id) + "-" + datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S-') + (tz.tzname()) + ".log")
                runlog_path = os.path.join(APP_PATH, "logs", runlog)

                # Obtain email if the user Scheduling a task has selected to be notified, log if problem with database and continue without sending mail
                try:
                    sql = text('select email from periodic_task where name =:nm and notify="1"')
                    result = db.engine.execute(sql, {'nm': str(_name)})
                    email = [row[0] for row in result]
                except Exception as e:
                    db.session.rollback()
                    log.info('Error querying the database %s', str(e))
                    email = ''
                log.info('%s executed scheduled job with id: %s', str(ldap_user), str(_op_id))
                log.info('created playbook runlog file %s', runlog)
                run_ssh_scheduler(cmd, runlog_path, ldap_user, email)


def remove_old_runlogs():
  """ Function that removes old runlogs"""
  path = os.path.join(APP_PATH, "logs")
  now = time.time()
  for f in os.listdir(path):
    f = os.path.join(path, f)
    if os.stat(f).st_mtime < now - RETENTION_DAYS * 86400:
      if os.path.isfile(f):
        if fnmatch.fnmatch(f, '*-runlog-*'):
          os.remove(os.path.join(path, f))

def purge_runhistory():
  """ Function that purges old entries in RunHistory table """
  cleanup_days =  timedelta(days=RETENTION_DAYS)
  cleanup_days_ago = datetime.datetime.now() - cleanup_days
  try:
    Runhistory.query.filter(Runhistory.time_started < cleanup_days_ago ).delete()
    db.session.commit()
    log.info('Purged runhistory table entries older than %s.', str(cleanup_days_ago))
  except:
    log.error('ERROR: %s ', str(e))
    db.session.rollback()
