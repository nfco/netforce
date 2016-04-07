from netforce.model import get_model
from netforce import migration
#from netforce.database import get_connection

class Migration(migration.Migration):
    _name="service.item"
    _version="3.100.0"

    def migrate(self):
        for obj in get_model("service.item").search_browse([[]]):
            lot = get_model("stock.lot").search_browse([["number","=",obj.serial_no]])
            if len(lot)>0:
                print(obj.number,obj.serial_no,lot[0].number,lot[0].id)
                obj.write({"lot_id": lot[0].id})

Migration.register()
