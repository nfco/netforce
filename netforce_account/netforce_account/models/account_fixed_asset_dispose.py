# Copyright (c) 2012-2015 Netforce Co. Ltd.
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
# OR OTHER DEALINGS IN THE SOFTWARE.

from netforce.model import Model, fields, get_model
import time


class FixedAssetDispose(Model):
    _name = "account.fixed.asset.dispose"
    _fields = {
        "asset_id": fields.Many2One("account.fixed.asset", "Asset", readonly=True),
        "date": fields.Date("Date", required=True),
        "loss_acc_id": fields.Many2One("account.account", "Loss Account", required=True),
        'journal_id': fields.Many2One("account.journal","Journal"),
    }

    def _get_journal(self,context={}):
        res = get_model("account.journal").search([["name", "=", "General"]])
        if res:
            return res[0]

    _defaults = {
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        'journal_id': _get_journal,
    }

    def dispose(self, ids, context={}):
        obj = self.browse(ids)[0]
        if not obj.journal_id:
            raise Exception("General journal not found")
        journal_id = obj.journal_id.id
        asset = obj.asset_id
        desc = "Dispose fixed asset [%s] %s" % (asset.number, asset.name)
        move_vals = {
            "journal_id": journal_id,
            "date": obj.date,
            "narration": desc,
        }
        lines = []
        amt = -asset.price_purchase or 0
        line_vals = {
            "description": desc,
            "account_id": asset.fixed_asset_account_id.id,
            "debit": amt > 0 and amt or 0,
            "credit": amt < 0 and -amt or 0,
        }
        lines.append(line_vals)
        amt = asset.price_purchase - asset.book_val
        line_vals = {
            "description": desc,
            "account_id": asset.accum_dep_account_id.id,
            "debit": amt > 0 and amt or 0,
            "credit": amt < 0 and -amt or 0,
        }
        lines.append(line_vals)
        amt = asset.book_val
        line_vals = {
            "description": desc,
            "account_id": obj.loss_acc_id.id,
            "debit": amt > 0 and amt or 0,
            "credit": amt < 0 and -amt or 0,
        }
        lines.append(line_vals)
        move_vals["lines"] = [("create", v) for v in lines]
        move_id = get_model("account.move").create(move_vals)
        get_model("account.move").post([move_id])
        asset.write({"state": "sold", "date_dispose": obj.date})
        return {
            "next": {
                "name": "fixed_asset",
                "mode": "form",
                "active_id": asset.id,
            }
        }

FixedAssetDispose.register()
