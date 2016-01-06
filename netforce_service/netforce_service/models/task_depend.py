from netforce.model import Model, fields, get_model, clear_cache
from netforce.database import get_connection


class TaskDepend(Model):
    _name = "task.depend"
    _string = "Task Dependency"
    _fields = {
        "task_id": fields.Many2One("task","Task",required=True,on_delete="cascade"),
        "prev_task_id": fields.Many2One("task","Previous Task",required=True),
        "delay": fields.Integer("Delay (Days)"),
    }
    _order = "id"

TaskDepend.register()
