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
import random

from netforce.model import Model, fields, get_model
from netforce import access
from netforce import database
from netforce import utils


class User(Model):
    _name = "base.user"
    _key = ["login"]
    _name_field = "login"
    _string = "User"
    _fields = {
        "name": fields.Char("Name", required=True, search=True),
        "login": fields.Char("Login", required=True, search=True),
        "password": fields.Char("Password", password=True, size=256),
        "email": fields.Char("Email", search=True),
        "mobile": fields.Char("Mobile"),
        "role_id": fields.Many2One("role", "Role"),
        "profile_id": fields.Many2One("profile", "Profile", required=True, search=True),
        "lastlog": fields.DateTime("Last login"),
        "active": fields.Boolean("Active"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "online_status": fields.Selection([["offline", "Offline"], ["online", "Online"]], "Status", function="get_online_status"),
        "contact_id": fields.Many2One("contact", "Contact"),
        "pin_code": fields.Char("PIN Code", password=True, size=256),
        "company_id": fields.Many2One("company","Company",search=True),
        "company2_id": fields.Many2One("company","Company #2",search=True),
        "url": fields.Char("URL", size=256, search=True),
    }
    _order = "login"
    _defaults = {
        "activ_code": lambda *a: "%.x" % random.randint(0, 1 << 32),
        "active": True,
    }

    def name_search(self, name, condition=[], limit=None, context={}):
        cond = [["or", ["name", "ilike", "%" + name + "%"], ["login", "ilike", "%" + name + "%"]], condition]
        ids = self.search(cond, limit=limit)
        return self.name_get(ids, context)

    def name_get(self, ids, context={}):
        vals = []
        for obj in self.browse(ids):
            name = "%s (%s)" % (obj.name, obj.login)
            vals.append([obj.id, name])
        return vals

    def disable_users(self, context={}):
        max_users = self.get_max_users()
        if max_users is None:
            return
        db = database.get_connection()
        num_users = db.get("SELECT COUNT(*) FROM base_user WHERE active").count
        if num_users <= max_users:
            return
        res = db.get("SELECT id FROM base_user WHERE active ORDER BY id OFFSET %d LIMIT 1" % max_users)
        user_id = res.id
        db.execute("UPDATE base_user SET active=false WHERE id>=%d" % user_id)

    def delete(self, ids, **kw):
        if 1 in ids:
            raise Exception("Can not delete root user (id=1)")
        super().delete(ids, **kw)

    def send_activ_email(self, ids, context={}):
        res = get_model("email.account").search([["type", "=", "smtp"]])
        if not res:
            raise Exception("Email account not found")
        smtp_id = res[0]
        for user in self.browse(ids):
            from_addr = "support@netforce.com"
            to_addr = user.email
            subject = "Welcome to Netforce!"
            body = """Welcome to Netforce and thanks for signing up!

Click on the link below to activate your account.
http://nf1.netforce.com/action?name=nfw_activate&activ_code=%s""" % user.activ_code
            vals = {
                "type": "out",
                "account_id": smtp_id,
                "from_addr": from_addr,
                "to_addr": to_addr,
                "subject": subject,
                "body": body,
            }
            msg_id = get_model("email.message").create(vals)
            get_model("email.message").send([msg_id])

    def send_password_reset_email(self, ids, context={}):
        res = get_model("email.account").search([["type", "=", "smtp"]])
        if not res:
            raise Exception("Email account not found")
        smtp_id = res[0]
        for user in self.browse(ids):
            code = "%.x" % random.randint(0, 1 << 32)
            user.write({"reset_code": code})
            from_addr = "support@netforce.com"
            to_addr = user.email
            subject = "Netforce password reset"
            body = """Click on the link below to reset your password.
http://nf1.netforce.com/action?name=nfw_reset_passwd&reset_code=%s""" % code
            vals = {
                "type": "out",
                "account_id": smtp_id,
                "from_addr": from_addr,
                "to_addr": to_addr,
                "subject": subject,
                "body": body,
            }
            msg_id = get_model("email.message").create(vals)
            get_model("email.message").send([msg_id])

    def get_online_status(self, ids, context={}):
        vals = {}
        db = database.get_connection()
        res = db.query("SELECT user_id FROM ws_listener")
        online_ids = set([r.user_id for r in res])
        for obj in self.browse(ids):
            vals[obj.id] = obj.id in online_ids and "online" or "offline"
        return vals

    def check_password(self, login, password, context={}):
        db = database.get_connection()
        res = db.get("SELECT id,password FROM base_user WHERE login ILIKE %s", login)
        if not res:
            return None
        if not utils.check_password(password, res.password):
            return None
        return res.id

    def check_pin_code(self, ids, pin_code, context={}):
        user_id = ids[0]
        db = database.get_connection()
        res = db.get("SELECT pin_code FROM base_user WHERE id=%s", user_id)
        if not res:
            return None
        if not utils.check_password(pin_code, res.pin_code):
            return None
        return True

    def get_ui_params(self, context={}):
        user_id = access.get_active_user()
        if not user_id:
            return
        try:
            access.set_active_user(1)
            db = database.get_connection()
            if not db:
                return
            user = self.browse(user_id)
            params = {
                "name": user.name,
            }
            prof = user.profile_id
            params["default_model_perms"] = prof.default_model_perms
            params["model_perms"] = []
            for p in prof.perms:
                params["model_perms"].append({
                    "model": p.model_id.name,
                    "perm_read": p.perm_read,
                    "perm_create": p.perm_create,
                    "perm_write": p.perm_write,
                    "perm_delete": p.perm_delete,
                })
            params["field_perms"] = []
            for p in prof.field_perms:
                params["field_perms"].append({
                    "model": p.field_id.model_id.name,
                    "field": p.field_id.name,
                    "perm_read": p.perm_read,
                    "perm_write": p.perm_write,
                })
            params["default_menu_access"] = prof.default_menu_access
            params["menu_perms"] = []
            for p in prof.menu_perms:
                params["menu_perms"].append({
                    "action": p.action,
                    "menu": p.menu,
                    "access": p.access,
                })
            params["other_perms"] = [p.code for p in prof.other_perms]
            return params
        finally:
            access.set_active_user(user_id)

User.register()
