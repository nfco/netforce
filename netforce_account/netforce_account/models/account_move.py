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
from netforce.utils import get_data_path, set_data_path, get_file_path
import time
from netforce.access import get_active_company


class Move(Model):
    _name = "account.move"
    _string = "Journal Entry"
    _name_field = "number"
    _multi_company = True
    _audit_log = True
    _key = ["company_id", "number"]
    _fields = {
        "journal_id": fields.Many2One("account.journal", "Journal", required=True, search=True),
        "narration": fields.Text("Narration", required=True, search=True),
        "date": fields.Date("Document Date", required=True, search=True, index=True),
        "date_posted": fields.Date("Posted Date", search=True, index=True),
        "state": fields.Selection([["draft", "Draft"], ["posted", "Posted"], ["voided", "Voided"]], "Status", required=True, search=True),
        "lines": fields.One2Many("account.move.line", "move_id", "Lines"),
        "total_debit": fields.Decimal("Total Debit", function="get_total", function_multi=True),
        "total_credit": fields.Decimal("Total Credit", function="get_total", function_multi=True),
        "type": fields.Selection([["auto", "auto"], ["manual", "Manual"]], "Type"),
        "ref": fields.Char("Reference", search=True),
        "number": fields.Char("Number", search=True, required=True),
        "default_line_desc": fields.Boolean("Default narration to line description"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "related_id": fields.Reference([["account.invoice", "Invoice"], ["account.payment", "Payment"], ["account.transfer", "Transfer"], ["hr.expense", "Expense Claim"], ["service.contract", "Service Contract"], ["pawn.loan", "Loan"], ["landed.cost","Landed Cost"], ["stock.picking","Stock Picking"]], "Related To"),
        "company_id": fields.Many2One("company", "Company"),
        "track_entries": fields.One2Many("account.track.entry","move_id","Tracking Entries"),
        "difference" : fields.Float("Difference",function="get_difference",function_multi=True),
        "verified": fields.Boolean("Verified",search=True),
    }

    def _get_journal(self, context={}):
        settings = get_model("settings").browse(1)
        return settings.general_journal_id.id

    def _get_number(self, context={}):
        journal_id = context.get("journal_id")
        if not journal_id:
            settings = get_model("settings").browse(1)
            journal_id = settings.general_journal_id.id
        if not journal_id:
            return
        journal = get_model("account.journal").browse(journal_id)
        seq_id = journal.sequence_id.id
        if not seq_id:
            return
        while 1:
            num = get_model("sequence").get_next_number(seq_id, context=context)
            res = self.search([["number", "=", num]])
            if not res:
                return num
            get_model("sequence").increment_number(seq_id, context=context)

    _defaults = {
        "state": "draft",
        "default_line_desc": True,
        "type": "auto",
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        "journal_id": _get_journal,
        "number": _get_number,
        "company_id": lambda *a: get_active_company(),
    }
    _order = "date desc,id desc"

    def get_difference(self, ids, context):
        vals = {}
        for obj in self.browse(ids):
            vals[obj.id] = {
                "difference": obj.total_debit-obj.total_credit ,
            }
        return vals

    def create(self, vals, **kw):
        t0 = time.time()
        new_id = super().create(vals, **kw)
        t01 = time.time()
        dt01 = (t01 - t0) * 1000
        print("account_move.dt01", dt01)
        obj = self.browse([new_id])[0]
        line_ids = []
        rec_ids = []
        for line in obj.lines:
            line_ids.append(line.id)
            if line.reconcile_id:
                rec_ids.append(line.reconcile_id.id)
        get_model("account.move.line").function_store(line_ids)
        if rec_ids:
            get_model("account.reconcile").function_store(rec_ids)
        get_model("field.cache").clear_cache(model="account.account")
        t1 = time.time()
        dt = (t1 - t0) * 1000
        print("account_move.create <<< %d ms" % dt)
        return new_id

    def write(self, ids, vals, **kw):
        super().write(ids, vals, **kw)
        line_ids = []
        rec_ids = []
        for obj in self.browse(ids):
            for line in obj.lines:
                line_ids.append(line.id)
                if line.reconcile_id:
                    rec_ids.append(line.reconcile_id.id)
        get_model("account.move.line").function_store(line_ids)
        if rec_ids:
            get_model("account.reconcile").function_store(rec_ids)
        get_model("field.cache").clear_cache(model="account.account")

    def delete(self, ids, **kw):
        rec_ids = []
        for obj in self.browse(ids):
            if obj.state == "posted":
                raise Exception("Can not deleted posted journal entry")
            for line in obj.lines:
                if line.reconcile_id:
                    rec_ids.append(line.reconcile_id.id)
        super().delete(ids, **kw)
        if rec_ids:
            get_model("account.reconcile").function_store(rec_ids)
        get_model("field.cache").clear_cache(model="account.account")

    def post(self, ids, context={}):
        settings = get_model("settings").browse(1)
        for obj in self.browse(ids):
            if settings.lock_date:
                assert obj.date >= settings.lock_date, "Accounting transaction is before lock date"
            if obj.state != "draft":
                raise Exception("Journal entry is not draft")
            total_debit = 0
            total_credit = 0
            for line in obj.lines:
                acc = line.account_id
                if acc.type == "view":
                    raise Exception("Can not post to 'view' account ([%s] %s)" % (acc.code, acc.name))
                if acc.company_id.id!=obj.company_id.id:
                    raise Exception("Wrong company for account %s in journal entry %s (account company: %s, journal entry company %s)("%(acc.code,obj.number,acc.company_id.code,obj.company_id.code))
                if acc.require_contact and not line.contact_id:
                    raise Exception("Missing contact for account %s" % acc.code)
                if acc.require_tax_no and not line.tax_no:
                    raise Exception("Missing tax number for account %s" % acc.code)
                if acc.require_track and not line.track_id:
                    raise Exception("Missing tracking category for account %s" % acc.code)
                if acc.require_track2 and not line.track2_id:
                    raise Exception("Missing secondary tracking category for account %s" % acc.code)
                if line.debit < 0:
                    raise Exception("Debit amount is negative (%s)" % line.debit)
                if line.credit < 0:
                    raise Exception("Credit amount is negative (%s)" % line.credit)
                if line.debit > 0 and line.credit > 0:
                    raise Exception("Debit and credit amounts can not be both non-zero (account: %s, debit: %s, credit: %s)" %
                                    (line.account_id.name_get()[0][1], line.debit, line.credit))
                total_debit += line.debit
                total_credit += line.credit
                if line.tax_comp_id and not line.tax_date:
                    line.write({"tax_date": line.move_id.date})
                if acc.currency_id.id != settings.currency_id.id and line.amount_cur is None:
                    raise Exception("Missing currency amount for account %s" % line.account_id.name_get()[0][1])
                if line.amount_cur is not None and acc.currency_id.id == settings.currency_id.id:
                    raise Exception("Currency amount for account %s should be empty" % line.account_id.name_get()[0][1])
            if abs(total_debit - total_credit) != 0:
                print("NOT BALANCED total_debit=%s total_credit=%s" % (total_debit, total_credit))
                for line in obj.lines:
                    print("  ACC: [%s] %s DR: %s CR: %s" %
                          (line.account_id.code, line.account_id.name, line.debit, line.credit))
                raise Exception("Journal entry is not balanced (debit=%s, credit=%s)" % (total_debit, total_credit))
            obj.write({"state": "posted"})
            if not obj.date_posted:
                date_posted = time.strftime("%Y-%m-%d")
                obj.write({"date_posted": date_posted})
            obj.create_track_entries()
            seq = 1
            for line in obj.lines:
                line.write({"sequence": seq})  # XXX
                seq += 1
        if not context.get("no_reconcile"):
            bank_ids = []
            for obj in self.browse(ids):
                for line in obj.lines:
                    acc = line.account_id
                    if acc.type in ("bank", "cash", "cheque"):
                        bank_ids.append(acc.id)
            if bank_ids:
                bank_ids = list(set(bank_ids))
                get_model("account.account").auto_bank_reconcile(bank_ids)
        get_model("account.balance").update_balances()

    def create_track_entries(self, ids, context={}):
        obj=self.browse(ids[0])
        for line in obj.lines:
            if line.track_id:
                vals={
                    "track_id": line.track_id.id,
                    "amount": line.credit-line.debit,
                    "description": line.description,
                    "move_id": obj.id,
                }
                get_model("account.track.entry").create(vals)
            if line.track2_id:
                vals={
                    "track_id": line.track2_id.id,
                    "amount": line.credit-line.debit,
                    "description": line.description,
                    "move_id": obj.id,
                }
                get_model("account.track.entry").create(vals)

    def void(self, ids, context={}):
        obj = self.browse(ids[0])
        settings = get_model("settings").browse(1)
        if settings.lock_date:
            if obj.date < settings.lock_date:
                raise Exception("Accounting transaction is before lock date")
        obj.lines.unreconcile()
        obj.write({"state": "voided"})
        obj.delete_track_entries()
        get_model("field.cache").clear_cache(model="account.account")
        get_model("account.balance").update_balances()

    def delete_track_entries(self, ids, context={}):
        obj=self.browse(ids[0])
        obj.track_entries.delete()

    def get_total(self, ids, context):
        vals = {}
        for obj in self.browse(ids):
            total_debit = 0
            total_credit = 0
            for line in obj.lines:
                total_debit += line.debit
                total_credit += line.credit
            vals[obj.id] = {
                "total_debit": total_debit,
                "total_credit": total_credit,
            }
        return vals

    def update_amounts(self, context):
        data = context["data"]
        data["total_debit"] = 0
        data["total_credit"] = 0
        for line in data["lines"]:
            if not line:
                continue
            debit = line.get("debit") or 0
            credit = line.get("credit") or 0
            data["total_debit"] += debit
            data["total_credit"] += credit
            if line.get("debit") is not None and line.get("credit") is None:
                line["credit"] = 0
            if line.get("credit") is not None and line.get("debit") is None:
                line["debit"] = 0
        data["difference"]= data["total_debit"]-data["total_credit"]
        return data

    def get_line_desc(self, context):
        data = context["data"]
        path = context["path"]
        if not data.get("default_line_desc"):
            return
        if not get_data_path(data, path):
            set_data_path(data, path, data.get("narration"))
        return data

    def view_journal(self, ids, context={}):
        res = self.read(ids, ["related_id"])[0]["related_id"]
        rel = res and res[0] or None
        next = None
        if rel:
            model, model_id = rel.split(",")
            if model == "account.invoice":
                next = {
                    "name": "view_invoice",
                    "active_id": model_id,
                }
            elif model == "account.payment":
                next = {
                    "name": "payment",
                    "mode": "form",
                    "active_id": model_id,
                }
            elif model == "account.transfer":
                next = {
                    "name": "bank_transfer",
                    "mode": "form",
                    "active_id": model_id,
                }
            elif model == "account.claim":
                next = {
                    "name": "account_claim_edit",
                    "active_id": model_id,
                }
        if not next:
            next = {
                "name": "journal_entry",
                "mode": "form",
                "active_id": ids[0],
            }
        return {"next": next}

    def copy(self, ids, context={}):
        obj = self.browse(ids)[0]
        vals = {
            "journal_id": obj.journal_id.id,
            "ref": obj.ref,
            "default_line_desc": obj.default_line_desc,
            "narration": obj.narration,
            "lines": [],
        }
        for line in obj.lines:
            line_vals = {
                "description": line.description,
                "account_id": line.account_id.id,
                "debit": line.debit,
                "credit": line.credit,
                "tax_comp_id": line.tax_comp_id.id,
                "tax_base": line.tax_base,
                "contact_id": line.contact_id.id,
                "track_id": line.track_id.id,
                "track2_id": line.track2_id.id,
            }
            vals["lines"].append(("create", line_vals))
        new_id = self.create(vals, context={"journal_id": obj.journal_id.id})
        new_obj = self.browse(new_id)
        return {
            "next": {
                "name": "journal_entry",
                "mode": "form",
                "active_id": new_id,
            },
            "flash": "Journal entry %s copied to %s" % (obj.number, new_obj.number),
        }

    def to_draft(self, ids, context={}):
        obj = self.browse(ids)[0]
        for line in obj.lines:
            line.unreconcile()
        obj.write({"state": "draft"})
        obj.delete_track_entries()
        get_model("account.balance").update_balances()
        return {
            "next": {
                "name": "journal_entry",
                "mode": "form",
                "active_id": obj.id,
            },
            "flash": "Journal entry #%d set to draft" % obj.id,
        }

    def onchange_journal(self, context={}):
        data = context["data"]
        journal_id = data["journal_id"]
        date = data["date"]
        number = self._get_number(context={"journal_id": journal_id, "date": date})
        data["number"] = number
        return data

    def onchange_date(self, context={}):
        data = context["data"]
        journal_id = data["journal_id"]
        date = data["date"]
        number = self._get_number(context={"journal_id": journal_id, "date": date})
        data["number"] = number
        return data

    def get_data(self, ids, context={}):
        company_id = get_active_company()
        comp = get_model("company").browse(company_id)
        settings = get_model('settings').browse(1)
        pages = []
        for obj in self.browse(ids):
            lines = []
            for line in obj.lines:
                lines.append({
                    'description': line.description,
                    'account_code': line.account_id.code,
                    'account_name': line.account_id.name,
                    'debit': line.debit,
                    'credit': line.credit,
                    'tax_comp': line.tax_comp_id.name,
                    'tax_base': line.tax_base,
                    'track': line.track_id.name,
                    'contact': line.contact_id.name,
                })
            data = {
                "comp_name": comp.name,
                "number": obj.number,
                "date": obj.date,
                "journal": obj.journal_id.name,
                "narration": obj.narration,
                "lines": lines,
                "total_debit": obj.total_debit,
                "total_credit": obj.total_credit,
            }
            if settings.logo:
                data['logo'] = get_file_path(settings.logo)
            pages.append(data)
        if pages:
            pages[-1]["is_last_page"] = True
        return {
            "pages": pages,
            "logo": get_file_path(settings.logo),  # XXX: remove when render_odt fixed
        }

    def get_report_data(self,ids=None,context={}):
        if ids is not None:  # for new templates
            return super().get_report_data(ids, context=context)
        ids = context["ids"]
        return self.get_data(ids,context)

    def reverse(self, ids, context={}):
        obj = self.browse(ids)[0]
        vals = {
            "journal_id": obj.journal_id.id,
            "ref": obj.ref,
            "default_line_desc": obj.default_line_desc,
            "narration": obj.narration,
            "lines": [],
        }
        for line in obj.lines:
            line_vals = {
                "description": line.description,
                "account_id": line.account_id.id,
                "debit": line.credit,
                "credit": line.debit,
                "tax_comp_id": line.tax_comp_id.id,
                "tax_base": line.tax_base,
                "contact_id": line.contact_id.id,
                "track_id": line.track_id.id,
                "track2_id": line.track2_id.id,
            }
            vals["lines"].append(("create", line_vals))
        new_id = self.create(vals, context={"journal_id": obj.journal_id.id})
        self.post([new_id])
        new_obj = self.browse(new_id)
        return {
            "next": {
                "name": "journal_entry",
                "mode": "form",
                "active_id": new_id,
            },
            "flash": "Journal entry %s reversed to %s" % (obj.number, new_obj.number),
            "reverse_move_id": new_id,
        }

Move.register()
