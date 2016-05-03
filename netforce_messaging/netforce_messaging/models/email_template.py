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
from netforce.template import render_template
import time
from pprint import pprint

class Template(Model):
    _name = "email.template"
    _string = "Email Template"
    _fields = {
        "name": fields.Char("Template Name", required=True, search=True),
        "from_addr": fields.Char("From", required=True),
        "to_addrs": fields.Char("To", size=256, required=True),
        "cc_addrs": fields.Char("Cc", size=256),
        "subject": fields.Char("Subject", size=256, required=True),
        # XXX: deprecated
        "content_type": fields.Selection([["plain", "Plain Text"], ["html", "HTML"]], "Content Type"),
        "body": fields.Text("Body", required=True),
        "attachments": fields.Char("Attachments", size=256),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "related": fields.Char("Related Document"),
        "contact": fields.Char("Contact"),
    }

    def create_email(self, ids, data={}, name_id=None, related_id=None, mailbox_id=None, context={}):
        obj = self.browse(ids)[0]
        try:
            from_addr = render_template(obj.from_addr or "", data)
        except:
            raise Exception("Failed to render 'From Address' in template: %s" % obj.name)
        try:
            to_addrs = render_template(obj.to_addrs or "", data)
        except:
            raise Exception("Failed to render 'To Addresses' in template: %s" % obj.name)
        if obj.cc_addrs:
            try:
                cc_addrs = render_template(obj.cc_addrs or "", data)
            except:
                raise Exception("Failed to render 'Cc Addresses' in template: %s" % obj.name)
        try:
            subject = render_template(obj.subject, data)
        except:
            raise Exception("Failed to render 'Subject' in template: %s" % obj.name)
        try:
            body = render_template(obj.body.replace("&quot;",'"'), data)
        except:
            raise Exception("Failed to render 'Body' in template: %s" % obj.body)
        if obj.related_id and not related_id:
            try:
                related_id = render_template(obj.related_id or "", data)
            except:
                raise Exception("Failed to render 'From Address' in template: %s" % obj.name)
        attachments = []
        if obj.attachments:
            try:
                files = render_template(obj.attachments, data)
                for f in files.split("|"):
                    fname = f.strip()
                    if not fname:
                        continue
                    attach_vals = {
                        "file": fname,
                    }
                    attachments.append(("create", attach_vals))
            except:
                raise Exception("Failed to render 'Attachments' in template: %s" % obj.name)
        vals = {
            "type": "out",
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "from_addr": from_addr,
            "to_addrs": to_addrs,
            "subject": subject,
            "body": body,
            "state": "to_send",
            "attachments": attachments,
            "name_id": name_id,
            "related_id": related_id,
        }
        if mailbox_id:
            vals["mailbox_id"] = mailbox_id
        pprint(vals)
        email_id = get_model("email.message").create(vals)
        return email_id

Template.register()
