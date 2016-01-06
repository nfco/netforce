# Copyright (c) 2012-2015 Netforce Co. Ltd.
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
# OR OTHER DEALINGS IN THE SOFTWARE.

from multiprocessing import Pool, Manager
from netforce import config
from netforce.model import get_model, clear_cache
from netforce import database
from netforce.access import set_active_user
import time
import json
from datetime import datetime, timedelta
import threading
import traceback
import sys
from netforce import utils
import os

_check_times = None

def run_job(dbname, job):
    print("run_job dbname=%s pid=%s job='%s'"%(dbname, os.getpid(), job["name"]))
    database.connections.clear()
    set_active_user(1)
    database.set_active_db(dbname)
    db = database.get_connection()
    db.begin()
    clear_cache()
    m = get_model(job["model"])
    f = getattr(m, job["method"])
    if job["args"]:
        args = json.loads(job["args"])
    else:
        args = []
    db.execute("UPDATE cron_job SET state='running' WHERE id=%s", job["id"])
    db.commit()
    print("starting job '%s'"%job["name"])
    try:
            with utils.timeout(seconds=job["timeout"]):
                f(*args)
            db.commit()
            print("job '%s' success" % job["name"])
    except Exception as e:
        print("WARNING: job '%s' failed: %s"%(job["name"],e))
        db.rollback()
        t=time.strftime("%Y-%m-%d %H:%M:%S")
        msg=traceback.format_exc()
        db.execute("UPDATE cron_job SET last_error_time=%s,error_message=%s WHERE id=%s", t, msg, job["id"])
        db.commit()
    t1 = time.strftime("%Y-%m-%s %H:%M:%S")
    if job["interval_num"]:
        if job["interval_type"] == "second":
            dt = timedelta(seconds=job["interval_num"])
        elif job["interval_type"] == "minute":
            dt = timedelta(minutes=job["interval_num"])
        elif job["interval_type"] == "hour":
            dt = timedelta(hours=job["interval_num"])
        elif job["interval_type"] == "day":
            dt = timedelta(days=job["interval_num"])
        else:
            raise Exception("Missing interval unit")
        next_date = datetime.strptime(job["date"], "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        while next_date <= now:  # TODO: make this faster
            next_date += dt
        if next_date < _check_times[dbname]:
            _check_times[dbname] = next_date
        db.execute("UPDATE cron_job SET date=%s,state='waiting' WHERE id=%s",
                   next_date.strftime("%Y-%m-%d %H:%M:%S"), job["id"])
    else:
        db.execute("UPDATE cron_job SET state='done' WHERE id=%s", job["id"])
    db.commit()

def start():
    global _check_times
    print("Running jobs in process %s..."%os.getpid())
    dbname = config.get("database")
    if dbname:
        check_dbs = [dbname]
    else:
        dbnames = config.get("databases", "")
        check_dbs = [x.strip() for x in dbnames.split(",")]
    print("check_dbs", check_dbs)
    manager = Manager()
    t = datetime.now()
    _check_times = manager.dict({db: t for db in check_dbs})
    for dbname in check_dbs:
        print("resetting jobs of db '%s'"%dbname)
        db=database.connect(dbname)
        res=db.execute("UPDATE cron_job SET state='waiting' WHERE state in ('running','error')")
        db.commit()
    job_pool = Pool(processes=int(config.get("job_processes")))
    while 1:
        try:
            # print("_check_time",_check_times)
            t0 = datetime.now()
            t0_s = t0.strftime("%Y-%m-%d %H:%M:%S")
            for dbname, next_t in _check_times.items():
                if next_t > t0:
                    continue
                _check_times[dbname] = t0 + timedelta(seconds=60)
                print("Checking for scheduled jobs in database %s..." % dbname)
                db = database.connect(dbname)
                db.begin()
                res = db.query("SELECT * FROM cron_job WHERE state='waiting' ORDER BY date")
                db.commit()
                new_next_t = None
                for job in res:
                    if job.date <= t0_s:
                        job_pool.apply_async(run_job, [dbname, dict(job)])
                    else:
                        new_next_t = datetime.strptime(job.date, "%Y-%m-%d %H:%M:%S")
                        break
                if new_next_t and new_next_t < _check_times[dbname]:
                    _check_times[dbname] = new_next_t
        except Exception as e:
            import traceback; traceback.print_exc()
            print("WARNING: failed to check for jobs: %s"%e)
        time.sleep(1)


def force_check_jobs():
    print("force_check_jobs")
    return # FIXME
    #dbname = database.get_active_db()
    #print("dbname", dbname)
    #_check_times[dbname] = datetime.now()
