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
from datetime import *
import time
from netforce import database
from netforce.utils import get_file_path
from netforce.access import get_active_company, get_active_user, check_permission_other
from netforce.utils import get_data_path


class ProductionOrder(Model):
    _name = "production.order"
    _string = "Production Order"
    _name_field = "number"
    _multi_company = True
    _key = ["company_id", "number"]  # need migration first otherwise can't add constraint...
    _fields = {
        "number": fields.Char("Number", required=True, search=True),
        "ref": fields.Char("Reference", search=True),  # XXX: deprecated
        "order_date": fields.Date("Order Date", required=True, search=True),
        "customer_id": fields.Many2One("contact", "Customer"),
        "due_date": fields.Date("Due Date"),
        "location_id": fields.Many2One("stock.location", "FG Warehouse", required=True, condition=[["type", "=", "internal"]]),
        "product_id": fields.Many2One("product", "Product", required=True, search=True),
        "qty_planned": fields.Decimal("Planned Qty", required=True, scale=6),
        "qty_received": fields.Decimal("Received Qty", function="get_qty_received", function_multi=True, scale=6),
        "qty_received_uos": fields.Decimal("Received Qty (UoS)", function="get_qty_received_uos", scale=6),
        "qty2_received": fields.Decimal("Received Secondary Qty", function="get_qty_received", function_multi=True, scale=6),
        "uom_id": fields.Many2One("uom", "UoM", required=True),
        "bom_id": fields.Many2One("bom", "Bill of Material"),
        "routing_id": fields.Many2One("routing", "Routing"),
        "components": fields.One2Many("production.component", "order_id", "Components"),
        "operations": fields.One2Many("production.operation", "order_id", "Operations"),
        "qc_tests": fields.One2Many("production.qc", "order_id", "QC Tests"),
        "state": fields.Selection([["draft", "Draft"], ["waiting_confirm", "Waiting Confirmation"], ["waiting_suborder", "Waiting Suborder"], ["waiting_material", "Waiting Material"], ["ready", "Ready To Start"], ["in_progress", "In Progress"], ["done", "Completed"], ["voided", "Voided"], ["split", "Split"]], "Status", required=True),
        #"stock_moves": fields.One2Many("stock.move","production_id","Stock Moves"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "documents": fields.One2Many("document", "related_id", "Documents"),
        "pickings": fields.One2Many("stock.picking", "related_id", "Stock Pickings"),
        "sale_id": fields.Many2One("sale.order", "Sales Order", search=True),
        "parent_id": fields.Many2One("production.order", "Parent Production Order", search=True),
        "sub_orders": fields.One2Many("production.order", "parent_id", "Sub Production Orders"),
        "total_qty_received": fields.Decimal("Total Received Qty", function="get_total_qty", function_multi=True, scale=6),
        "total_qty_issued": fields.Decimal("Total Issued Qty", function="get_total_qty", function_multi=True, scale=6),
        "total_qty_diff": fields.Decimal("Qty Loss", function="get_total_qty", function_multi=True, scale=6),
        "total_qty_stock": fields.Decimal("Total Qty in Stock", function="get_total_qty", function_multi=True, scale=6),
        "max_qty_loss": fields.Decimal("Max Qty Loss", function="get_total_qty", function_multi=True, scale=6),
        "production_location_id": fields.Many2One("stock.location", "Production Location", required=True),
        "next_production_location_id": fields.Many2One("stock.location", "Next Production Location", function="get_next_production_location"),
        "overdue": fields.Boolean("Overdue", function="get_overdue", function_search="search_overdue"),
        "team_id": fields.Many2One("mfg.team", "Team", search=True),
        "time_start": fields.DateTime("Start Time", readonly=True),
        "time_stop": fields.DateTime("Finish Time", readonly=True),
        "duration": fields.Decimal("Duration (Hours)", function="get_duration"),
        "done_qty_loss_approved_by_id": fields.Many2One("base.user", "Approved Qty Loss By", readonly=True),
        "done_qc_approved_by_id": fields.Many2One("base.user", "Approved QC By", readonly=True),
        "split_approved_by_id": fields.Many2One("base.user", "Approved By", readonly=True),
        "container_id": fields.Many2One("stock.container", "FG Container"),
        "qty_loss_flag": fields.Boolean("Qty Loss Flag", function="get_qty_flag"),
        "qc_flag": fields.Boolean("QC Approved", function="get_qc_flag"),
        "lot_id": fields.Many2One("stock.lot", "FG Lot"),
        "stock_moves": fields.One2Many("stock.move", "related_id", "Stock Movements"),
        "remark": fields.Text("Remark"),
        "company_id": fields.Many2One("company", "Company"),
        "supplier_id": fields.Many2One("contact", "Supplier"),
        "pickings": fields.Many2Many("stock.picking", "Stock Pickings", function="get_pickings"),
        "invoices": fields.One2Many("account.invoice", "related_id", "Invoices"),
        "emails": fields.One2Many("email.message", "related_id", "Emails"),
        "track_id": fields.Many2One("account.track.categ","Tracking Code"),
        "track_entries": fields.One2Many("account.track.entry",None,"Tracking Entries",function="get_track_entries",function_write="write_track_entries"),
        "track_balance": fields.Decimal("Tracking Balance",function="_get_related",function_context={"path":"track_id.balance"}),
        "total_cost": fields.Float("Total Cost",function="get_total_cost",function_multi=True),
        "unit_cost": fields.Float("Unit Cost",function="get_total_cost",function_multi=True),
        "period_id": fields.Many2One("production.period","Production Period"),
        "sale_lines": fields.One2Many("sale.order.line","production_id","Sales Order Lines"),
    }
    _order = "number"

    def _get_number(self, context={}):
        while 1:
            num = get_model("sequence").get_number("production")
            if not num:
                return None
            res = self.search([["number", "=ilike", num + "%"]])
            if not res:
                return num
            get_model("sequence").increment("production")

    _defaults = {
        "number": _get_number,
        "state": "draft",
        "order_date": lambda *a: time.strftime("%Y-%m-%d"),
        "company_id": lambda *a: get_active_company(),
    }

    def get_qty_flag(self, ids, context={}):
        vals = {}
        flag = False
        for obj in self.browse(ids):
            if obj.state in ["done", "voided", "split"] or obj.done_qty_loss_approved_by_id:
                flag = True
        vals[obj.id] = flag
        return vals

    def get_qc_flag(self, ids, context={}):
        vals = {}
        flag = False
        for obj in self.browse(ids):
            if obj.state in ["done", "voided", "split"] or obj.done_qc_approved_by_id:
                flag = True
        vals[obj.id] = flag
        return vals

    def onchange_product(self, context):
        data = context["data"]
        prod_id = data["product_id"]
        prod = get_model("product").browse(prod_id)
        data["qty_planned"] = 1
        if prod.uom_id:
            data["uom_id"] = prod.uom_id.id
        return data

    def onchange_bom(self, context):
        data = context["data"]
        bom_id = data["bom_id"]
        qty_planned = data["qty_planned"]
        bom = get_model("bom").browse(bom_id)
        ratio = (qty_planned or 0.0) / bom.qty
        data["routing_id"] = bom.routing_id.id
        data["location_id"] = bom.location_id.id
        if bom.routing_id:
            data["production_location_id"]=bom.routing_id.location_id.id
        if not data["uom_id"]:
            data["uom_id"] = bom.uom_id.id
        if data["uom_id"] != bom.uom_id.id:
            prod_order_uom = get_model("uom").browse(data["uom_id"])
            ratio = ratio / prod_order_uom.ratio / bom.uom_id.ratio
        components = []
        for line in bom.lines:
            components.append({
                "product_id": line.product_id.id,
                "qty_planned": round(line.qty * ratio, 2),
                "uom_id": line.uom_id.id,
                "location_id": line.location_id.id,
                "issue_method": line.issue_method,
            })
        data["components"] = components
        routing = bom.routing_id
        if routing:
            ops = []
            for line in routing.lines:
                ops.append({
                    "workcenter_id": line.workcenter_id.id,
                    "planned_duration": (line.duration or 0) * ratio,
                })
            data["operations"] = ops
        return data

    def onchange_routing(self, context):
        data = context["data"]
        bom_id = data["bom_id"]
        qty_planned = data["qty_planned"]
        bom = get_model("bom").browse(bom_id)
        ratio = qty_planned / bom.qty
        routing_id = data["routing_id"]
        routing = get_model("routing").browse(routing_id)
        data["production_location_id"] = routing.location_id.id
        ops = []
        for line in routing.lines:
            ops.append({
                "workcenter_id": line.workcenter_id.id,
                "planned_duration": (line.duration or 0) * ratio,
            })
        data["operations"] = ops
        return data

    def create_components(self, ids, context={}):
        for obj in self.browse(ids):
            bom = obj.bom_id
            if not bom:
                continue
            # TODO: move this to some other function like apply_bom or something like that...
            if bom.container == "sale" and obj.sale_id:
                res = get_model("stock.container").search([["number", "=", obj.sale_id.number]])
                if res:
                    cont_id = res[0]
                else:
                    vals = {
                        "number": obj.sale_id.number,
                    }
                    cont_id = get_model("stock.container").create(vals)
                obj.write({"container_id": cont_id})
            if bom.lot == "production":
                res = get_model("stock.lot").search([["number", "=", obj.number]])
                if res:
                    lot_id = res[0]
                else:
                    vals = {
                        "number": obj.number,
                    }
                    lot_id = get_model("stock.lot").create(vals)
                obj.write({"lot_id": lot_id})
            ratio = obj.qty_planned / bom.qty
            for line in bom.lines:
                vals = {
                    "order_id": obj.id,
                    "product_id": line.product_id.id,
                    "qty_planned": round(line.qty * ratio, 2),
                    "uom_id": line.uom_id.id,
                    "location_id": line.location_id.id,
                    "issue_method": line.issue_method,
                }
                if line.container == "sale" and obj.sale_id:
                    res = get_model("stock.container").search([["number", "=", obj.sale_id.number]])
                    if res:
                        cont_id = res[0]
                    else:
                        cont_vals = {
                            "number": obj.sale_id.number,
                        }
                        cont_id = get_model("stock.container").create(cont_vals)
                    vals["container_id"] = cont_id
                if line.lot == "production":
                    res = get_model("stock.lot").search([["number", "=", obj.number]])
                    if res:
                        lot_id = res[0]
                    else:
                        cont_vals = {
                            "number": obj.number,
                        }
                        lot_id = get_model("stock.lot").create(cont_vals)
                    vals["lot_id"] = lot_id
                get_model("production.component").create(vals)

    def create_operations(self, ids, context={}):
        for obj in self.browse(ids):
            bom = obj.bom_id
            if not bom:
                continue
            ratio = obj.qty_planned / bom.qty
            routing = bom.routing_id
            if not routing:
                continue
            for line in routing.lines:
                vals = {
                    "order_id": obj.id,
                    "workcenter_id": line.workcenter_id.id,
                    "planned_duration": (line.duration or 0) * ratio,
                }
                get_model("production.operation").create(vals)

    def create_qc_tests(self, ids, context={}):
        for obj in self.browse(ids):
            bom = obj.bom_id
            if not bom:
                continue
            for qc_test in bom.qc_tests:
                vals = {
                    "order_id": obj.id,
                    "test_id": qc_test.id,
                    "min_value": qc_test.min_value,
                    "max_value": qc_test.max_value
                }
                get_model("production.qc").create(vals)

    def request_confirm(self, ids, context={}):
        obj = self.browse(ids)[0]
        obj.write({"state": "waiting_confirm"})

    def confirm(self, ids, context={}):
        for obj in self.browse(ids):
            if not obj.due_date:
                raise Exception("Missing due date")
            if not obj.production_location_id:
                raise Exception("Missing production location")
            if obj.sub_orders:
                obj.write({"state": "waiting_suborder"})
                obj.sub_orders.confirm()
            else:
                obj.write({"state": "waiting_material"})
                obj.update_status()
            obj.create_planned_production_moves()

    def ready(self, ids, context={}):
        for obj in self.browse(ids):
            for sub in obj.sub_orders:
                if sub.state in ("waiting_material", "ready", "in_progress"):
                    raise Exception("Sub production order not completed: %s" % sub.number)
            obj.write({"state": "ready"})

    def in_progress(self, ids, context={}):
        for obj in self.browse(ids):
            obj.write({"state": "in_progress"})
            if not obj.time_start:
                t = time.strftime("%Y-%m-%d %H:%M:%S")
                obj.write({"time_start": t})

    def done(self, ids, context={}):
        for obj in self.browse(ids):
            obj.backflush()
            obj.check_qty_loss()
            obj.check_qc()
            t = time.strftime("%Y-%m-%d %H:%M:%S")
            obj.complete_production_moves()
            obj.write({"state": "done", "time_stop": t})
            if obj.parent_id:
                obj.parent_id.update_planned_qtys_from_sub()
                obj.parent_id.update_lot(context={"product_id": obj.product_id.id, "lot_id": obj.lot_id.id})
                obj.parent_id.update_status()

    def check_qty_loss(self, ids, context={}):
        for obj in self.browse(ids):
            if round(obj.total_qty_diff, 2) > round(obj.max_qty_loss or 0.0, 2) and not obj.done_qty_loss_approved_by_id:
                raise Exception("Qty loss is too high, need approval")

    def check_qc(self, ids, context={}):
        for obj in self.browse(ids):
            qc_ok = True
            for test in obj.qc_tests:  # TODO: make this logic configurable in qc.test
                if test.result == "no":
                    qc_ok = False
                elif test.result == "yes":
                    qc_ok = True
                    break
            if not qc_ok and not obj.done_qc_approved_by_id:
                raise Exception("QC not passed, need approval")

    def get_qty_received(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            total_qty = {
                "qty_received": 0,
                "qty2_received": 0,
            }
            for pick in obj.pickings:
                for move in pick.lines:
                    if move.product_id.id != obj.product_id.id or move.state != "done":
                        continue
                    qty = get_model("uom").convert(move.qty, move.uom_id.id, obj.uom_id.id)
                    if move.location_from_id.id != obj.location_id.id and move.location_to_id.id == obj.location_id.id:
                        total_qty["qty_received"] += qty or 0
                        total_qty["qty2_received"] += move.qty2 or 0
                    elif move.location_from_id.id == obj.location_id.id and move.location_to_id.id != obj.location_id.id:
                        total_qty["qty_received"] -= qty or 0
                        total_qty["qty2_received"] -= move.qty2 or 0
            vals[obj.id] = total_qty
        return vals

    def get_qty_received_uos(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            prod = get_model("product").browse(obj.product_id.id)
            if prod and prod["uos_factor"] and prod["uos_factor"] != 0:
                vals[obj.id] = round(obj.qty_received / prod["uos_factor"], 2)
        return vals

    def copy_to_pick_out(self, ids, context={}):
        obj = self.browse(ids)[0]
        if obj.production_location_id.type=="internal":
            pick_type="internal"
        else:
            pick_type="out"
        pick_vals = {
            "type": pick_type,
            "ref": obj.number,
            "related_id": "production.order,%s" % obj.id,
            "lines": [],
        }
        for comp in obj.components:
            qty_remain = comp.qty_planned - comp.qty_issued
            if qty_remain <= 0.001:
                continue
            line_vals = {
                "product_id": comp.product_id.id,
                "qty": qty_remain,
                "uom_id": comp.uom_id.id,
                "location_from_id": comp.location_id.id,
                "location_to_id": obj.production_location_id.id,
                "related_id": "production.order,%s" % obj.id,
            }
            pick_vals["lines"].append(("create", line_vals))
        if not pick_vals["lines"]:
            raise Exception("Nothing remaining to issue")
        pick_id = get_model("stock.picking").create(pick_vals, context={"pick_type": pick_type})
        pick = get_model("stock.picking").browse(pick_id)
        return {
            "next": {
                "name": "pick_internal" if pick_type=="internal" else "pick_out",
                "mode": "form",
                "active_id": pick_id,
            },
            "flash": "Picking %s created from production order %s" % (pick.number, obj.number),
        }

    def copy_to_pick_in(self, ids, context={}):
        obj = self.browse(ids)[0]
        if obj.production_location_id.type=="internal":
            pick_type="internal"
        else:
            pick_type="in"
        pick_vals = {
            "type": pick_type,
            "ref": obj.number,
            "related_id": "production.order,%s" % obj.id,
            "lines": [],
        }
        qty_remain = obj.qty_planned - obj.qty_received
        if qty_remain > 0.001:
            line_vals = {
                "product_id": obj.product_id.id,
                "qty": qty_remain,
                "uom_id": obj.uom_id.id,
                "unit_price": obj.product_id.cost_price,
                "location_from_id": obj.production_location_id.id,
                "location_to_id": obj.location_id.id,
            }
            pick_vals["lines"].append(("create", line_vals))
        for comp in obj.components:
            qty_remain = comp.qty_planned - comp.qty_issued
            if qty_remain >= -0.001:
                continue
            line_vals = {
                "product_id": comp.product_id.id,
                "qty": -qty_remain,
                "uom_id": comp.uom_id.id,
                "location_from_id": obj.production_location_id.id,
                "location_to_id": comp.location_id.id,
            }
            pick_vals["lines"].append(("create", line_vals))
        if not pick_vals["lines"]:
            raise Exception("Nothing remaining to receive")
        pick_id = get_model("stock.picking").create(pick_vals, context={"pick_type": pick_type})
        pick = get_model("stock.picking").browse(pick_id)
        return {
            "next": {
                "name": "pick_internal" if pick_type=="internal" else "pick_in",
                "mode": "form",
                "active_id": pick_id,
            },
            "flash": "Picking %s created from production order %s" % (pick.number, obj.number),
        }

    def get_qty_backflush(self, component=None):
        if component:
            return component.qty_planned - component.qty_issued
        return 0.0

    def backflush(self, ids, context={}):
        res = get_model("stock.location").search([["type", "=", "production"]])
        if not res:
            raise Exception("Production location not found")
        prod_loc_id = res[0]
        for obj in self.browse(ids):
            out_lines = []
            in_lines = []
            for comp in obj.components:
                if comp.issue_method != "backflush":
                    continue
                if not comp.qty_backflush:
                    raise Exception("Please insert backflush qty for %s" % comp.product_id.name)
                # qty_remain=comp.qty_backflush # MTS need to know qty_planned after complete production order
                # qty_remain=comp.qty_planned-comp.qty_issued
                qty_remain = self.get_qty_backflush(comp)
                if qty_remain > 0.001:
                    line_vals = {
                        "product_id": comp.product_id.id,
                        "qty": qty_remain,
                        "uom_id": comp.uom_id.id,
                        "location_from_id": comp.location_id.id,
                        "location_to_id": prod_loc_id,
                        "container_from_id": comp.container_id.id,
                    }
                    out_lines.append(("create", line_vals))
                elif qty_remain < -0.001:
                    line_vals = {
                        "product_id": comp.product_id.id,
                        "qty": -qty_remain,
                        "uom_id": comp.uom_id.id,
                        "location_from_id": prod_loc_id,
                        "location_to_id": comp.location_id.id,
                        "container_from_id": comp.container_id.id,
                    }
                    in_lines.append(("create", line_vals))
            settings = get_model("settings").browse(1)
            if out_lines:
                pick_vals = {
                    "type": "out",
                    "ref": obj.number,
                    "journal_id": settings.pick_out_journal_id.id,
                    "related_id": "production.order,%s" % obj.id,
                    "lines": out_lines,
                }
                pick_id = get_model("stock.picking").create(pick_vals, context={"pick_type": "out"})
                get_model("stock.picking").set_done([pick_id])
            if in_lines:
                pick_vals = {
                    "type": "in",
                    "ref": obj.number,
                    "journal_id": settings.pick_in_journal_id.id,
                    "related_id": "production.order,%s" % obj.id,
                    "lines": in_lines,
                }
                pick_id = get_model("stock.picking").create(pick_vals, context={"pick_type": "in"})
                get_model("stock.picking").set_done([pick_id])

    def void(self, ids, context={}):
        for obj in self.browse(ids):
            move_ids = []
            pick_ids = []
            for move in obj.stock_moves:
                move_ids.append(move.id)
                pick_ids.append(move.picking_id.id)
            # for comp in obj.components:
                # for move in comp.stock_moves:
                # move_ids.append(move.id)
            get_model("stock.picking").write(list(set(pick_ids)), {"state": "voided"})
            get_model("stock.move").write(move_ids, {"state": "voided"})
            obj.write({"state": "voided"})
            if obj.parent_id:
                obj.parent_id.update_status()

    def delete(self, ids, **kw):
        for obj in self.browse(ids):
            move_ids = []
            for move in obj.stock_moves:
                if move.related_id and move.related_id._model == "production.order" and move.related_id.id == obj.id:
                    move_ids.append(move.id)
            get_model("stock.move").delete(move_ids)
        super().delete(ids, **kw)

    def copy(self, ids, context):
        obj = self.browse(ids)[0]
        vals = {
            "due_date": obj.due_date,
            "product_id": obj.product_id.id,
            "qty_planned": obj.qty_planned,
            "uom_id": obj.uom_id.id,
            "bom_id": obj.bom_id.id,
            "routing_id": obj.routing_id.id,
            "location_id": obj.location_id.id,
            "production_location_id": obj.production_location_id.id,
        }
        comps = []
        for comp in obj.components:
            comps.append({
                "product_id": comp.product_id.id,
                "qty_planned": comp.qty_planned,
                "uom_id": comp.uom_id.id,
                "location_id": comp.location_id.id,
                "issue_method": comp.issue_method,
            })
        vals["components"] = [("create", v) for v in comps]
        opers = []
        for oper in obj.operations:
            opers.append({
                "workcenter_id": oper.workcenter_id.id,
                "planned_duration": oper.planned_duration,
            })
        vals["operations"] = [("create", v) for v in opers]
        prod_id = get_model("production.order").create(vals)
        prod = get_model("production.order").browse(prod_id)
        return {
            "next": {
                "name": "production",
                "mode": "form",
                "active_id": prod_id,
            },
            "flash": "Production order %s copied from %s" % (prod.number, obj.number),
        }

    def copy_to_purchase(self, ids, context={}):
        obj = self.browse(ids)[0]
        suppliers = {}
        for line in obj.components:
            prod = line.product_id
            if prod.procure_method != "mto" or prod.supply_method != "purchase":
                continue
            if not prod.suppliers:
                raise Exception("Missing supplier for product '%s'" % prod.name)
            supplier_id = prod.suppliers[0].supplier_id.id
            suppliers.setdefault(supplier_id, []).append((prod.id, line.qty_planned, line.uom_id.id, line.location_id.id))
        if not suppliers:
            raise Exception("No purchase orders to create")
        order_ids = []
        for supplier_id, lines in suppliers.items():
            order_vals = {
                "contact_id": supplier_id,
                "ref": obj.number,
                "lines": [],
            }
            for prod_id, qty, uom_id, location_id in lines:
                prod = get_model("product").browse(prod_id)
                line_vals = {
                    "product_id": prod_id,
                    "description": prod.description or "/",
                    "qty": qty,
                    "uom_id": uom_id,
                    "unit_price": prod.purchase_price or 0,
                    "tax_id": prod.purchase_tax_id.id,
                    "sale_id": obj.sale_id.id,
                    'location_id': location_id,
                }
                order_vals["lines"].append(("create", line_vals))
            order_id = get_model("purchase.order").create(order_vals)
            order_ids.append(order_id)
        orders = get_model("purchase.order").browse(order_ids)
        return {
            "next": {
                "name": "purchase",
                "search_condition": [["ref", "=", obj.number]],
            },
            "flash": "Purchase orders created successfully: " + ", ".join([o.number for o in orders]),
        }

    def get_root_number(self, obj_id, context={}):
        obj = self.browse(obj_id)
        if not obj.parent_id:
            return obj.number
        return self.get_root_number(obj.parent_id.id)

    def get_sub_number(self, num, context={}):
        for i in range(1, 100):
            n = "%s-S%.3d" % (num, i)
            res = self.search([["number", "=", n]])
            if not res:
                return n
        raise Exception("Failed to generate production order number (root=%s)" % num)

    def get_bom_ids(self, **kwargs):
        prod_id = kwargs["product_id"]
        res = get_model("bom").search([["product_id", "=", prod_id]])
        return res

    def copy_to_production(self, ids, context={}):
        obj = self.browse(ids)[0]
        if obj.sub_orders:
            return
        if not obj.due_date:
            raise Exception("Missing due date in production order %s" % obj.number)
        prod = obj.product_id
        d = datetime.strptime(obj.due_date, "%Y-%m-%d") - timedelta(days=prod.mfg_lead_time or 0)
        due_date = d.strftime("%Y-%m-%d")
        order_ids = []
        for line in obj.components:
            prod = line.product_id
            if prod.procure_method != "mto" or prod.supply_method != "production":
                continue
            # MTS need to mapping bom automatic
            # We need to inherit this function
            res = self.get_bom_ids(product_id=prod.id, prod_order_id=obj.id)
            # res=get_model("bom").search([["product_id","=",prod.id]])
            if not res:
                raise Exception("BoM not found for product '%s'" % prod.name)
            bom_id = res[0]  # FIXME
            bom = get_model("bom").browse(bom_id)
            loc_id = bom.location_id.id
            if not loc_id:
                raise Exception("Missing FG location in BoM %s" % bom.number)
            routing = bom.routing_id
            if not routing:
                raise Exception("Missing routing in BoM %s" % bom.number)
            order_vals = {
                "number": self.get_sub_number(self.get_root_number(obj.id)),
                "sale_id": obj.sale_id.id,
                "parent_id": obj.id,
                "product_id": prod.id,
                "qty_planned": line.qty_planned,
                "uom_id": line.uom_id.id,
                "bom_id": bom_id,
                "location_id": loc_id,
                "routing_id": routing.id,
                "production_location_id": routing.location_id.id,
                "due_date": due_date,
                "team_id": obj.team_id.id,
                "state": "waiting_confirm",
                "remark": obj.remark,
            }
            order_id = get_model("production.order").create(order_vals)
            get_model("production.order").create_components([order_id])
            get_model("production.order").create_operations([order_id])
            get_model("production.order").create_qc_tests([order_id])
            order_ids.append(order_id)
        if not order_ids:
            return {
                "flash": "Not production orders to create",
            }
        return {
            "flash": "Production orders created successfully",
            "order_ids": order_ids,
        }

    def copy_to_production_all(self, ids, context={}):
        has_new = False
        new_order_ids = ids
        while new_order_ids:
            new_order_ids2 = []
            for order in get_model("production.order").browse(new_order_ids):
                res = order.copy_to_production()
                if res and res.get("order_ids"):
                    new_order_ids2 += res["order_ids"]
                    has_new = True
            new_order_ids = new_order_ids2
        if has_new:
            self.rename_orders(ids)
        return {
            "flash": "Production orders created successfully",
        }

    def rename_orders(self, ids, context={}):
        obj = self.browse(ids)[0]
        root = obj.number
        n = [1]  # XXX, python oddity...

        def _rename(o):
            for sub in o.sub_orders:
                _rename(sub)
            new_num = "%s-S%.2d" % (root, n[0])
            o.write({"number": new_num})
            if o.lot_id and o.bom_id.lot == "production":
                o.lot_id.write({"number": new_num})  # XXX: check how to do this better...
            n[0] += 1
        _rename(obj)

    def get_total_qty(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            total_in = obj.qty_received
            total_out = 0
            total_qty_stock = 0
            for comp in obj.components:
                if comp.qty_issued > 0:
                    total_out += comp.qty_issued
                else:
                    total_in -= comp.qty_issued
                total_qty_stock += comp.qty_stock
            bom = obj.bom_id
            if bom and bom.max_qty_loss is not None:
                ratio = obj.qty_planned / bom.qty
                max_qty_loss = round(bom.max_qty_loss * ratio, 2)
            else:
                max_qty_loss = None
            vals[obj.id] = {
                "total_qty_received": total_in,
                "total_qty_issued": total_out,
                "total_qty_stock": total_qty_stock,
                "total_qty_diff": total_out - total_in,
                "max_qty_loss": max_qty_loss,
            }
        return vals

    def to_draft(self, ids, context={}):
        obj = self.browse(ids)[0]
        if obj.pickings:
            raise Exception("There are still stock movements for production order %s"%obj.number)
        obj.write({"state": "draft"})

    def get_overdue(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            if obj.due_date:
                vals[obj.id] = obj.due_date < time.strftime(
                    "%Y-%m-%d") and obj.state in ("draft", "waiting_confirm", "waiting_suborder", "waiting_material", "ready", "in_progress")
            else:
                vals[obj.id] = False
        return vals

    def search_overdue(self, clause, context={}):
        return [["due_date", "<", time.strftime("%Y-%m-%d")], ["state", "in", ["draft", "waiting", "ready"]]]

    def get_next_production_location(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            if not obj.parent_id:
                vals[obj.id] = None
            else:
                vals[obj.id] = obj.parent_id.production_location_id.id
        return vals

    def qty_loss_approve_done(self, ids, context={}):
        if not check_permission_other("production_approve_loss_over_max"):
            raise Exception("Permission denied")
        obj = self.browse(ids)[0]
        user_id = get_active_user()
        obj.write({"done_qty_loss_approved_by_id": user_id})
        return {
            "next": {
                "name": "production",
                "mode": "form",
                "active_id": obj.id,
            },
            "flash": "Production order Qty Loss completion approved successfully",
        }

    def qc_approve_done(self, ids, context={}):
        if not check_permission_other("production_approve_qc"):
            raise Exception("Permission denied")
        obj = self.browse(ids)[0]
        user_id = get_active_user()
        obj.write({"done_qc_approved_by_id": user_id})
        return {
            "next": {
                "name": "production",
                "mode": "form",
                "active_id": obj.id,
            },
            "flash": "Production order QC completion approved successfully",
        }

    def disapprove_qty_loss(self, ids, context={}):
        obj = self.browse(ids)[0]
        obj.write({"done_qty_loss_approved_by_id": None})
        return {
            "flash": "Disapprove Qty Loss successfully",
        }

    def disapprove_qc(self, ids, context={}):
        obj = self.browse(ids)[0]
        obj.write({"done_qc_approved_by_id": None})
        return {
            "flash": "Disapprove QC successfully",
        }

    def approve_split(self, ids, context={}):
        if not check_permission_other("production_approve_split"):
            raise Exception("Permission denied")
        obj = self.browse(ids)[0]
        user_id = get_active_user()
        obj.write({"split_approved_by_id": user_id})

    def get_duration(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            if obj.time_start and obj.time_stop:
                t0 = datetime.strptime(obj.time_start, "%Y-%m-%d %H:%M:%S")
                t1 = datetime.strptime(obj.time_stop, "%Y-%m-%d %H:%M:%S")
                vals[obj.id] = (t1 - t0).total_seconds() / 3600.0
            else:
                vals[obj.id] = None
        return vals

    def onchange_planned_qty_line(self, context={}):
        data = context.get('data')
        lines = data['components']
        data['qty_planned'] = 0
        for obj in lines:
            data['qty_planned'] += obj['qty_planned']
        return data

    def update_lot(self, ids, context={}):
        if context["product_id"] and context["lot_id"]:
            for obj in self.browse(ids):
                count = 0
                for comp in obj.components:
                    if comp.product_id.id == context["product_id"]:
                        count += 1
                if count > 1:
                    continue
                for comp in obj.components:
                    if comp.product_id.id == context["product_id"]:
                        comp.write({"lot_id": context["lot_id"]})

    def update_planned_qtys_from_sub(self, ids, context={}):
        print("update_planned_qtys_from_sub", ids)
        obj = self.browse(ids)[0]
        min_ratio = None
        for comp in obj.components:
            found = False
            for sub in obj.sub_orders:
                if sub.product_id.id == comp.product_id.id:
                    found = True
                    break
            if not found:
                continue
            if not comp.qty_planned:
                continue
            if sub.state == "done":
                ratio = (sub.qty_received or 0) / comp.qty_planned
            else:
                ratio = (sub.qty_planned or 0) / comp.qty_planned
            if min_ratio is None or ratio < min_ratio:
                min_ratio = ratio
        if not min_ratio:
            return
        vals = {
            "qty_planned": round(obj.qty_planned * min_ratio, 2),
        }
        obj.write(vals)
        for comp in obj.components:
            vals = {
                "qty_planned": round(comp.qty_planned * min_ratio, 2),
            }
            comp.write(vals)
        for op in obj.operations:
            if not op.planned_duration:
                continue
            vals = {
                "planned_duration": op.planned_duration * min_ratio,
            }
            op.write(vals)
        if obj.parent_id:
            obj.parent_id.update_planned_qtys_from_sub()

    def onchange_qc_test(self, context):
        data = context["data"]
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        test_id = line.get("test_id")
        if not test_id:
            return
        test = get_model("qc.test").browse(test_id)
        line["min_value"] = test.min_value
        line["max_value"] = test.max_value
        return data

    def onchange_qc_value(self, context):
        data = context["data"]
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        try:
            value = float(line.get("value"))
        except:
            return
        min_value = line.get("min_value")
        max_value = line.get("max_value")
        if min_value and value < min_value:
            line["result"] = "no"
        elif max_value and value > max_value:
            line["result"] = "no"
        else:
            line["result"] = "yes"
        return data

    def update_status(self, ids, context={}):
        print("**********************************************************")
        print("production.update_status", ids)
        settings = get_model("settings").browse(1)
        comp_ids = []
        for obj in self.browse(ids):
            if obj.state not in ("waiting_suborder", "waiting_material", "ready"):
                continue
            for comp in obj.components:
                comp_ids.append(comp.id)
        qty_stock = {}
        qty_issued = {}
        for comp in get_model("production.component").browse(comp_ids):  # read function fields in bulk for speed
            qty_stock[comp.id] = comp.qty_stock
            qty_issued[comp.id] = comp.qty_issued
        for obj in self.browse(ids):
            if obj.state not in ("waiting_suborder", "waiting_material", "ready"):
                continue
            new_state = None
            if not new_state:
                for comp in obj.components:
                    if qty_stock[comp.id] - (comp.qty_planned - qty_issued[comp.id]) < -0.001:
                        new_state = "waiting_material"
                        break
            if new_state or settings.production_waiting_suborder:
                for sub in obj.sub_orders:
                    if sub.state in ("draft", "waiting_confirm", "waiting_suborder", "waiting_material", "ready", "in_progress"):
                        new_state = "waiting_suborder"
                        break
            else:
                for sub in obj.sub_orders:
                    if sub.state in ("in_progress"):
                        new_state = "waiting_suborder"
                        break
            if not new_state:
                new_state = "ready"
            if new_state != obj.state:
                obj.write({"state": new_state})

    def create_planned_production_moves(self, ids, context={}):
        print("create_planned_production_moves", ids)
        obj = self.browse(ids[0])
        if obj.production_location_id.type!="internal":
            raise Exception("Invalid production location type")
        res = get_model("stock.location").search([["type", "=", "production"]])
        if not res:
            raise Exception("Location of type 'production' not found")
        prod_loc_id = res[0]
        settings = get_model("settings").browse(1)
        vals = {
            "type": "in",
            "related_id": "production.order,%s" % obj.id,
            "journal_id": settings.pick_in_journal_id.id,
            "date": obj.due_date+" 00:00:00",
            "lines": [("create", {
                "product_id": obj.product_id.id,
                "qty": obj.qty_planned,
                "uom_id": obj.uom_id.id,
                "location_from_id": prod_loc_id,
                "location_to_id": obj.production_location_id.id,
            })],
        }
        in_pick_id = get_model("stock.picking").create(vals, context={"pick_type": "in"})
        get_model("stock.picking").pending([in_pick_id])
        vals = {
            "type": "out",
            "related_id": "production.order,%s" % obj.id,
            "journal_id": settings.pick_out_journal_id.id,
            "date": obj.order_date+" 00:00:00",
            "lines": [],
        }
        for comp in obj.components:
            vals["lines"].append(("create",{
                "product_id": comp.product_id.id,
                "qty": comp.qty_planned,
                "uom_id": comp.uom_id.id,
                "location_from_id": obj.production_location_id.id,
                "location_to_id": prod_loc_id,
            }))
        out_pick_id = get_model("stock.picking").create(vals, context={"pick_type": "out"})
        get_model("stock.picking").pending([out_pick_id])

    def complete_production_moves(self,ids,context={}):
        obj=self.browse(ids[0])
        for pick in obj.pickings:
            if pick.state in ("in","out"):
                pick.set_done()

    def get_pickings(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            pick_ids = []
            for move in obj.stock_moves:
                pick_id = move.picking_id.id
                if pick_id not in pick_ids:
                    pick_ids.append(pick_id)
            vals[obj.id] = pick_ids
        return vals

    def copy_to_invoice(self, ids, context={}):
        id = ids[0]
        obj = self.browse(id)
        contact = obj.supplier_id
        if not contact:
            raise Exception("Missing supplier")
        inv_vals = {
            "type": "in",
            "inv_type": "invoice",
            "ref": obj.number,
            "related_id": "production.order,%s" % obj.id,
            "contact_id": contact.id,
            "lines": [],
        }
        qty=obj.qty_planned
        prod=obj.product_id
        price=prod.purchase_price or 0
        line_vals = {
            "product_id": prod.id,
            "description": prod.description or "/",
            "qty": qty,
            "uom_id": obj.uom_id.id,
            "unit_price": price,
            "account_id": prod and prod.purchase_account_id.id or None,
            "tax_id": prod.purchase_tax_id.id,
            "amount": qty*price,
        }
        inv_vals["lines"].append(("create", line_vals))
        inv_id = get_model("account.invoice").create(inv_vals, {"type": "in", "inv_type": "invoice"})
        inv = get_model("account.invoice").browse(inv_id)
        return {
            "next": {
                "name": "view_invoice",
                "active_id": inv_id,
            },
            "flash": "Invoice %s created from production order %s" % (inv.number, obj.number),
        }

    def get_track_entries(self,ids,context={}):
        vals={}
        for obj in self.browse(ids):
            if not obj.track_id:
                vals[obj.id]=[]
                continue
            res=get_model("account.track.entry").search([["track_id","child_of",obj.track_id.id]])
            vals[obj.id]=res
        return vals

    def write_track_entries(self,ids,field,val,context={}):
        for op in val:
            if op[0]=="create":
                rel_vals=op[1]
                for obj in self.browse(ids):
                    if not obj.track_id:
                        continue
                    rel_vals["track_id"]=obj.track_id.id
                    get_model("account.track.entry").create(rel_vals,context=context)
            elif op[0]=="write":
                rel_ids=op[1]
                rel_vals=op[2]
                get_model("account.track.entry").write(rel_ids,rel_vals,context=context)
            elif op[0]=="delete":
                rel_ids=op[1]
                get_model("account.track.entry").delete(rel_ids,context=context)

    def get_total_cost(self,ids,context={}):
        vals={}
        for obj in self.browse(ids):
            total_amt=0
            for cost in obj.track_entries:
                total_amt-=cost.amount
            vals[obj.id]={
                "total_cost": total_amt,
                "unit_cost": total_amt/obj.qty_received if obj.qty_received else None,
            }
        return vals

ProductionOrder.register()
