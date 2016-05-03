from netforce.model import Model, fields, get_model
from datetime import *
import time

class CreateTaskList(Model):
    _name = "create.task.list"
    _transient = True
    _fields = {
        "template_id": fields.Many2One("task.list.template","Template",required=True),
        "project_id": fields.Many2One("project","Project",required=True),
        "milestone_id": fields.Many2One("project.milestone","Milestone"),
        "sequence": fields.Integer("Base Sequence"),
    }

    def create_task_list(self,ids,context={}):
        obj=self.browse(ids[0])
        template=obj.template_id
        vals={
            "name": template.name,
        }
        list_id=get_model("task.list").create(vals)
        d=date.today()
        for task_tmpl in template.task_templates:
            vals={
                "sequence": (obj.sequence or 0)+(task_tmpl.sequence or 0),
                "project_id": obj.project_id.id,
                "milestone_id": obj.milestone_id.id,
                "task_list_id": list_id,
                "title": task_tmpl.title,
                "description": task_tmpl.description,
                "duration": task_tmpl.duration,
                "date_start": (d+timedelta(days=task_tmpl.start_after or 0)).strftime("%Y-%m-%d"),
            }
            get_model("task").create(vals)
        return {
            "next": {
                "name": "task_list",
                "mode": "form",
                "active_id": list_id,
            }
        }

CreateTaskList.register()
