from netforce.model import Model, fields
from netforce.access import get_active_user

class ImportField(Model):
    _name="import.field"
    _name_field="string"

    _fields={
        'name': fields.Char("Name", required=True),
        'string': fields.Char("String", required=True),
        'model': fields.Char("Model", required=True),
    }

ImportField.register()
