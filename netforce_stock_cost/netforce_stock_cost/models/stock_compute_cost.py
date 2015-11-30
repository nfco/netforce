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
from netforce.database import get_connection
import time
from datetime import *
from collections import deque
import heapq
from netforce.utils import print_color

class ComputeCost(Model):
    _name="stock.compute.cost"
    _transient=True

    def compute_cost(self,ids,context={}):
        print_color("COMPUTING COST...","green")
        self.compute_cost_standard(context=context);
        self.compute_cost_fifo(context=context);
        self.compute_cost_avg(context=context);
        self.compute_cost_lifo(context=context);
        get_model("field.cache").clear_cache(model="stock.location")
        return {
            "next": {
                "name": "stock_board",
            },
            "flash": "Inventory cost updated successfully.",
        }

    def compute_cost_standard(self,context={}):
        uoms={}
        for uom in get_model("uom").search_browse([]):
            uoms[uom.id]=uom.ratio
        locations={}
        for loc in get_model("stock.location").search_browse([["type","=","internal"]]):
            locations[loc.id]={}
        db=get_connection()
        print("reading...")
        q="SELECT m.id,m.date,m.product_id,p.cost_method,p.uom_id as prod_uom_id,m.qty,m.uom_id,m.cost_amount,m.location_from_id,m.location_to_id,m.move_id,p.cost_price AS prod_cost_price FROM stock_move m,product p WHERE p.cost_method='standard' AND p.type='stock' AND p.id=m.product_id AND m.state='done'"
        args=[]
        product_ids=context.get("product_ids")
        if product_ids:
            q+=" AND m.product_id IN %s"
            args.append(tuple(product_ids))
        q+=" ORDER BY m.date,m.id"
        res=db.query(q,*args)
        moves=[]
        prod_ids=set([])
        for r in res:
            #print("MOVE date=%s prod=%s from=%s to=%s qty=%s method=%s"%(r.date,r.product_id,r.location_from_id,r.location_to_id,r.qty,r.cost_method))
            loc_from=locations.get(r.location_from_id)
            loc_to=locations.get(r.location_to_id)
            move={
                "id": r.id,
                "qty": r.qty,
                "old_cost_amount": r.cost_amount,
            }
            if loc_from:
                ratio=uoms[r.uom_id]/uoms[r.prod_uom_id]
                move["cost_amount"]=(r.prod_cost_price or 0)*ratio*r.qty
            else:
                move["cost_amount"]=r.cost_amount
            moves.append(move)
            prod_ids.add(r.product_id)
        print("writing...")
        for m in moves:
            if m["cost_amount"]!=m["old_cost_amount"]:
                cost_price=m["cost_amount"]/m["qty"] if m["qty"] and m["cost_amount"] else 0
                db.execute("UPDATE stock_move SET cost_amount=%s,cost_price=%s WHERE id=%s",m["cost_amount"],cost_price,m["id"])
        prod_ids=list(prod_ids)
        if prod_ids:
            db.execute("UPDATE product SET update_balance=true WHERE id IN %s",tuple(prod_ids))

    def compute_cost_avg(self,context={}):
        print("compute_cost_avg")
        uoms={}
        for uom in get_model("uom").search_browse([]):
            uoms[uom.id]=uom.ratio
        locations={}
        for loc in get_model("stock.location").search_browse([["type","=","internal"]]):
            locations[loc.id]={}
        db=get_connection()
        print("reading...")
        q="SELECT m.id,m.date,m.product_id,p.cost_method,p.uom_id as prod_uom_id,m.qty,m.uom_id,m.cost_amount,m.location_from_id,m.location_to_id,m.move_id FROM stock_move m,product p WHERE p.cost_method='average' AND p.type='stock' AND p.id=m.product_id AND m.state='done'"
        args=[]
        product_ids=context.get("product_ids")
        if product_ids:
            q+=" AND m.product_id IN %s"
            args.append(tuple(product_ids))
        q+=" ORDER BY m.date,m.id"
        res=db.query(q,*args)
        prod_moves={}
        for r in res:
            #print("MOVE date=%s prod=%s from=%s to=%s qty=%s method=%s"%(r.date,r.product_id,r.location_from_id,r.location_to_id,r.qty,r.cost_method))
            prod_id=r.product_id
            ratio=uoms[r.uom_id]/uoms[r.prod_uom_id]
            move={
                "id": r.id,
                "date": r.date,
                "qty": r.qty,
                "conv_qty": r.qty*ratio,
                "old_cost_amount": r.cost_amount,
                "cost_amount": r.cost_amount or 0,
                "loc_from_id": r.location_from_id,
                "loc_to_id": r.location_to_id,
            }
            prod_moves.setdefault(prod_id,[]).append(move)
        prod_ids=sorted(prod_moves.keys())
        print("computing...")
        for prod_id in prod_ids:
            print("START prod_id",prod_id)
            for loc in locations.values():
                loc["qty"]=0
                loc["amt"]=0
            moves=prod_moves[prod_id]
            for m in moves:
                loc_from=locations.get(m["loc_from_id"])
                if loc_from:
                    if loc_from["qty"]>=m["conv_qty"]:
                        cost_price=loc_from["amt"]/loc_from["qty"]
                        m["cost_amount"]=round(cost_price*m["conv_qty"],2)
                        loc_from["qty"]-=m["conv_qty"]
                        loc_from["amt"]-=m["cost_amount"]
                    else:
                        m["cost_amount"]=0
                print("[%s] move #%s: %s -> %s, %s @ %s (%s)"%(m["date"],m["id"],m["loc_from_id"],m["loc_to_id"],m["conv_qty"],m["cost_amount"],"calc" if loc_from else "read"))
                loc_to=locations.get(m["loc_to_id"])
                if loc_to:
                    loc_to["qty"]+=m["conv_qty"]
                    loc_to["amt"]+=m["cost_amount"]
        print("writing...")
        for prod_id in prod_ids:
            moves=prod_moves[prod_id]
            for m in moves:
                if m["cost_amount"]!=m["old_cost_amount"]:
                    cost_price=m["cost_amount"]/m["conv_qty"] if m["conv_qty"] else 0
                    db.execute("UPDATE stock_move SET cost_amount=%s, cost_price=%s WHERE id=%s",m["cost_amount"],cost_price,m["id"])
        if prod_ids:
            db.execute("UPDATE product SET update_balance=true WHERE id IN %s",tuple(prod_ids))

    def compute_cost_fifo(self,context={}):
        print("compute_cost_fifo")
        uoms={}
        for uom in get_model("uom").search_browse([]):
            uoms[uom.id]=uom.ratio
        int_locs={}
        for loc in get_model("stock.location").search_browse([["type","=","internal"]]):
            int_locs[loc.id]=True
        db=get_connection()
        print("reading...")
        q="SELECT m.id,m.date,m.product_id,p.cost_method,p.uom_id as prod_uom_id,m.qty,m.uom_id,m.cost_amount,m.location_from_id,m.location_to_id,m.move_id FROM stock_move m,product p WHERE p.cost_method='fifo' AND p.type='stock' AND p.id=m.product_id AND m.state='done'"
        args=[]
        product_ids=context.get("product_ids")
        if product_ids:
            q+=" AND m.product_id IN %s"
            args.append(tuple(product_ids))
        res=db.query(q,*args)
        prod_moves={}
        for r in res:
            print("MOVE date=%s prod=%s from=%s to=%s qty=%s method=%s"%(r.date,r.product_id,r.location_from_id,r.location_to_id,r.qty,r.cost_method))
            prod_id=r.product_id
            ratio=uoms[r.uom_id]/uoms[r.prod_uom_id]
            conv_qty=r.qty*ratio
            move={
                "id": r.id,
                "date": r.date,
                "qty": r.qty,
                "conv_qty": conv_qty,
                "location_from_id": r.location_from_id,
                "location_to_id": r.location_to_id,
                "old_cost_amount": r.cost_amount,
            }
            loc_from=int_locs.get(r.location_from_id)
            if not loc_from: #FIXME
                move["qty_in"]=conv_qty
                unit_price=r.cost_amount/conv_qty if conv_qty else 0
                move["unit_price"]=unit_price
                move["cost"]=conv_qty*unit_price
            else:
                move["qty_in"]=0
                move["unit_price"]=None
                move["cost"]=0
            prod_moves.setdefault(prod_id,[]).append(move)
        prod_ids=sorted(prod_moves.keys())
        print("computing...")
        for prod_id in prod_ids:
            print("START prod_id",prod_id)
            moves=prod_moves[prod_id]
            inputs=[]
            loc_outputs={}
            for m in moves:
                loc_from=int_locs.get(m["location_from_id"])
                loc_to=int_locs.get(m["location_to_id"])
                if loc_to and m["unit_price"]:
                    inputs.append((m["date"],m["id"],m))
                if loc_from:
                    loc_outputs.setdefault(m["location_from_id"],[]).append((m["date"],m["id"],m))
            heapq.heapify(inputs)
            for outputs in loc_outputs.values():
                heapq.heapify(outputs)
            loc_queues={}
            def _print_moves():
                print("=== moves ================================")
                for m in moves:
                    print("id=%(id)s date=%(date)s qty=%(qty)s unit_price=%(unit_price)s loc_from=%(loc_from_id)s loc_to=%(loc_to_id)s qty_in=%(qty_in)s cost=%(cost)s"%m)
            def _get_first_input():
                if not inputs:
                    return None
                return inputs[0][2]
            def _get_first_output(loc_id):
                outputs=loc_outputs.get(loc_id)
                if not outputs:
                    return None
                return outputs[0][2]
            def _transfer_to_loc(qty,price,loc_id):
                q=loc_queues.setdefault(loc_id,deque())
                q.append((qty,price))
                _transfer_to_output(loc_id)
            def _transfer_to_output(loc_id):
                q=loc_queues.get(loc_id)
                while q:
                    m=_get_first_output(loc_id)
                    if not m:
                        break
                    print("OUT %s"%m["id"])
                    qty_remain=m["qty"]-m["qty_in"]
                    (first_qty,first_price)=q[0]
                    if first_qty>qty_remain:
                        use_qty=qty_remain
                        q[0]=(first_qty-use_qty,first_price)
                    else:
                        use_qty=first_qty
                        q.popleft()
                    use_cost=use_qty*first_price
                    m["qty_in"]+=use_qty
                    m["cost"]+=use_cost
                    if m["qty_in"]<=m["qty"]:
                        m["unit_price"]=m["cost"]/m["qty"]
                        outputs=loc_outputs[loc_id]
                        heapq.heappop(outputs)
                        loc_to=int_locs.get(m["location_to_id"])
                        if loc_to:
                            heapq.heappush(inputs,(m["date"],m["id"],m))
            while 1:
                #_print_moves()
                m=_get_first_input()
                if not m:
                    break
                print("IN %s"%m["id"])
                _transfer_to_loc(m["qty_in"],m["unit_price"],m["location_to_id"])
                m["qty_in"]=0
                heapq.heappop(inputs)
            print("DONE prod_id",prod_id)
            #_print_moves()
        print("writing...")
        for prod_id in prod_ids:
            moves=prod_moves[prod_id]
            for m in moves:
                if m["unit_price"] is not None:
                    new_cost_amount=m["unit_price"]*m["conv_qty"]
                else:
                    new_cost_amount=0
                if new_cost_amount!=m["old_cost_amount"]:
                    new_cost_price=new_cost_amount/m["qty"] if m["qty"] else 0
                    db.execute("UPDATE stock_move SET cost_amount=%s, cost_price=%s WHERE id=%s",new_cost_amount,new_cost_price,m["id"])
        if prod_ids:
            db.execute("UPDATE product SET update_balance=true WHERE id IN %s",tuple(prod_ids))

    def compute_cost_lifo(self,context={}):
        print("compute_cost_lifo")
        # XXX: add this

ComputeCost.register()
