from celery import Celery
from app.conf.config import BROKER_URL
from app.schedule import celeryconfig

def make_celery(app):
    # create context tasks in celery
    celery = Celery(
        app.import_name,
        broker=BROKER_URL
        #include=['app.tasks']
    )
    celery.conf.update(app.config)
    celery.config_from_object(celeryconfig)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery.Task = ContextTask

    return celery
