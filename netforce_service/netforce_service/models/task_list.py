from netforce.model import Model, fields, get_model, clear_cache
from netforce.database import get_connection
from datetime import *
import time
from netforce import access


class TaskList(Model):
    _name = "task.list"
    _string = "Task List"
    _fields = {
        "name": fields.Char("Name",required=True),
        "date_created": fields.Date("Date Created",required=True),
        "project_id": fields.Many2One("project","Project"),
        "milestone_id": fields.Many2One("project.milestone","Milestone"),
        "tasks": fields.One2Many("task","task_list_id","Tasks"),
    }
    _order = "date_created desc,id desc"
    _defaults ={
        "date_created": lambda *a: time.strftime("%Y-%m-%d"),
    }

TaskList.register()
