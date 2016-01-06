from netforce.model import get_model
from netforce import migration
from netforce.database import get_connection

class Migration(migration.Migration):
    _name="stock.stock_cost_amount"
    _version="3.1.0"

    def migrate(self):
        for move in get_model("stock.move").search_browse([["cost_amount","=",None]]):

            cost_price=move.unit_price or 0
            cost_amount=(move.qty or 0)*cost_price
            move.write({"cost_price": cost_price, "cost_amount": cost_amount})

Migration.register()
