from netforce.model import Model, fields, get_model
from netforce.utils import get_file_path

class MatchFieldLine(Model):
    _name="match.field.line"
    _fields={
        'match_id': fields.Many2One("match.field","Match Field", required=True, on_delete="cascade"),
        'customer_field': fields.Char("Customer Field"),
        'field_id': fields.Many2One("import.field","Netforce Field"),
        'simple_value': fields.Text("Simple Value"), #Depricate
    }


MatchFieldLine.register()
