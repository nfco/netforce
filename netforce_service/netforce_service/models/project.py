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


class Project(Model):
    _name = "project"
    _string = "Project"
    _audit_log = True
    _fields = {
        "name": fields.Char("Project Name", required=True, search=True),
        "number": fields.Char("Project Number", search=True),
        "contact_id": fields.Many2One("contact", "Customer", search=True),
        "start_date": fields.Date("Start Date", required=True),
        "end_date": fields.Date("End Date"),
        "product_id": fields.Many2One("product", "Product"),  # XXX: deprecated
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "documents": fields.One2Many("document", "related_id", "Documents"),
        "state": fields.Selection([["in_progress", "In Progress"], ["done", "Completed"], ["canceled", "Canceled"]], "Status", required=True),
        "jobs": fields.One2Many("job", "project_id", "Jobs"),
        "tasks": fields.One2Many("task", "project_id", "Tasks"),
        "work_time": fields.One2Many("work.time", "job_id", "Work Time"),
        "claims": fields.One2Many("product.claim", "project_id", "Claim Bills"),
        "borrows": fields.One2Many("product.borrow", "project_id", "Borrow Requests"),
        "description": fields.Text("Description"),
        "track_id": fields.Many2One("account.track.categ","Actual Cost Tracking Code"),
        "track_balance": fields.Decimal("Tracking Balance",function="_get_related",function_context={"path":"track_id.balance"}),
        "sub_tracks": fields.One2Many("account.track.categ",None,"Actual Cost Sub-Tracking Codes",function="_get_related",function_context={"path":"track_id.sub_tracks"}),
        "est_track_id": fields.Many2One("account.track.categ","Estimate Cost Tracking Code"),
        "est_track_balance": fields.Decimal("Tracking Balance",function="_get_related",function_context={"path":"est_track_id.balance"}),
        "est_sub_tracks": fields.One2Many("account.track.categ",None,"Est. Cost Sub-Tracking Codes",function="_get_related",function_context={"path":"est_track_id.sub_tracks"}),
        "issues": fields.One2Many("issue","project_id","Issues"),
        "resources": fields.Many2Many("service.resource","Resources"),
        "milestones": fields.One2Many("project.milestone","project_id","Milestones"),
    }
    _order = "start_date"

    _defaults = {
        "start_date": lambda *a: time.strftime("%Y-%m-%d"),
        "state": "in_progress",
    }

Project.register()
