
from netforce.model import get_model
from netforce.access import set_active_user
from netforce import migration


class Migration(migration.Migration):
    _name="default.report.template"
    _version="3.1.0"

    def migrate(self):
        set_active_user(1)
        ids=get_model("report.template").search([])
        get_model("report.template").write(ids, {'default': False})
        get_model("report.template").get_default_template()


Migration.register()
