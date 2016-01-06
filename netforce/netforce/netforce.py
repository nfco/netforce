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

import tornado.ioloop
import tornado.httpserver
import tornado.web
from . import controller
from . import config
from . import module
from . import template
from . import static
from . import database
import argparse
from . import model
from . import locale
from . import action
from . import layout
from . import job
from . import test
from . import loader
from . import reloader
from . import migration
from . import log
from multiprocessing import Process
import platform
import netforce
import os
import time
from .utils import print_color
import psutil
from . import ipc
import signal

NUM_PROCESSES = 0


def check_signals():
    ipc.check_signals()


def web_manager():
    handlers = controller.get_handlers()
    settings = {
        "static_handler_class": static.StaticHandler,
        "static_path": "static",
    }
    app = tornado.web.Application(handlers, **settings)
    server = tornado.httpserver.HTTPServer(app, xheaders=True)
    server.bind(int(config.get("port")))
    print("Listening on port %s..." % config.get("port"))
    if platform.system() == "Windows":  # XXX
        server.start()
    else:
        if not config.DEV_MODE:
            num_procs=NUM_PROCESSES or int(config.get("web_processes"))
        else:
            num_procs=1
        server.start(num_procs)
    cb = tornado.ioloop.PeriodicCallback(check_signals, 1000)
    cb.start()
    tornado.ioloop.IOLoop.instance().start()


def job_manager():
    job.start()


def load_modules(modules):
    print("loading modules...")
    for mod in modules:
        module.load_module(mod)

MODULE_VERSION = None


def set_module_version(v):
    global MODULE_VERSION
    MODULE_VERSION = v


def get_module_version():
    return MODULE_VERSION

web_proc=None
job_proc=None

def on_sigterm(signum,frame):
    print("Received SIGTERM pid=%s"%os.getpid())
    print("Kill all child processes...")
    root = psutil.Process(os.getpid())
    sub_pids=[]
    for child in root.get_children(recursive=True):
        sub_pids.append(child.pid)
    print("kill sub_pids",sub_pids)
    for pid in sub_pids:
        try:
            proc=psutil.Process(pid)
            proc.kill()
        except Exception as e:
            print("WARNING: failed to kill process %s: %s"%(pid,e))
    print("#"*80)
    print("ALL CHILD PROCESS KILLED, KILLING ROOT PROCESS IN 5 SECONDS...")
    print("#"*80)
    time.sleep(5);
    root.kill()

def run_server():
    global NUM_PROCESSES
    parser = argparse.ArgumentParser(description="Netforce server")
    parser.add_argument("-v", "--version", action="store_true", help="Show version information")
    parser.add_argument("-d", "--db", metavar="DB", help="Database")
    parser.add_argument("-u", "--update", action="store_true", help="Update database schema")
    parser.add_argument("-M", "--migrate", metavar="FROM_VERSION", help="Apply version migrations")
    parser.add_argument("-l", "--load", metavar="MODULE", help="Load module data")
    parser.add_argument("-s", "--export_static", action="store_true", help="Update static files")
    parser.add_argument("-t", "--test", action="store_true", help="Run unit tests")
    parser.add_argument("-D", "--devel", action="store_true", help="Development mode")
    parser.add_argument("-m", "--minify", action="store_true", help="Minify js/css")
    parser.add_argument("-f", "--force", action="store_true", help="Force")
    parser.add_argument("-j", "--jobs", action="store_true", help="Run jobs")
    parser.add_argument("-p", "--num_proc", metavar="NUM", type=int, help="Number of processes to use")
    args = parser.parse_args()
    NUM_PROCESSES = args.num_proc
    config.DEV_MODE = args.devel
    if config.DEV_MODE:
        print("running in development mode...")
    config.load_config()
    if args.version:
        version = get_module_version()
        print(version)
        return
    dbname = args.db or config.get("database")
    if dbname:
        database.set_active_db(dbname)
    ipc.init()
    if args.update:
        model.update_db(force=args.force)
        db = database.get_connection()
        db.commit()
        return
    if args.migrate is not None:
        migration.apply_migrations(from_version=args.migrate)
        db = database.get_connection()
        db.commit()
        return
    if args.load:
        loader.load_data(module=args.load)
        return
    if args.export_static:
        static.export_static()
        return
    if args.test:
        test.run_tests()
        return
    locale.load_translations()
    action.load_actions()
    layout.load_xml_layouts()
    static.make_js(minify=args.minify)
    static.make_css(minify=args.minify)
    static.make_ui_params()
    if config.DEV_MODE:
        reloader.start_reloader()
    if config.DEV_MODE or platform.system() == "Windows":  # XXX
        web_manager()
    else:
        global web_proc,job_proc
        web_proc = Process(target=web_manager)
        web_proc.start()
        if args.jobs:
            job_proc = Process(target=job_manager)
            job_proc.start()
        signal.signal(signal.SIGTERM,on_sigterm)
        web_proc.join()
        if args.jobs:
            job_proc.join()
