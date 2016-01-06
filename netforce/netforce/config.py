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

import configparser
import os

DEV_MODE = False

config = {}


def load_config(filename=None):
    global config
    if not filename:
        for f in ("server.conf", "/etc/netforce/server.conf"):
            if os.path.exists(f):
                filename = f
                break
    config = {
        "host": "localhost",
        "port": "9999",
        "db_user": "postgres",
        "db_password": "postgres",
        "super_password": "admin",
        "web_processes": "4",
        "job_processes": "1",
    }
    if filename:
        test = open(filename).read()  # XXX: test if have permissions to read
        parser = configparser.ConfigParser()
        parser.read(filename)
        if parser.has_section("server"):
            for k, v in parser.items("server"):
                config[k] = v
    else:
        print("No configuration file found")


def get(name, default=None):
    return config.get(name, default)


def get_db_url(dbname):
    user = config.get("db_user")
    password = config.get("db_password")
    if not user or not password:
        raise Exception("Failed to get URL for database '%s'" % dbname)
    host = config.get("db_host", "localhost")
    url = "postgresql://%s:%s@%s/%s" % (user, password, host, dbname)
    return url
