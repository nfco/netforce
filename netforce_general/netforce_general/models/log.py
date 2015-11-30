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

from netforce.model import Model, fields, get_model
import time
from netforce.access import get_active_user, get_ip_addr, set_active_user
from netforce.utils import get_ip_country


class Log(Model):
    _name = "log"
    _string = "Log Entry"
    _fields = {
        "date": fields.DateTime("Date", required=True, search=True),
        "user_id": fields.Many2One("base.user", "User", search=True),
        "ip_addr": fields.Char("IP Address", search=True),
        "country_id": fields.Many2One("country", "Country", readonly=True),
        "message": fields.Text("Message", required=True, search=True),
        "details": fields.Text("Details", search=True),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "related_id": fields.Reference([],"Related To"),
    }
    _defaults = {
        "date": lambda *a: time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _order = "id desc"

    def log(self, msg, details=None, ip_addr=None, related_id=None):
        uid = get_active_user()
        if not ip_addr:
            ip_addr = get_ip_addr()
        try:
            country_code = get_ip_country(ip_addr)
            res = get_model("country").search([["code", "=", country_code]])
            country_id = res[0]
        except Exception as e:
            #print("Failed to get IP country: %s"%e)
            country_id = None
        vals = {
            "user_id": uid,
            "ip_addr": ip_addr,
            "message": msg,
            "details": details,
            "country_id": country_id,
            "related_id": related_id,
        }
        set_active_user(1)
        self.create(vals)
        set_active_user(uid)

Log.register()
