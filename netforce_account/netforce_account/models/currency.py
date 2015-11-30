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

from netforce.model import Model, fields
from netforce import database
from netforce import ipc
import os
from netforce import access
from decimal import *
import decimal

_cache = {}


def _clear_cache():
    pid = os.getpid()
    print("currency _clear_cache pid=%s" % pid)
    _cache.clear()

ipc.set_signal_handler("clear_currency_cache", _clear_cache)


class Currency(Model):
    _name = "currency"
    _string = "Currency"
    _key = ["name"]
    _name_field = "code"
    _fields = {
        "name": fields.Char("Name", required=True, search=True),
        "code": fields.Char("Code", required=True, search=True),
        "sign": fields.Char("Sign", required=True),
        "rates": fields.One2Many("currency.rate", "currency_id", "Rate History"),
        "sell_rate": fields.Decimal("Current Sell Rate", scale=6, function="get_current_rate", function_multi=True),
        "buy_rate": fields.Decimal("Current Buy Rate", scale=6, function="get_current_rate", function_multi=True),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "product_id": fields.Many2One("product","Product"),
        "account_receivable_id": fields.Many2One("account.account","Account Receivable"),
        "account_payable_id": fields.Many2One("account.account","Account Payable"),
    }

    def create(self, *a, **kw):
        new_id = super().create(*a, **kw)
        ipc.send_signal("clear_currency_cache")
        return new_id

    def write(self, *a, **kw):
        super().write(*a, **kw)
        ipc.send_signal("clear_currency_cache")

    def delete(self, *a, **kw):
        super().delete(*a, **kw)
        ipc.send_signal("clear_currency_cache")

    def get_current_rate(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            if obj.rates:
                vals[obj.id] = {
                    "sell_rate": obj.rates[0].sell_rate,
                    "buy_rate": obj.rates[0].buy_rate,
                }
            else:
                vals[obj.id] = {
                    "sell_rate": None,
                    "buy_rate": None,
                }
        return vals

    def get_rate(self, ids, date=None, rate_type="buy", context={}):
        obj_id = ids[0]
        dbname = database.get_active_db()
        company_id = access.get_active_company()
        key = (dbname, company_id, obj_id, date, rate_type)
        if key in _cache and not context.get("no_cache"):
            return _cache[key]
        obj = self.browse(obj_id)
        res = None
        for rate in obj.rates:
            if rate.company_id.id != company_id:
                continue
            if date and rate.date > date:
                continue
            if rate_type == "buy":
                res = rate.buy_rate
                break
            else:
                res = rate.sell_rate
                break
        if res is None:
            for rate in obj.rates:
                if date and rate.date > date:
                    continue
                if rate_type == "buy":
                    res = rate.buy_rate
                    break
                else:
                    res = rate.sell_rate
                    break
        _cache[key] = res
        return res

    def convert(self, amt, cur_from_id, cur_to_id, from_rate=None, to_rate=None, rate=None, round=False, date=None, rate_type="buy", context={}):
        if cur_from_id == cur_to_id:
            return amt
        if not from_rate and not rate:
            from_rate = self.get_rate([cur_from_id], date=date, rate_type=rate_type, context=context)
        if not to_rate and not rate:
            to_rate = self.get_rate([cur_to_id], date=date, rate_type=rate_type, context=context)
        if not from_rate and not rate:
            print("WARNING: missing rate for currency %s" % cur_from_id)
            from_rate = 0
        if not to_rate and not rate:
            print("WARNING: missing rate for currency %s" % cur_to_id)
            to_rate = 0
        if rate:
            amt2 = amt * rate
        else:
            amt2 = amt * from_rate / Decimal(to_rate) if to_rate else 0
        if round:
            return self.round(cur_to_id, amt2)
        else:
            return amt2

    def round(self, cur_id, amt):
        decimal.getcontext().rounding=ROUND_UP
        return Decimal(amt).quantize(Decimal("0.01"))

Currency.register()
