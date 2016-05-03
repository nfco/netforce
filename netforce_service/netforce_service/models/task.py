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

from netforce.model import Model, fields, get_model, clear_cache
from netforce.database import get_connection
from datetime import *
import time
from netforce import access

def is_holiday(d):
    w=d.weekday()
    if w==5 or w==6:
        return True
    res=get_model("hr.holiday").search([["date","=",d.strftime("%Y-%m-%d")]])
    if res:
        return True
    return False

class Task(Model):
    _name = "task"
    _string = "Task"
    _name_field = "title"
    _fields = {
        "number": fields.Char("Number",required=True,search=True),
        "sequence": fields.Integer("Sequence"),
        "date_created": fields.DateTime("Date Created",required=True,search=True),
        "project_id": fields.Many2One("project","Project",required=True,search=True),
        "milestone_id": fields.Many2One("project.milestone","Milestone",search=True),
        "task_list_id": fields.Many2One("task.list","Task List",search=True),
        "job_id": fields.Many2One("job","Service Order",search=True),
        "contact_id": fields.Many2One("contact","Customer",function="_get_related",function_context={"path":"project_id.contact_id"}),
        "title": fields.Char("Title",required=True,search=True),
        "description": fields.Text("Description",search=True),
        "progress": fields.Integer("Progress (%)"),
        "date_start": fields.Date("Start Date",required=True),
        "date_end": fields.Date("End Date",function="get_end_date",store=True),
        "duration": fields.Integer("Duration (Days)",required=True),
        "due_date": fields.Date("Due Date"),
        "done_date": fields.Date("Completion Date"),
        "resource_id": fields.Many2One("service.resource","Assigned To"),
        "documents": fields.One2Many("document", "related_id", "Documents"),
        "emails": fields.One2Many("email.message", "related_id", "Emails"),
        "comments": fields.Text("Comments"),
        "messages": fields.One2Many("message", "related_id", "Messages"),
        "emails": fields.One2Many("email.message", "related_id", "Emails"),
        "state": fields.Selection([["open","Open"],["closed","Closed"]],"Status",required=True,search=True),
        "depends": fields.One2Many("task.depend","task_id","Task Dependencies"),
        "related_id": fields.Reference([["job","Job"]],"Related To"),
        "depends_json": fields.Text("Task Dependencies (String)",function="get_depends_json"),
    }
    _order = "project_id.number,sequence,id,priority"

    def _get_number(self, context={}):
        seq_id = get_model("sequence").find_sequence(type="task")
        if not seq_id:
            return None
        while 1:
            num = get_model("sequence").get_next_number(seq_id)
            user_id = access.get_active_user()
            access.set_active_user(1)
            res = self.search([["number", "=", num]])
            access.set_active_user(user_id)
            if not res:
                return num
            get_model("sequence").increment_number(seq_id)

    _defaults={
        "date_created": lambda *a: time.strftime("%Y-%m-%d %H:%M:%S"),
        "state": "new",
        "number": _get_number,
    }

    def get_depends_json(self,ids,context={}):
        vals={}
        for obj in self.browse(ids):
            res=[]
            for dep in obj.depends:
                res.append((dep.prev_task_id.id,dep.delay))
            vals[obj.id]=res
        return vals

    def calc_end_date(self,date_start,duration):
        d=datetime.strptime(date_start,"%Y-%m-%d")
        dur=0
        while True:
            if not is_holiday(d):
                dur+=1
            if dur>=duration:
                break
            d+=timedelta(days=1)
        return d.strftime("%Y-%m-%d")

    def update_end(self,context={}):
        data=context.get("data",{})
        date_start=data["date_start"]
        duration=data.get("duration",0)
        if date_start and duration:
            data["date_end"]=self.calc_end_date(date_start,duration)
        return data

    def get_end_date(self,ids,context={}):
        vals={}
        for obj in self.browse(ids):
            if obj.date_start and obj.duration:
                vals[obj.id]=self.calc_end_date(obj.date_start,obj.duration)
        return vals

    def create(self,vals,*args,**kw):
        new_id=super().create(vals,*args,**kw)
        self.function_store([new_id])
        return new_id

    def write(self,ids,*args,**kw):
        super().write(ids,*args,**kw)
        self.function_store(ids)

Task.register()
