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

from netforce import get_module_version
from netforce.model import Model, fields, get_model
from netforce import database
import json
from netforce import config
import xmlrpc.client
import time
from netforce.utils import get_ip_country, new_token, get_file_path
from netforce.logger import audit_log
from netforce.access import set_active_user, get_ip_addr, get_active_user, set_active_company
import urllib


class Login(Model):
    _name = "login"
    _transient = True

    _fields = {
        "db_name": fields.Selection([], "Database", required=True),
        "login": fields.Char("Login", required=True),
        "password": fields.Char("Password", required=True),
        "show_dbs": fields.Boolean("Show DBs"),
        "company_logo": fields.Char("Company Logo", size=256),
    }

    def get_show_dbs(self, context={}):
        if config.get("database"):
            return False
        elif config.get("database_from_domain"):
            request = context["request"]
            host = request.host
            subdom = host.split(".", 1)[0]
            if subdom not in ("all", "clients"):  # XXX
                return False
        elif config.get("database_from_http_header"):
            return False
        return True

    def get_db_name(self, context={}):
        if config.get("database"):
            dbname = config.get("database")
            return dbname
        elif config.get("database_from_domain"):
            request = context["request"]
            host = request.host
            subdom = host.split(".", 1)[0]
            if subdom not in ("all", "clients"):  # XXX
                dbname = subdom.replace("-", "_")
                return dbname
        elif config.get("database_from_http_header"):
            request = context["request"]
            dbname = request.headers.get("X-Database")
            return dbname
        return None

    def get_company_logo(self, context={}):
        dbname = database.get_active_db()
        if not dbname:
            return None
        user_id = get_active_user()
        try:
            set_active_user(1)
            res = get_model("company").search([["parent_id", "=", None]], order="id")
            if not res:
                return None
            company_id = res[0]
            set_active_company(company_id)
            settings = get_model("settings").browse(1)
            if not settings.logo:
                return None
            return "/static/db/%s/files/%s" % (dbname, settings.logo)
        finally:
            set_active_user(user_id)

    _defaults = {
        "show_dbs": get_show_dbs,
        "db_name": get_db_name,
        "company_logo": get_company_logo,
    }

    def get_databases(self, context={}):
        if config.get("database"):
            dbname = config.get("database")
            return [(dbname, dbname)]
        elif config.get("database_from_domain"):
            request = context["request"]
            host = request.host
            subdom = host.split(".", 1)[0]
            if subdom not in ("all", "clients"):  # XXX
                dbname = subdom.replace("-", "_")
                return [(dbname, dbname)]
        elif config.get("database_from_http_header"):
            request = context["request"]
            dbname = request.headers.get("X-Database")
            return [(dbname, dbname)]
        db_list = sorted(database.list_databases())
        if config.get("force_list_dbs"):
            db_list = database.list_databases()
        return [(x, x) for x in db_list]

    def login(self, context={}):
        set_active_user(None)
        data = context["data"]
        db_name = data.get("db_name")
        if not db_name:
            raise Exception("Missing db name")
        database.set_active_db(db_name)
        login = data["login"]
        password = data["password"]
        user_id = get_model("base.user").check_password(login, password)
        if not user_id:
            audit_log("Invalid login (%s)" % login)
            db = database.get_connection()
            db.commit()
            raise Exception("Invalid login")
        try:
            print("login ok", login)
            set_active_user(1)
            user = get_model("base.user").browse(user_id)
            if user.profile_id.prevent_login or not user.active:
                raise Exception("User not allowed to login")
            t = time.strftime("%Y-%m-%d %H:%M:%S")
            user.write({"lastlog": t})
            profile = user.profile_id
            action = profile.home_action or "account_board"
            token = new_token(db_name, user_id)
            db = database.get_connection()
            res = db.get("SELECT * FROM pg_class WHERE relname='settings'")
            settings = get_model("settings").browse(1)
            version = settings.version
            mod_version = get_module_version()
            if version != mod_version:
                raise Exception("Database version (%s) is different than modules version (%s), please upgrade database before login." % (
                    version, mod_version))
            company_id = user.company_id.id or profile.login_company_id.id
            if not company_id:
                res = get_model("company").search([["parent_id", "=", None]])
                if not res:
                    raise Exception("No company found")
                company_id = res[0]
            comp = get_model("company").browse(company_id)
            return {
                "cookies": {
                    "dbname": database.get_active_db(),
                    "user_id": user_id,
                    "token": token,
                    "user_name": user.name,
                    "package": settings.package,
                    "company_id": company_id,
                    "company_name": comp.name,
                },
                "next": {
                    "type": "url",
                    "url": "/ui#name=%s" % action,
                },
            }
        finally:
            set_active_user(user_id)
            audit_log("Login")

    def logout(self, context={}):
        print("logout1")
        audit_log("Logout")
        print("logout2")
        return {
            "cookies": {
                "dbname": None,
                "user_id": None,
                "user_name": None,
                "company_name": None,
                "package": None,
                "company_id": None,
                "token": None,
            },
            "next": {
                "name": "login",
            }
        }

Login.register()
