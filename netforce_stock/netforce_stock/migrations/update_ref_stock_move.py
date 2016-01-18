from netforce.model import get_model
from netforce import migration
from netforce.access import set_active_user, set_active_company

class Migration(migration.Migration):
    _name="stock.update.ref.stock.move"
    _version="3.1.1"

    def migrate(self):
        set_active_company(1)
        set_active_user(1)
        total_all=0
        total_found=0
        for move in get_model("stock.move").search_browse([[]]):
            ref=move.ref
            total_all+=1
            if not ref:
                pick=move.picking_id
                move.write({"ref": pick.number})
                total_found+=1
        print("="*80)
        print('updated %s of %s item'%(total_found,total_all))
        print("="*80)

Migration.register()
