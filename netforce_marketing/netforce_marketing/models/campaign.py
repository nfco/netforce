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
from netforce.database import get_connection
from datetime import *
import time


class Campaign(Model):
    _name = "mkt.campaign"
    _string = "Campaign"
    _fields = {
        "name": fields.Char("Campaign Name", required=True, search=True),
        "date": fields.Date("Date", required=True, search=True),
        "target_lists": fields.Many2Many("mkt.target.list", "Target Lists"),
        "email_tmpl_id": fields.Many2One("email.template", "Email Template"),
        "mailbox_id": fields.Many2One("email.mailbox", "Email Mailbox"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "state": fields.Selection([["active", "Active"], ["inactive", "Inactive"]], "Status", required=True),
        "limit_day": fields.Integer("Daily Limit"),
        "limit_hour": fields.Integer("Hourly Limit"),
        "num_targets": fields.Integer("Number targets", function="get_stats", function_multi=True),
        "num_create": fields.Integer("Number emails created", function="get_stats", function_multi=True),
        "percent_create": fields.Float("% created", function="get_stats", function_multi=True),
        "num_sent": fields.Integer("Number emails sent", function="get_stats", function_multi=True),
        "percent_sent": fields.Float("% sent", function="get_stats", function_multi=True),
        "num_delivered": fields.Integer("Number emails delivered", function="get_stats", function_multi=True),
        "percent_delivered": fields.Float("% delivered", function="get_stats", function_multi=True),
        "num_bounced": fields.Integer("Number emails bounced", function="get_stats", function_multi=True),
        "percent_bounced": fields.Float("% bounced", function="get_stats", function_multi=True),
        "num_rejected": fields.Integer("Number emails rejected", function="get_stats", function_multi=True),
        "percent_rejected": fields.Float("% rejected", function="get_stats", function_multi=True),
        "num_opened": fields.Integer("Number emails opened", function="get_stats", function_multi=True),
        "percent_opened": fields.Float("% opened", function="get_stats", function_multi=True),
        "num_clicked": fields.Integer("Number emails clicked", function="get_stats", function_multi=True),
        "percent_clicked": fields.Float("% clicked", function="get_stats", function_multi=True),
        "num_create_day": fields.Integer("Emails created within day", function="get_stats", function_multi=True),
        "num_create_hour": fields.Integer("Emails created within hour", function="get_stats", function_multi=True),
        "emails": fields.One2Many("email.message", "related_id", "Emails"),
        "min_target_life": fields.Integer("Minimum Target Life (days)"),
    }
    _defaults = {
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        "state": "active",
    }

    def create_emails_all(self, context={}):
        for obj in self.search_browse([["state", "=", "active"]]):
            obj.create_emails()

    def create_emails(self, ids, context={}):
        obj = self.browse(ids)[0]
        if obj.state != "active":
            raise Exception("Invalid state")
        if not obj.email_tmpl_id:
            raise Exception("Missing email template")
        limit = None
        if obj.limit_day:
            limit = obj.limit_day - obj.num_create_day
        if obj.limit_hour:
            l = obj.limit_hour - obj.num_create_hour
            if limit is None or l < limit:
                limit = l
        sent_emails = set()
        for email in obj.emails:
            if not email.name_id:
                continue
            if email.name_id._model != "mkt.target":
                continue
            target_id = email.name_id.id
            res = get_model("mkt.target").search([["id", "=", email.name_id.id]])  # XXX
            if not res:
                continue
            target = get_model("mkt.target").browse(target_id)
            sent_emails.add(target.email)
        count = 0
        for tl in obj.target_lists:
            for target in tl.targets:
                if target.email in sent_emails:
                    continue
                if obj.min_target_life and target.target_life < obj.min_target_life:
                    continue
                if limit is not None and count >= limit:
                    break
                settings = get_model("settings").browse(1)
                data = {
                    "settings": settings,
                    "obj": target,
                }
                obj.email_tmpl_id.create_email(
                    data, name_id="mkt.target,%d" % target.id, related_id="mkt.campaign,%d" % obj.id, mailbox_id=obj.mailbox_id.id)
                count += 1
                db = get_connection()
                db.commit()
        return {
            "next": {
                "name": "campaign",
                "mode": "form",
                "active_id": obj.id,
            },
            "flash": "%d emails created" % count,
        }

    def get_stats(self, ids, context={}):
        vals = {}
        for obj_id in ids:
            vals[obj_id] = {
                "num_targets": 0,
                "num_create": 0,
                "num_sent": 0,
                "num_delivered": 0,
                "num_bounced": 0,
                "num_rejected": 0,
                "num_opened": 0,
                "num_clicked": 0,
                "num_create_day": 0,
                "num_create_hour": 0,
            }
        db = get_connection()
        res = db.query(
            "SELECT c.id,COUNT(DISTINCT t.email) FROM mkt_campaign c JOIN m2m_mkt_campaign_mkt_target_list r ON r.mkt_campaign_id=c.id JOIN mkt_target t ON t.list_id=r.mkt_target_list_id WHERE c.id IN %s GROUP BY c.id", tuple(ids))
        for r in res:
            vals[r.id]["num_targets"] = r.count
        res = db.query("SELECT related_id,COUNT(*) FROM email_message WHERE related_id IN %s GROUP BY related_id",
                       tuple(["mkt.campaign,%d" % x for x in ids]))
        for r in res:
            obj_id = int(r.related_id.split(",")[1])
            v = vals[obj_id]
            v["num_create"] = r.count
        d = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        res = db.query("SELECT related_id,COUNT(*) FROM email_message WHERE related_id IN %s AND date>%s GROUP BY related_id",
                       tuple(["mkt.campaign,%d" % x for x in ids]), d)
        for r in res:
            obj_id = int(r.related_id.split(",")[1])
            v = vals[obj_id]
            v["num_create_day"] = r.count
        d = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        res = db.query("SELECT related_id,COUNT(*) FROM email_message WHERE related_id IN %s AND date>%s GROUP BY related_id",
                       tuple(["mkt.campaign,%d" % x for x in ids]), d)
        for r in res:
            obj_id = int(r.related_id.split(",")[1])
            v = vals[obj_id]
            v["num_create_hour"] = r.count
        res = db.query("SELECT related_id,COUNT(*) FROM email_message WHERE related_id IN %s AND state='sent' GROUP BY related_id",
                       tuple(["mkt.campaign,%d" % x for x in ids]))
        for r in res:
            obj_id = int(r.related_id.split(",")[1])
            v = vals[obj_id]
            v["num_sent"] = r.count
        res = db.query("SELECT related_id,COUNT(*) FROM email_message WHERE related_id IN %s AND state='delivered' GROUP BY related_id",
                       tuple(["mkt.campaign,%d" % x for x in ids]))
        for r in res:
            obj_id = int(r.related_id.split(",")[1])
            v = vals[obj_id]
            v["num_delivered"] = r.count
        res = db.query("SELECT related_id,COUNT(*) FROM email_message WHERE related_id IN %s AND state='bounced' GROUP BY related_id",
                       tuple(["mkt.campaign,%d" % x for x in ids]))
        for r in res:
            obj_id = int(r.related_id.split(",")[1])
            v = vals[obj_id]
            v["num_bounced"] = r.count
        res = db.query("SELECT related_id,COUNT(*) FROM email_message WHERE related_id IN %s AND state='rejected' GROUP BY related_id",
                       tuple(["mkt.campaign,%d" % x for x in ids]))
        for r in res:
            obj_id = int(r.related_id.split(",")[1])
            v = vals[obj_id]
            v["num_rejected"] = r.count
        res = db.query("SELECT related_id,COUNT(*) FROM email_message WHERE related_id IN %s AND opened GROUP BY related_id",
                       tuple(["mkt.campaign,%d" % x for x in ids]))
        for r in res:
            obj_id = int(r.related_id.split(",")[1])
            v = vals[obj_id]
            v["num_opened"] = r.count
        res = db.query("SELECT related_id,COUNT(*) FROM email_message WHERE related_id IN %s AND clicked GROUP BY related_id",
                       tuple(["mkt.campaign,%d" % x for x in ids]))
        for r in res:
            obj_id = int(r.related_id.split(",")[1])
            v = vals[obj_id]
            v["num_clicked"] = r.count
        for obj in self.browse(ids):
            v = vals[obj.id]
            v["percent_create"] = v["num_create"] * 100.0 / v["num_targets"] if v["num_targets"] else None
            v["percent_sent"] = v["num_sent"] * 100.0 / v["num_create"] if v["num_create"] else None
            v["percent_delivered"] = v["num_delivered"] * 100.0 / v["num_create"] if v["num_create"] else None
            v["percent_bounced"] = v["num_bounced"] * 100.0 / v["num_create"] if v["num_create"] else None
            v["percent_rejected"] = v["num_rejected"] * 100.0 / v["num_create"] if v["num_create"] else None
            v["percent_opened"] = v["num_opened"] * 100.0 / v["num_create"] if v["num_create"] else None
            v["percent_clicked"] = v["num_clicked"] * 100.0 / v["num_create"] if v["num_create"] else None
        return vals

Campaign.register()
