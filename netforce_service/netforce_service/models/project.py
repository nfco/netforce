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
        "track_entries": fields.One2Many("account.track.entry",None,"Actual Cost Tracking Entries",function="get_track_entries",function_write="write_track_entries"),
        "track_balance": fields.Decimal("Tracking Balance",function="_get_related",function_context={"path":"track_id.balance"}),
        "est_track_id": fields.Many2One("account.track.categ","Estimate Cost Tracking Code"),
        "est_track_entries": fields.One2Many("account.track.entry",None,"Estimate Cost Tracking Entries",function="get_est_track_entries",function_write="write_est_track_entries"),
        "est_track_balance": fields.Decimal("Tracking Balance",function="_get_related",function_context={"path":"est_track_id.balance"}),
        "issues": fields.One2Many("issue","project_id","Issues"),
        "resources": fields.Many2Many("service.resource","Resources"),
        "milestones": fields.One2Many("project.milestone","project_id","Milestones"),
    }
    _order = "start_date"

    _defaults = {
        "start_date": lambda *a: time.strftime("%Y-%m-%d"),
        "state": "in_progress",
    }

    def get_track_entries(self,ids,context={}):
        vals={}
        for obj in self.browse(ids):
            if not obj.track_id:
                vals[obj.id]=[]
                continue
            res=get_model("account.track.entry").search([["track_id","child_of",obj.track_id.id]])
            vals[obj.id]=res
        return vals

    def get_est_track_entries(self,ids,context={}):
        vals={}
        for obj in self.browse(ids):
            if not obj.track_id:
                vals[obj.id]=[]
                continue
            res=get_model("account.track.entry").search([["track_id","child_of",obj.est_track_id.id]])
            vals[obj.id]=res
        return vals

    def create_track(self,ids,context={}):
        obj=self.browse(ids[0])
        if not obj.number:
            raise Exception("Missing project number")
        res=get_model("account.track.categ").search([["code","=",obj.number]])
        if res:
            track_id=res[0]
        else:
            track_id=get_model("account.track.categ").create({
                "code": obj.number,
                "name": obj.name,
                "type": "1",
                })
        obj.write({"track_id": track_id})

    def create_est_track(self,ids,context={}):
        obj=self.browse(ids[0])
        if not obj.number:
            raise Exception("Missing project number")
        code=obj.number+"-EST"
        res=get_model("account.track.categ").search([["code","=",code]])
        if res:
            track_id=res[0]
        else:
            track_id=get_model("account.track.categ").create({
                "code": code,
                "name": obj.name+" (Est)",
                "type": "1",
                })
        obj.write({"est_track_id": track_id})

    def write_track_entries(self,ids,field,val,context={}):
        for op in val:
            if op[0]=="create":
                rel_vals=op[1]
                for obj in self.browse(ids):
                    if not obj.track_id:
                        continue
                    rel_vals["track_id"]=obj.track_id.id
                    get_model("account.track.entry").create(rel_vals,context=context)
            elif op[0]=="write":
                rel_ids=op[1]
                rel_vals=op[2]
                get_model("account.track.entry").write(rel_ids,rel_vals,context=context)
            elif op[0]=="delete":
                rel_ids=op[1]

    def write_est_track_entries(self,ids,field,val,context={}):
        for op in val:
            if op[0]=="create":
                rel_vals=op[1]
                for obj in self.browse(ids):
                    if not obj.track_id:
                        continue
                    rel_vals["track_id"]=obj.est_track_id.id
                    get_model("account.track.entry").create(rel_vals,context=context)
            elif op[0]=="write":
                rel_ids=op[1]
                rel_vals=op[2]
                get_model("account.track.entry").write(rel_ids,rel_vals,context=context)
            elif op[0]=="delete":
                rel_ids=op[1]
                get_model("account.track.entry").delete(rel_ids,context=context)
                get_model("account.track.entry").delete(rel_ids,context=context)

Project.register()
