from netforce.model import get_model
from netforce.access import set_active_company
from netforce import migration

class Migration(migration.Migration):
    _name="account.track.categ"
    _version="3.1.1"

    def migrate(self):
        first_company = get_model("company").search_browse([[]])
        first_company = first_company[0]
        set_active_company(first_company.id)
        setting = get_model("settings").browse(1)
        if setting.currency_id.id:
            for acc_track_categ in get_model("account.track.categ").search_browse([]):
                if not acc_track_categ.currency_id:
                    acc_track_categ.write({"currency_id":setting.currency_id.id})

        #for company in get_model("company").search_browse([]):
            #set_active_company(company.id)
            #setting = get_model("settings").browse(1)
            #if not setting.currency_id.id:
                #continue
            #for acc_track_categ in get_model("account.track.categ").search_browse([]):
                #acc_track_categ.write({"currency_id":setting.currency_id.id})

Migration.register()
