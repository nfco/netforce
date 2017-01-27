from netforce.model import Model, fields

class MatchFieldLog(Model):
    _name="match.field.log"
    _fields={
        'match_id': fields.Many2One("match.field","Match", required=True, on_delete="cascade"),
        'sequence': fields.Integer("Line No."),
        'description': fields.Text("Description"),
    }

    _order="sequence"

MatchFieldLog.register()
