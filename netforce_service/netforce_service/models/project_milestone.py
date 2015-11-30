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


class Milestone(Model):
    _name = "project.milestone"
    _string = "Project Milestone"
    _audit_log = True
    _fields = {
        "project_id": fields.Many2One("project","Project", required=True, search=True),
        "name": fields.Char("Title"),
        "description": fields.Text("Description"),
        "track_id": fields.Many2One("account.track.categ","Tracking Category"),
        "plan_date_from": fields.Date("Planned Start Date"),
        "plan_date_to": fields.Date("Planned End Date"),
        "act_date_from": fields.Date("Planned Start Date"),
        "act_date_to": fields.Date("Planned End Date"),
        "track_entries": fields.One2Many("account.track.entry",None,"Actual Cost Tracking Entries",function="get_track_entries",function_write="write_track_entries"),
        "track_balance": fields.Decimal("Tracking Balance",function="_get_related",function_context={"path":"track_id.balance"}),
        "est_track_id": fields.Many2One("account.track.categ","Estimate Cost Tracking Code"),
        "est_track_entries": fields.One2Many("account.track.entry",None,"Estimate Cost Tracking Entries",function="get_est_track_entries",function_write="write_est_track_entries"),
        "est_track_balance": fields.Decimal("Tracking Balance",function="_get_related",function_context={"path":"est_track_id.balance"}),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "documents": fields.One2Many("document", "related_id", "Documents"),
        "state": fields.Selection([["planned", "Planned"], ["in_progress", "In Progress"], ["done", "Completed"], ["canceled", "Canceled"]], "Status", required=True),
    }
    _order = "project_id.start_date,sequence"
    _defaults={
        "state": "planned",
    }

Milestone.register()
