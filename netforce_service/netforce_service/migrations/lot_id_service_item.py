from netforce.model import get_model
from netforce import migration
#from netforce.database import get_connection

class Migration(migration.Migration):
    _name="service.item"
    _version="3.1.1"

    def migrate(self):
        for obj in get_model("service.item").search_browse([[]]):
            # skip item that has lot already
            if obj.serial_no and not obj.lot_id:
                lot = get_model("stock.lot").search_browse([["number","=",obj.serial_no]])
                if len(lot)>0:
                    print("Lot Number %s is already exist"%obj.number)
                    obj.write({"lot_id": lot[0].id})
                else:
                    print("Create Lot for %s which serial no is %s"%(obj.number,obj.serial_no))
                    lot_id = get_model("stock.lot").create({"number": obj.serial_no})
                    obj.write({"lot_id": lot_id})

Migration.register()
