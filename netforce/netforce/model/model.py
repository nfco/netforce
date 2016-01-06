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

from netforce import database
from netforce import access
from . import fields
import csv
from io import StringIO
import netforce
import os
import shutil
import re
import ast
import time
import psycopg2
import dateutil.parser
import netforce
from lxml import etree
from netforce import utils
from decimal import *

models = {}
browse_cache = {}


def get_model(name):
    dbname = database.get_active_db()
    m = models.get(name)
    if not m:
        raise Exception("Model not found: %s" % name)
    return m


def clear_cache():
    browse_cache.clear()


class ValidationError(Exception):

    def __init__(self, msg, error_fields=None):
        super().__init__(msg)
        self.error_fields = error_fields


class Model(object):
    _name = None
    _string = None
    _fields = None
    _table = None
    _inherit = None
    _defaults = {}
    _order = None
    _key = None
    _name_field = None
    _code_field = None
    _export_field = None
    _image_field = None
    _store = True
    _transient = False
    _context = {}
    _sql_constraints = []
    _constraints = []
    _export_fields = None
    _audit_log = False
    _indexes = []
    _multi_company = False
    _offline = False

    @classmethod
    def register(cls):
        if cls._inherit:
            parent_model = get_model(cls._inherit)
            parent_cls = parent_model.__class__
            model_cls = type(cls._inherit, (cls, parent_cls), {})
            model_cls._fields = parent_cls._fields.copy()
            model_cls._fields.update(cls._fields or {})
            model_cls._defaults = parent_cls._defaults.copy()
            model_cls._defaults.update(cls._defaults)
        else:
            if not cls._name:
                raise Exception("Missing model name in %s" % cls)
            if not cls._table:
                cls._table = cls._name.replace(".", "_")
            model_cls = cls
            cls_fields = {  # XXX
                "create_time": fields.DateTime("Create Time", readonly=True),
                "write_time": fields.DateTime("Write Time", readonly=True),
                "create_uid": fields.Integer("Create UID", readonly=True),
                "write_uid": fields.Integer("Write UID", readonly=True),
            }
            if model_cls._fields:
                cls_fields.update(model_cls._fields)
            model_cls._fields = cls_fields
        model = object.__new__(model_cls)
        models[model_cls._name] = model
        for n, f in model_cls._fields.items():
            f.register(model_cls._name, n)

    def update_db(self):
        db = database.get_connection()
        res = db.get("SELECT * FROM pg_class WHERE relname=%s", self._table)
        if not res:
            db.execute("CREATE TABLE %s (id SERIAL, PRIMARY KEY (id))" % self._table)
        else:
            res = db.query(
                "SELECT * FROM pg_attribute a WHERE attrelid=(SELECT oid FROM pg_class WHERE relname=%s) AND attnum>0 AND attnotnull", self._table)
            for r in res:
                n = r.attname
                if n == "id":
                    continue
                f = self._fields.get(n)
                if f and f.store:
                    continue
                print("  dropping not-null of old column %s.%s" % (self._table, n))
                q = "ALTER TABLE %s ALTER COLUMN \"%s\" DROP NOT NULL" % (self._table, n)
                db.execute(q)

    def update_db_constraints(self):  # XXX: move to update_db
        db = database.get_connection()
        constraints = self._sql_constraints[:]
        # if self._key: # XXX
        #    constraints.append(("key_uniq","unique ("+", ".join([n for n in self._key])+")",""))
        for (con_name, con_def, _) in constraints:
            full_name = "%s_%s" % (self._table, con_name)
            res = db.get(
                "SELECT conname, pg_catalog.pg_get_constraintdef(oid,true) AS condef FROM pg_constraint WHERE conname=%s", full_name)
            if res:
                if con_def == res["condef"].lower():
                    continue
                print("  constraint exists but must be deleted")
                print("    condef_old: %s" % res["condef"].lower())
                print("    condef_new: %s" % con_def)
                db.execute("ALTER TABLE %s DROP CONSTRAINT %s" % (self._table, full_name))
            print("  adding constraint:", self._name, con_name, con_def)
            db.execute("ALTER TABLE %s ADD CONSTRAINT %s %s" % (self._table, full_name, con_def))

    def update_db_indexes(self):
        db = database.get_connection()
        for field_names in self._indexes:
            idx_name = self._table + "_" + "_".join(field_names) + "_idx"
            res = db.get("SELECT * FROM pg_index i,pg_class c WHERE c.oid=i.indexrelid AND c.relname=%s", idx_name)
            if not res:
                print("creating index %s" % idx_name)
                db.execute("CREATE INDEX " + idx_name + " ON " + self._table + " (" + ",".join(field_names) + ")")

    def get_field(self, name):
        if not name in self._fields:
            raise Exception("No such field %s in %s" % (name, self._name))
        return self._fields[name]

    def default_get(self, field_names=None, context={}, load_m2o=True):
        vals = {}
        if field_names is None:
            field_names = self._defaults.keys()
        for n in field_names:
            v = self._defaults.get(n)
            if hasattr(v, "__call__"):
                vals[n] = v(self, context)
            else:
                vals[n] = v
        defaults = context.get("defaults", {})
        for n, v in defaults.items():
            f = self._fields.get(n)
            if not f:  # XXX
                continue
            if v:
                if isinstance(f, fields.Many2One):
                    v = int(v)
            vals[n] = v
        if field_names:
            db = database.get_connection()
            if db:
                user_id = access.get_active_user()
                res = db.query(
                    "SELECT field,value FROM field_default WHERE user_id=%s AND model=%s AND field IN %s", user_id, self._name, tuple(field_names))
                for r in res:
                    n = r.field
                    f = self._fields[n]
                    v = r.value
                    if v:
                        if isinstance(f, fields.Many2One):
                            v = int(v)
                        elif isinstance(f, fields.Float):
                            v = float(v)
                    vals[n] = v
        if load_m2o:
            def _add_name(vals, model):
                for n, v in vals.items():
                    if not v:
                        continue
                    f = model.get_field(n)
                    if isinstance(f, fields.Many2One):
                        mr = get_model(f.relation)
                        name = mr.name_get([v])[0][1]
                        vals[n] = [v, name]
                    elif isinstance(f, fields.One2Many):
                        for v2 in v:
                            _add_name(v2, get_model(f.relation))
            _add_name(vals, self)
        return vals

    def _add_missing_defaults(self, vals, context={}):
        other_fields = [n for n in self._fields if not n in vals or vals[n] is None]
        if not other_fields:
            return vals
        defaults = self.default_get(other_fields, context=context, load_m2o=False)
        for n in other_fields:
            v = defaults.get(n)
            if v is not None:
                vals[n] = v
        return vals

    def _check_key(self, ids, context={}): # TODO: make more efficient
        if not self._key:
            return
        res=self.read(ids,self._key,load_m2o=False,context=context)
        for r in res:
            cond = [(k, "=", r[k]) for k in self._key]
            ids = self.search(cond)
            if len(ids) > 1:
                raise Exception("Duplicate keys: model=%s, %s" % (self._name, ", ".join(["%s='%s'"%(k,r[k]) for k in self._key])))

    def create(self, vals, context={}):
        if not access.check_permission(self._name, "create"):
            raise Exception("Permission denied (create %s, user_id=%s)" % (self._name, access.get_active_user()))
        vals = self._add_missing_defaults(vals, context=context)
        for n, v in list(vals.items()):
            f = self._fields[n]
            if isinstance(f, fields.Char):
                if f.password and v:
                    vals[n] = utils.encrypt_password(v)
            elif isinstance(f, fields.Json):
                if not isinstance(v, str):
                    vals[n] = utils.json_dumps(v)
        if not vals.get("create_time"):
            vals["create_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if not vals.get("create_uid"):
            vals["create_uid"] = access.get_active_user()
        store_fields = [n for n in vals if self._fields[n].store]
        cols = store_fields[:]
        q = "INSERT INTO " + self._table
        q += " (" + ",".join(['"%s"' % col for col in cols]) + ")"
        q += " VALUES (" + ",".join(["%s" for col in cols]) + ") RETURNING id"
        args = [vals[n] for n in store_fields]
        db = database.get_connection()
        res = db.get(q, *args)
        new_id = res.id
        locale = netforce.locale.get_active_locale()
        if locale and locale != "en_US":  # XXX
            trans_fields = [n for n in store_fields if self._fields[n].translate]
            for n in trans_fields:
                val = vals[n]
                db.execute("INSERT INTO translation_field (lang,model,field,rec_id,translation) VALUES (%s,%s,%s,%s,%s)",
                           locale, self._name, n, new_id, val)
        multico_fields = [n for n in store_fields if self._fields[n].multi_company]
        if multico_fields:
            company_id = access.get_active_company()
            for n in multico_fields:
                val = vals[n]
                if val is not None:
                    f = self._fields[n]
                    if isinstance(f, fields.Many2One):
                        val = str(val)
                    elif isinstance(f, fields.Float):
                        val = str(val)
                    elif isinstance(f, fields.Char):
                        pass
                    elif isinstance(f, fields.File):
                        pass
                    else:
                        raise Exception("Multicompany field not yet implemented: %s" % n)
                db.execute("INSERT INTO field_value (company_id,model,field,record_id,value) VALUES (%s,%s,%s,%s,%s)",
                           company_id, self._name, n, new_id, val)
        for n in vals:
            f = self._fields[n]
            if isinstance(f, fields.One2Many):
                mr = get_model(f.relation)
                ops = vals[n]
                for op in ops:
                    if op[0] == "create":
                        vals_ = op[1]
                        rf = mr.get_field(f.relfield)
                        if isinstance(rf, fields.Many2One):
                            vals_[f.relfield] = new_id
                        elif isinstance(rf, fields.Reference):
                            vals_[f.relfield] = "%s,%d" % (self._name, new_id)
                        else:
                            raise Exception("Invalid relfield: %s" % f.relfield)
                        if f.multi_company:
                            vals_["company_id"] = access.get_active_company()
                        mr.create(vals_, context=context)
                    elif op[0] == "add":
                        mr.write(op[1], {f.relfield: new_id})
                    elif op[0] in ("delete", "delete_all"):
                        pass
                    else:
                        raise Exception("Invalid operation: %s" % op[0])
            elif isinstance(f, fields.Many2Many):
                mr = get_model(f.relation)
                ops = vals[n]
                for op in ops:
                    if op[0] in ("set", "add"):
                        ids_ = op[1]
                        for id in ids_:
                            db.execute("INSERT INTO %s (%s,%s) VALUES (%%s,%%s)" %
                                       (f.reltable, f.relfield, f.relfield_other), new_id, id)
                    else:
                        raise Exception("Invalid operation: %s" % op[0])
        self._check_key([new_id])
        self._check_constraints([new_id])
        self._changed([new_id], vals.keys())
        self.audit_log("create", {"id": new_id, "vals": vals})
        self.trigger([new_id], "create")
        return new_id

    def _expand_condition(self, condition, context={}):
        new_condition = []
        for clause in condition:
            if clause in ("or", "and"):
                new_clause = clause
            else:
                if len(clause) > 1 and isinstance(clause[0], str) and clause[0] not in ("or", "and"):
                    new_clause = clause
                    n = clause[0]
                    if n.find(".") == -1:
                        f = self._fields.get(n)
                        if f and f.function_search:
                            ctx = f.function_context or {}
                            ctx.update(context)
                            f = getattr(self, f.function_search)
                            new_clause = f(clause, ctx)
                else:
                    new_clause = self._expand_condition(clause, context=context)
            new_condition.append(new_clause)
        return new_condition

    def _where_calc(self, condition, context={}, tbl_count=1):
        # print("_where_calc",condition)
        condition = self._expand_condition(condition, context=context)
        # print("exp_condition",condition)
        joins = []
        args = []

        def _where_calc_r(cond):
            nonlocal args, tbl_count, joins
            cond_list = []
            and_list = []
            if len(cond) >= 1 and cond[0] in ("or", "and"):
                mode = cond[0]
                cond = cond[1:]
            else:
                mode = "and"
            for clause in cond:
                if len(clause) >= 1 and isinstance(clause[0], str) and clause[0] not in ("or", "and"):
                    field, op, val = clause
                    fnames = field.split(".")
                    m = self
                    col_tbl = "tbl0"
                    for fname in fnames[:-1]:
                        f = m.get_field(fname)
                        mr = get_model(f.relation)
                        rtbl = "tbl%d" % tbl_count
                        tbl_count += 1
                        if isinstance(f, fields.Many2One):
                            joins.append("LEFT JOIN %s %s ON %s.id=%s.%s" % (mr._table, rtbl, rtbl, col_tbl, fname))
                        elif isinstance(f, fields.One2Many):
                            joins.append("JOIN %s %s ON %s.id=%s.%s" % (mr._table, rtbl, col_tbl, rtbl, f.relfield))
                        elif isinstance(f, fields.Many2Many):
                            joins.append("JOIN %s %s ON EXISTS (SELECT * FROM %s WHERE %s=%s.id AND %s=%s.id)" %
                                         (mr._table, rtbl, f.reltable, f.relfield, col_tbl, f.relfield_other, rtbl))
                        else:
                            raise Exception("Invalid search condition: %s" % condition)
                        m = mr
                        col_tbl = rtbl
                    end_field = fnames[-1]
                    if end_field != "id":
                        f = m.get_field(end_field)
                        if isinstance(f, fields.Many2One):
                            m = get_model(f.relation)
                        elif isinstance(f, fields.One2Many):
                            mr = get_model(f.relation)
                            rtbl = "tbl%d" % tbl_count
                            tbl_count += 1
                            joins.append("JOIN %s %s ON %s.id=%s.%s" % (mr._table, rtbl, col_tbl, rtbl, f.relfield))
                            m = mr
                            col_tbl = rtbl
                            end_field = "id"
                        elif isinstance(f, fields.Many2Many):
                            mr = get_model(f.relation)
                            rtbl = "tbl%d" % tbl_count
                            tbl_count += 1
                            joins.append("JOIN %s %s ON EXISTS (SELECT * FROM %s WHERE %s=%s.id AND %s=%s.id)" %
                                         (mr._table, rtbl, f.reltable, f.relfield, col_tbl, f.relfield_other, rtbl))
                            m = mr
                            col_tbl = rtbl
                            end_field = "id"
                    col = col_tbl + "." + end_field
                    if op == "=" and val is None:
                        cond_list.append("%s IS NULL" % col)
                    elif op == "!=" and val is None:
                        cond_list.append("%s IS NOT NULL" % col)
                    else:
                        if op in ("=", "!=", "<", ">", "<=", ">="):
                            cond_list.append("%s %s %%s" % (col, op))
                            args.append(val)
                        elif op in ("in", "not in"):
                            if val:
                                cond_list.append(col + " " + op + " (" + ",".join(["%s"] * len(val)) + ")")
                                args += val
                            else:
                                if op == "in":
                                    cond_list.append("false")
                                elif op == "not in":
                                    cond_list.append("true")
                        elif op in ("like", "ilike"):
                            cond_list.append("%s %s %%s" % (col, op))
                            args.append("%" + val + "%")
                        elif op in ("=like", "=ilike"):
                            cond_list.append("%s %s %%s" % (col, op[1:]))
                            args.append(val)
                        elif op == "child_of":
                            if isinstance(val, str):  # XXX
                                cond_list.append("%s IN (WITH RECURSIVE q AS (SELECT id FROM %s WHERE %s=%%s UNION ALL SELECT h.id FROM q JOIN %s h ON h.parent_id=q.id) SELECT id FROM q)" % (
                                    col, m._table, m._name_field or "name", m._table))
                                args.append(val)
                            else:
                                if isinstance(val, int):
                                    val = [val]
                                if val:
                                    cond_list.append("%s IN (WITH RECURSIVE q AS (SELECT id FROM %s WHERE id IN %%s UNION ALL SELECT h.id FROM q JOIN %s h ON h.parent_id=q.id) SELECT id FROM q)" % (
                                        col, m._table, m._table))
                                    args.append(tuple(val))
                                else:
                                    cond_list.append("FALSE")
                        elif op == "not child_of":
                            if isinstance(val, str):  # XXX
                                cond_list.append("%s NOT IN (WITH RECURSIVE q AS (SELECT id FROM %s WHERE %s=%%s UNION ALL SELECT h.id FROM q JOIN %s h ON h.parent_id=q.id) SELECT id FROM q)" % (
                                    col, m._table, m._name_field or "name", m._table))
                                args.append(val)
                            else:
                                if isinstance(val, int):
                                    val = [val]
                                if val:
                                    cond_list.append("%s NOT IN (WITH RECURSIVE q AS (SELECT id FROM %s WHERE id IN %%s UNION ALL SELECT h.id FROM q JOIN %s h ON h.parent_id=q.id) SELECT id FROM q)" % (
                                        col, m._table, m._table))
                                    args.append(tuple(val))
                                else:
                                    cond_list.append("TRUE")
                        elif op == "child_of<":
                            cond_list.append("%s IN (WITH RECURSIVE q AS (SELECT id FROM %s WHERE id=%%s UNION ALL SELECT h.id FROM q JOIN %s h ON h.parent_id=q.id) SELECT id FROM q WHERE id!=%%s)" % (
                                col, m._table, m._table))
                            args += [val, val]
                        elif op == "parent_of":
                            if isinstance(val, int):
                                val = [val]
                            if val:
                                cond_list.append("%s IN (WITH RECURSIVE q AS (SELECT id,parent_id FROM %s WHERE id IN %%s UNION ALL SELECT h.id,h.parent_id FROM q JOIN %s h ON h.id=q.parent_id) SELECT id FROM q)" % (
                                    col, m._table, m._table))
                                args.append(tuple(val))
                            else:
                                cond_list.append("FALSE")
                        else:
                            raise Exception("Invalid condition operator: %s" % op)
                else:
                    cond = _where_calc_r(clause)
                    cond_list.append(cond)
            if mode == "and":
                cond = " AND ".join(cond_list) if cond_list else "true"
            elif mode == "or":
                cond = "(" + (" OR ".join(cond_list) if cond_list else "false") + ")"
            if and_list:
                cond += " AND " + " AND ".join(and_list)
            return cond
        cond = _where_calc_r(condition)
        # print("=>",joins,cond,args)
        return [joins, cond, args]

    def _order_calc(self, order):
        joins = []
        clauses = []
        tbl_count = 1
        if order:
            for comp in order.split(","):
                comp = comp.strip()
                res = comp.split(" ")
                if len(res) > 1:
                    odir = res[1]
                else:
                    odir = "ASC"
                path = res[0]
                m = self
                tbl = "tbl0"

                def _add_join(col):
                    f = m._fields[col]
                    if isinstance(f, fields.Many2One):
                        mr = get_model(f.relation)
                        rtbl = "otbl%d" % tbl_count
                        tbl_count += 1
                        joins.append("LEFT JOIN %s %s ON %s.id=%s.%s" % (mr._table, rtbl, rtbl, tbl, col))
                        m = mr
                        tbl = rtbl
                    else:
                        raise Exception("Invalid field %s in order clause %s" % (col, comp))
                cols = path.split(".")
                for col in cols[:-1]:
                    f = m.get_field(col)
                    mr = get_model(f.relation)
                    rtbl = "otbl%d" % tbl_count
                    tbl_count += 1
                    joins.append("LEFT JOIN %s %s ON %s.id=%s.%s" % (mr._table, rtbl, rtbl, tbl, col))
                    m = mr
                    tbl = rtbl
                col = cols[-1]
                f = m._fields.get(col)
                if f and not f.store and not f.sql_function:
                    path = f.function_context.get("path")  # XXX
                    if not path:
                        raise Exception("Invalid field %s in order clause %s" % (col, comp))
                    cols = path.split(".")
                    for col in cols[:-1]:
                        f = m.get_field(col)
                        mr = get_model(f.relation)
                        rtbl = "otbl%d" % tbl_count
                        tbl_count += 1
                        joins.append("LEFT JOIN %s %s ON %s.id=%s.%s" % (mr._table, rtbl, rtbl, tbl, col))
                        m = mr
                        tbl = rtbl
                    col = cols[-1]
                    f = m._fields.get(col)
                if isinstance(f, fields.Many2One):
                    mr = get_model(f.relation)
                    rtbl = "otbl%d" % tbl_count
                    tbl_count += 1
                    joins.append("LEFT JOIN %s %s ON %s.id=%s.%s" % (mr._table, rtbl, rtbl, tbl, col))
                    m = mr
                    tbl = rtbl
                    col = m._name_field or "name"
                if f and f.sql_function:  # XXX
                    clause = "\"%s\" %s" % (path, odir)
                else:
                    clause = "%s.%s %s" % (tbl, col, odir)
                clauses.append(clause)
        #print("_order_calc(%s: %s) -> %s %s"%(self._name,order,joins,clauses))
        return (joins, clauses)

    def _check_condition_has_active(self, condition):
        def _check_r(cond):
            #print("XXX _check_r",cond)
            for clause in cond:
                if not isinstance(clause, (tuple, list)):
                    continue  # XXX: [["id","in",[1,2,3]]]
                if len(clause) >= 1 and isinstance(clause[0], str) and clause[0] not in ("or", "and"):
                    if clause[0] == "active":
                        return True
                else:
                    if _check_r(clause):
                        return True
            return False
        return _check_r(condition)

    def search(self, condition, order=None, limit=None, offset=None, count=False, child_condition=None, context={}):
        #print(">>> SEARCH",self._name,condition)
        if child_condition:
            child_ids = self.search(child_condition, context=context)
            res = self.search([condition, ["id", "parent_of", child_ids]], order=order,
                              limit=limit, offset=offset, count=count, context=context)
            return res
        cond = [condition]
        if "active" in self._fields and context.get("active_test") != False:
            if not self._check_condition_has_active(condition):
                cond.append(["active", "=", True])
        share_condition = access.get_filter(self._name, "read")
        if share_condition:
            cond.append(share_condition)
        joins, cond, w_args = self._where_calc(cond, context=context)
        args=w_args[:]
        ord_joins, ord_clauses = self._order_calc(order or self._order or "id")
        # print("CONDITION:",cond)
        q = "SELECT tbl0.id FROM " + self._table + " tbl0"
        if joins:
            q += " " + " ".join(joins)
        if ord_joins:
            q += " " + " ".join(ord_joins)
        if cond:
            q += " WHERE (" + cond + ")"
        if ord_clauses:
            q += " ORDER BY " + ",".join(ord_clauses)
        if offset is not None:
            q += " OFFSET %s"
            args.append(offset)
        if limit is not None:
            q += " LIMIT %s"
            args.append(limit)
        db = database.get_connection()
        res = db.query(q, *args)
        ids = utils.rmdup([r.id for r in res])
        if not count:
            return ids
        q = "SELECT COUNT(*) AS total FROM " + self._table + " tbl0"
        if joins:
            q += " " + " ".join(joins)
        if cond:
            q += " WHERE " + cond
        res = db.get(q, *w_args)
        #print("<<< SEARCH",self._name,condition)
        return (ids, res.total)

    def write(self, ids, vals, check_time=False, context={}):
        #print(">>> WRITE",self._name,ids,vals)
        if not access.check_permission(self._name, "write", ids):
            raise Exception("Permission denied (write %s)" % self._name)
        if not ids or not vals:
            return
        if not vals.get("write_time"):
            vals["write_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if not vals.get("write_uid"):
            vals["write_uid"] = access.get_active_user()
        for n, v in list(vals.items()):
            f = self._fields[n]
            if isinstance(f, fields.Json):
                if not isinstance(v, str):
                    vals[n] = utils.json_dumps(v)  # XXX
            elif isinstance(f, fields.Char):
                if f.password and v:
                    vals[n] = utils.encrypt_password(v)
        db = database.get_connection()
        if check_time:
            q = "SELECT MAX(write_time) AS write_time FROM " + self._table + \
                " WHERE id IN (" + ",".join([str(int(id)) for id in ids]) + ")"

            res = db.get(q)
            write_time = res.write_time
            if write_time and write_time > check_time:  # TODO: check == case
                raise Exception("Failed to write record (concurrent access), please reload the page.")
        store_fields = [n for n in vals if self._fields[n].store]
        locale = netforce.locale.get_active_locale()
        if locale and locale != "en_US":  # XXX
            trans_fields = [n for n in store_fields if self._fields[n].translate]
            store_fields = list(set(store_fields) - set(trans_fields))
        else:
            trans_fields = []
        multico_fields = [n for n in store_fields if self._fields[n].multi_company]
        if multico_fields:
            store_fields = list(set(store_fields) - set(multico_fields))
        cols = store_fields[:]
        if cols:
            q = "UPDATE " + self._table
            q += " SET " + ",".join(['"%s"=%%s' % col for col in cols])
            q += " WHERE id IN (" + ",".join([str(int(id)) for id in ids]) + ")"
            args = [vals[n] for n in store_fields]
            db.execute(q, *args)
        if trans_fields:
            res = db.query("SELECT id,field,rec_id FROM translation_field WHERE lang=%s AND model=%s AND field IN %s AND rec_id in %s",
                           locale, self._name, tuple(trans_fields), tuple(ids))
            trans_ids = {}
            rec_ids = {}
            for r in res:
                trans_ids.setdefault(r.field, []).append(r.id)
                rec_ids.setdefault(r.field, []).append(r.rec_id)
            for n in trans_fields:
                val = vals[n]
                ids2 = trans_ids.get(n)
                if ids2:
                    db.execute("UPDATE translation_field SET translation=%s WHERE id in %s", val, tuple(ids2))
                ids3 = rec_ids.get(n, [])
                ids4 = list(set(ids) - set(ids3))
                for rec_id in ids4:
                    db.execute(
                        "INSERT INTO translation_field (lang,model,field,rec_id,translation) VALUES (%s,%s,%s,%s,%s)", locale, self._name, n, rec_id, val)
        if multico_fields:
            company_id = access.get_active_company()
            res = db.query("SELECT id,field,record_id FROM field_value WHERE company_id=%s AND model=%s AND field IN %s AND record_id in %s",
                           company_id, self._name, tuple(multico_fields), tuple(ids))
            val_ids = {}
            rec_ids = {}
            for r in res:
                val_ids.setdefault(r.field, []).append(r.id)
                rec_ids.setdefault(r.field, []).append(r.record_id)
            for n in multico_fields:
                val = vals[n]
                if val is not None:
                    f = self._fields[n]
                    if isinstance(f, fields.Many2One):
                        val = str(val)
                    elif isinstance(f, fields.Float):
                        val = str(val)
                    elif isinstance(f, fields.Char):
                        pass
                    elif isinstance(f, fields.File):
                        pass
                    else:
                        raise Exception("Multicompany field not yet implemented: %s" % n)
                ids2 = val_ids.get(n)
                if ids2:
                    db.execute("UPDATE field_value SET value=%s WHERE id in %s", val, tuple(ids2))
                ids3 = rec_ids.get(n, [])
                ids4 = list(set(ids) - set(ids3))
                for rec_id in ids4:
                    db.execute("INSERT INTO field_value (company_id,model,field,record_id,value) VALUES (%s,%s,%s,%s,%s)",
                               company_id, self._name, n, rec_id, val)
        for n in vals:
            f = self._fields[n]
            if f.function_write:
                continue
            if isinstance(f, fields.One2Many):
                mr = get_model(f.relation)
                rf = mr.get_field(f.relfield)
                ops = vals[n]
                for op in ops:
                    if op[0] == "create":
                        vals_ = op[1]
                        for id in ids:
                            if isinstance(rf, fields.Many2One):
                                vals_[f.relfield] = id
                            elif isinstance(rf, fields.Reference):
                                vals_[f.relfield] = "%s,%d" % (self._name, id)
                            else:
                                raise Exception("Invalid relfield: %s" % f.relfield)
                            if f.multi_company:
                                vals_["company_id"] = access.get_active_company()
                            mr.create(op[1])
                    elif op[0] == "write":
                        mr.write(op[1], op[2])
                    elif op[0] == "delete":
                        mr.delete(op[1])
                    elif op[0] == "delete_all":
                        if isinstance(rf, fields.Many2One):
                            ids2 = mr.search([[f.relfield, "in", ids]])
                        elif isinstance(rf, fields.Reference):
                            rel_ids = ["%s,%d" % (self._name, id) for id in ids]
                            ids2 = mr.search([[f.relfield, "in", rel_ids]])
                        else:
                            raise Exception("Invalid relfield: %s" % f.relfield)
                        mr.delete(ids2)
                    elif op[0] == "add":
                        mr.write(op[1], {f.relfield: ids[0]})
                    elif op[0] == "remove":
                        mr.write(op[1], {f.relfield: None})
                    else:
                        raise Exception("Invalid operation: %s" % op[0])
            elif isinstance(f, fields.Many2Many):
                mr = get_model(f.relation)
                ops = vals[n]
                for op in ops:
                    if op[0] == "add":
                        ids_ = op[1]
                        for id1 in ids:
                            for id2 in ids_:
                                db.execute("INSERT INTO %s (%s,%s) VALUES (%%s,%%s)" %
                                           (f.reltable, f.relfield, f.relfield_other), id1, id2)
                    elif op[0] == "remove":
                        ids_ = op[1]
                        db.execute("DELETE FROM %s WHERE %s IN (%s) AND %s IN (%s)" % (
                            f.reltable, f.relfield, ",".join([str(int(x)) for x in ids]), f.relfield_other, ",".join([str(int(x)) for x in ids_])))
                    elif op[0] == "set":
                        ids_ = op[1]
                        db.execute("DELETE FROM %s WHERE %s IN (%s)" %
                                   (f.reltable, f.relfield, ",".join([str(int(x)) for x in ids])))
                        for id1 in ids:
                            for id2 in ids_:
                                db.execute("INSERT INTO %s (%s,%s) VALUES (%%s,%%s)" %
                                           (f.reltable, f.relfield, f.relfield_other), id1, id2)
        for n in vals:
            f = self._fields[n]
            if not f.function_write:
                continue
            func = getattr(self, f.function_write)
            func(ids, n, vals[n], context=context)
        self._check_key(ids)
        self._check_constraints(ids)
        self._changed(ids, vals.keys())
        self.audit_log("write", {"ids": ids, "vals": vals})
        self.trigger(ids, "write")

    def delete(self, ids, context={}):
        if not access.check_permission(self._name, "delete", ids):
            raise Exception("Permission denied (delete %s)" % self._name)
        if not ids:
            return
        self.trigger(ids, "delete")
        q = "DELETE FROM " + self._table + " WHERE id IN (" + ",".join([str(int(id)) for id in ids]) + ")"
        db = database.get_connection()
        try:
            db.execute(q)
        except psycopg2.Error as e:
            code = e.pgcode
            if code == "23502":
                raise Exception(
                    "Can't delete item because it is still being referenced (model=%s, ids=%s)" % (self._name, ids))
        self.audit_log("delete", {"ids": ids})

    def read(self, ids, field_names=None, load_m2o=True, get_time=False, context={}):
        #print(">>> READ",self._name,ids,field_names)
        if not access.check_permission(self._name, "read", ids):
            raise Exception("Permission denied (read %s, ids=%s)" % (self._name, ",".join([str(x) for x in ids])))
        #print("read perm ok")
        if not ids:
            #print("<<< READ",self._name)
            return []
        if not field_names:
            field_names = [n for n, f in self._fields.items() if not isinstance(
                f, (fields.One2Many, fields.Many2Many)) and not (not f.store and not f.function)]
        field_names = list(set(field_names))  # XXX
        cols = ["id"] + [n for n in field_names if self.get_field(n).store]
        q = "SELECT " + ",".join(['"%s"' % col for col in cols]) + " FROM " + self._table
        q += " WHERE id IN (" + ",".join([str(int(id)) for id in ids]) + ")"
        db = database.get_connection()
        res = db.query(q)
        id_res = {}
        for r in res:
            id_res[r["id"]] = r
        for id in ids:
            if id not in id_res:
                raise Exception("Invalid read ID %s (%s)" % (id, self._name))
        res = [dict(id_res[id]) for id in ids]
        multi_funcs = {}
        for n in field_names:
            f = self._fields[n]
            if not f.function or f.store:
                continue
            if f.function_multi:
                multi_funcs[f.function] = True
            else:
                func = getattr(self, f.function)
                ctx = context.copy()
                ctx.update(f.function_context)
                #print(">>> FUNC",f.function,n)
                vals = func(ids, context=ctx)
                #print("<<< FUNC",f.function,n)
                for r in res:
                    r[n] = vals.get(r["id"])
        for func_name in multi_funcs:
            func = getattr(self, func_name)
            if func:
                #print(">>> FUNC_MULTI",func_name)
                vals = func(ids, context=context)
                #print("<<< FUNC_MULTI",func_name)
                for r in res:
                    r.update(vals[r["id"]])
        multico_fields = [n for n in field_names if self._fields[n].multi_company and self._fields[n].store]
        if multico_fields:
            company_id = access.get_active_company()
            res2 = db.query("SELECT field,record_id,value FROM field_value WHERE model=%s AND field IN %s AND record_id IN %s AND company_id=%s", self._name, tuple(
                multico_fields), tuple(ids), company_id)
            vals = {}
            for r in res2:
                vals[(r.record_id, r.field)] = r.value
            for n in multico_fields:
                for r in res:
                    k = (r["id"], n)
                    r[n]=vals.get(k)
                f = self._fields[n]
                if isinstance(f, fields.Many2One):
                    r_ids=[]
                    for r in res:
                        v = r[n]
                        if v is not None and v.isnumeric():
                        #if v is not None:
                            r_ids.append(int(v))
                    r_ids=list(set(r_ids))
                    mr=get_model(f.relation)
                    r_ids2=mr.search([["id","in",r_ids]],context={"active_test":False})
                    r_ids2_set=set(r_ids2)
                    for r in res:
                        v = r[n]
                        if v is not None and v.isnumeric():
                        #if v is not None:
                            v=int(v)
                            if v in r_ids2_set:
                                r[n]=v
                            else:
                                r[n]=None
                elif isinstance(f, fields.Float):
                    for r in res:
                        k = (r["id"], n)
                        if k not in vals:
                            continue
                        v = vals[k]
                        if v is not None and v.isnumeric():
                        #if v is not None:
                            r[n] = float(v)
                elif isinstance(f, fields.Char):
                    pass
                elif isinstance(f, fields.File):
                    pass
                else:  # TODO: add more field types...
                    raise Exception("Multicompany field not yet implemented: %s" % n)
        for n in field_names:
            f = self._fields[n]
            if not f.function:
                if isinstance(f, fields.One2Many):
                    mr = get_model(f.relation)
                    rf = mr._fields[f.relfield]
                    if isinstance(rf, fields.Reference):
                        cond = [(f.relfield, "in", ["%s,%d" % (self._name, id) for id in ids])]
                        if f.condition:
                            cond += f.condition
                        if f.multi_company:
                            cond += [("company_id", "=", access.get_active_company())]
                        ids2 = mr.search(cond)
                        res2 = mr.read(ids2, [f.relfield], load_m2o=False)
                        vals = {}
                        for r in res2:
                            vals.setdefault(r[f.relfield], []).append(r["id"])
                        for r in res:
                            r[n] = vals.get("%s,%d" % (self._name, r["id"]), [])
                    else:
                        # XXX: remove this optimization and use general case below?
                        if not f.operator or f.operator == "in":
                            cond = [(f.relfield, "in", ids)]
                            if f.condition:
                                cond += f.condition
                            if f.multi_company:
                                cond += [("company_id", "=", access.get_active_company())]
                            ids2 = mr.search(cond, order=f.order)
                            res2 = mr.read(ids2, [f.relfield], load_m2o=False)
                            vals = {}
                            for r in res2:
                                vals.setdefault(r[f.relfield], []).append(r["id"])
                            for r in res:
                                r[n] = vals.get(r["id"], [])
                        else:
                            vals = {}
                            for id in ids:
                                cond = [(f.relfield, f.operator, id)]
                                if f.condition:
                                    cond += f.condition
                                if f.multi_company:
                                    cond += [("company_id", "=", access.get_active_company())]
                                rids = mr.search(cond)
                                vals[id] = rids
                            for r in res:
                                r[n] = vals.get(r["id"], [])
                elif isinstance(f, fields.Many2Many):
                    res2 = db.query("SELECT %s,%s FROM %s WHERE %s in (%s)" % (
                        f.relfield, f.relfield_other, f.reltable, f.relfield, ",".join([str(int(x)) for x in ids])))
                    r_ids = [r[f.relfield_other] for r in res2]
                    if f.condition:
                        mr = get_model(f.relation)
                        cond=[["id","in",r_ids]]
                        cond.append(f.condition)
                        r_ids_cond = mr.search(cond) # TODO: make this more efficient
                    else:
                        r_ids_cond = r_ids
                    vals = {}
                    for r in res2:
                        if r[f.relfield_other] in r_ids_cond:
                            vals.setdefault(r[f.relfield], []).append(r[f.relfield_other])
                    for r in res:
                        r[n] = vals.get(r["id"], [])
                elif isinstance(f, fields.Json):
                    for r in res:
                        val = r[n]
                        if val:
                            r[n] = utils.json_loads(val)
            if isinstance(f, fields.Many2One) and load_m2o:
                mr = get_model(f.relation)
                ids2 = [r[n] for r in res if r[n]]
                ids2 = list(set(ids2))
                ids2 = mr.search([["id", "in", ids2]], context={"active_test": False})  # for permissions
                res2 = mr.name_get(ids2)
                names = {}
                images = {}
                for r in res2:
                    names[r[0]] = r[1]
                    if len(r) >= 3:
                        images[r[0]] = r[2]
                for r in res:
                    id = r[n]
                    if id:
                        r[n] = [id, names.get(id, "Permission Denied"), images.get(id)]
            elif isinstance(f, fields.Reference) and load_m2o:
                refs = {}
                for r in res:
                    v = r[n]
                    if v:
                        r_model, r_id = v.split(",")
                        r_id = int(r_id)
                        refs.setdefault(r_model, []).append(r_id)
                names = {}
                for r_model, r_ids in refs.items():
                    mr = get_model(r_model)
                    r_ids = list(set(r_ids))
                    r_ids2 = mr.search([["id", "in", r_ids]], context={"active_test": False})
                    res2 = mr.name_get(r_ids2)
                    for r in res2:
                        names[(r_model, r[0])] = r[1]
                for r in res:
                    v = r[n]
                    if v:
                        r_model, r_id = v.split(",")
                        r_id = int(r_id)
                        if (r_model, r_id) in names:
                            r[n] = [v, names[(r_model, r_id)]]
                        else:
                            r[n] = None
            elif isinstance(f, fields.Char) and f.password:
                for r in res:
                    if r[n]:
                        r[n] = "****"
        trans_fields = [n for n in field_names if self._fields[n].translate]
        if trans_fields:
            locale = netforce.locale.get_active_locale()
            if locale and locale != "en_US":
                res2 = db.query("SELECT field,rec_id,translation FROM translation_field WHERE lang=%s AND model=%s AND field IN %s AND rec_id IN %s",
                                locale, self._name, tuple(trans_fields), tuple(ids))
                trans = {}
                for r in res2:
                    trans[(r.rec_id, r.field)] = r.translation
                for n in trans_fields:
                    for r in res:
                        r[n] = trans.get((r["id"], n), r[n])
        if get_time:
            t = time.strftime("%Y-%m-%d %H:%M:%S")
            for r in res:
                r["read_time"] = t
        #print("<<< READ",self._name)
        return res

    def browse(self, ids, context={}):
        # print("Model.browse",self._name,ids)
        cache = {}
        if isinstance(ids, int):
            #netforce.utils.print_color("WARNING: calling browse with int is DEPRECATED (model=%s)"%self._name,"red")
            return BrowseRecord(self._name, ids, [ids], context=context, browse_cache=cache)
        else:
            return BrowseList(self._name, ids, ids, context=context, browse_cache=cache)

    def search_browse(self, condition, **kw):
        ids = self.search(condition, **kw)
        ctx = kw.get("context", {})
        return self.browse(ids, context=ctx)

    def search_read(self, condition, field_names=None, context={}, **kw):
        res = self.search(condition, context=context, **kw)
        if isinstance(res, tuple):
            ids, count = res
            data = self.read(ids, field_names, context=context)
            return data, count
        else:
            ids = res
            data = self.read(ids, field_names, context=context)
            return data

    def get(self, key_vals, context={}, require=False):
        if not self._key:
            raise Exception("Model %s has no key" % self._name)
        if isinstance(key_vals, str):
            cond = [(self._key[0], "=", key_vals)]
        else:
            cond = [(n, "=", key_vals[n]) for n in self._key]
        res = self.search(cond)
        if not res:
            if require:
                raise Exception("Record not found: %s / %s" % (self._name, key_vals))
            return None
        if len(res) > 1:
            raise Exception("Duplicate keys (model=%s, key=%s)" % (self._name, key_vals))
        return res[0]

    def get_by_code(self,code,context={}):
        code_field=self._code_field or "code"
        res=self.search([[code_field,"=",code]])
        if not res:
            return None
        return res[0]

    def merge(self, vals):
        vals_ = {}
        for n, v in vals.items():
            if n == "id":
                continue
            f = self.get_field(n)
            if isinstance(f, fields.Many2One) and isinstance(v, str):
                mr = get_model(f.relation)
                v_ = mr.get(v)
                if not v_:
                    raise Exception("Key not found %s on %s" % (v, mr._name))
            else:
                v_ = v
            vals_[n] = v_
        if vals.get("id"):
            ids = [vals["id"]]
        else:
            if self._key:
                cond = [(k, "=", vals_.get(k)) for k in self._key]
                ids = self.search(cond)
                if len(ids) > 1:
                    raise Exception("Duplicate keys: %s %s" % (self._name, cond))
            else:
                ids = None
        if ids:
            self.write(ids, vals_)
            id = ids[0]
        else:
            id = self.create(vals_)
        return id

    def get_meta(self, field_names=None, context={}):
        if not field_names:
            field_names = self._fields.keys()
        res = {}
        for n in field_names:
            f = self.get_field(n)
            vals = f.get_meta(context=context)
            res[n] = vals
        return res

    def function_store(self, ids, field_names=None, context={}):
        t0 = time.time()
        if not field_names:
            field_names = [n for n, f in self._fields.items() if f.function and f.store]
        funcs = []
        multi_funcs = {}
        for n in field_names:
            f = self._fields[n]
            if not f.function:
                raise Exception("Not a function field: %s.%s", self._name, n)
            if f.function_multi:
                prev_order = multi_funcs.get(f.function)
                if prev_order is not None:
                    multi_funcs[f.function] = min(f.function_order, prev_order)
                else:
                    multi_funcs[f.function] = f.function_order
            else:
                funcs.append((f.function_order, f.function, f.function_context, n))
        for func_name, order in multi_funcs.items():
            funcs.append((order, func_name, {}, None))  # TODO: context
        funcs.sort(key=lambda a: (a[0], a[1]))
        db = database.get_connection()
        for order, func_name, func_ctx, n in funcs:
            func = getattr(self, func_name)
            ctx = context.copy()
            ctx.update(func_ctx)
            res = func(ids, context=ctx)
            if n:
                q = "UPDATE " + self._table
                q += " SET \"%s\"=%%s" % n
                q += " WHERE id=%s"
                for id, val in res.items():
                    db.execute(q, val, id)
            else:
                for id, vals in res.items():
                    cols = [n for n in vals.keys() if n in field_names]
                    q = "UPDATE " + self._table
                    q += " SET " + ",".join(['"%s"=%%s' % col for col in cols])
                    q += " WHERE id=%s" % int(id)
                    args = [vals[col] for col in cols]
                    db.execute(q, *args)
        self._check_constraints(ids, context=context)
        t1 = time.time()
        dt = (t1 - t0) * 1000
        print("function_store", self._name, ids, field_names, "<<< %d ms" % dt)

    def _check_constraints(self, ids, context={}):
        for name in self._constraints:
            f = getattr(self, name, None)
            if not f or not hasattr(f, "__call__"):
                raise Exception("No such method %s in %s" % (name, self._name))
            f(ids)

    def _changed(self, ids, field_names):
        funcs = {}
        for n in field_names:
            f = self._fields[n]
            if f.on_write:
                funcs.setdefault(f.on_write, []).append(n)
        for f, fields in funcs.items():
            func = getattr(self, f)
            func(ids)

    def name_get(self, ids, context={}):
        if not access.check_permission(self._name, "read", ids):
            return [(id, "Permission denied") for id in ids]
        f_name = self._name_field or "name"
        f_image = self._image_field or "image"
        if f_image in self._fields:
            show_image = True
            fields = [f_name, f_image]
        else:
            show_image = False
            fields = [f_name]
        res = self.read(ids, fields)
        if show_image:
            return [(r["id"], r[f_name], r[f_image]) for r in res]
        else:
            return [(r["id"], r[f_name]) for r in res]

    def name_search(self, name, condition=None, limit=None, context={}):
        f = self._name_field or "name"
        search_mode = context.get("search_mode")
        if search_mode == "suffix":
            cond = [[f, "=ilike", "%" + name]]
        elif search_mode == "prefix":
            cond = [[f, "=ilike", name + "%"]]
        else:
            cond = [[f, "ilike", name]]
        if condition:
            cond = [cond, condition]
        ids = self.search(cond, limit=limit, context=context)
        return self.name_get(ids, context=context)

    def name_create(self, name, context={}):
        f = self._name_field or "name"
        vals = {f: name}
        return self.create(vals, context=context)

    def _get_related(self, ids, context={}):
        path = context.get("path")
        if not path:
            raise Exception("Missing path")
        fields = path.split(".")
        vals = {}
        # i=0
        for obj in self.browse(ids):
            # print("XXX",i)
            # i+=1
            val = obj
            for field in fields:
                val = val[field]
            if isinstance(val, BrowseRecord):
                val = val.id
            vals[obj.id] = val
        return vals

    def _search_related(self, clause, context={}):
        path = context.get("path")
        if not path:
            raise Exception("Missing path")
        return [path, clause[1], clause[2]]

    def export_data(self, ids, context={}):
        exp_fields = context.get("export_fields")
        if not exp_fields:
            raise Exception("Missing export fields")
        print("Model.export_data", ids, exp_fields)

        def _get_header(path, model=self._name, prefix=""):
            print("_get_header", path, model, prefix)
            m = get_model(model)
            res = path.partition(".")
            if not res[1]:
                if path == "id":
                    label = "Database ID"
                else:
                    f = m._fields[path]
                    label = f.string
                return prefix + label.replace("/", "&#47;")
            n, _, path2 = res
            if n == "id":
                label = "Database ID"
            else:
                f = m._fields[n]
                label = f.string
            prefix += label.replace("/", "&#47;") + "/"
            return _get_header(path2, f.relation, prefix)
        out = StringIO()
        wr = csv.writer(out)
        headers = [_get_header(n) for n in exp_fields]
        wr.writerow(headers)

        def _write_objs(objs, prefix=""):
            print("write_objs", len(objs))
            rows = []
            for i, obj in enumerate(objs):
                print("%s/%s: %s.%s" % (i, len(objs), obj._model, obj.id))
                row = {}
                todo = {}
                for path in exp_fields:
                    if not path.startswith(prefix):
                        continue
                    rpath = path[len(prefix):]
                    n = rpath.split(".", 1)[0]
                    m = get_model(obj._model)
                    f = m._fields.get(n)
                    if not f and n != "id":
                        raise Exception("Invalid export field: %s" % path)
                    if isinstance(f, fields.One2Many):
                        if rpath.find(".") == -1:
                            print("WARNING: Invalid export field: %s" % path)
                            continue
                        if n not in todo:
                            todo[n] = obj[n]
                    elif isinstance(f, fields.Many2One):
                        if rpath.find(".") == -1:
                            v = obj[n]
                            if v:
                                mr = get_model(v._model)
                                exp_field = mr.get_export_field()
                                v = v[exp_field]
                            else:
                                v = ""
                            row[path] = v
                        else:
                            if n not in todo:
                                v = obj[n]
                                todo[n] = [v]
                    elif isinstance(f, fields.Selection):
                        v = obj[n]
                        if v:
                            for k, s in f.selection:
                                if v == k:
                                    v = s
                                    break
                        else:
                            v = ""
                        row[path] = v
                    elif isinstance(f, fields.Many2Many):
                        if rpath.find(".") == -1:
                            v = obj[n]
                            if v:
                                mr = get_model(v.model)
                                exp_field = mr.get_export_field()
                                v = ", ".join([o[exp_field] for o in v])
                            else:
                                v = ""
                            row[path] = v
                        else:
                            if n not in todo:
                                v = obj[n]
                                todo[n] = [v]
                    else:
                        v = obj[n]
                        row[path] = v
                subrows = {}
                for n, subobjs in todo.items():
                    subrows[n] = _write_objs(subobjs, prefix + n + ".")
                for rows2 in subrows.values():
                    if rows2:
                        row.update(rows2[0])
                rows.append(row)
                i = 1
                while 1:
                    row = {}
                    for rows2 in subrows.values():
                        if len(rows2) > i:
                            row.update(rows2[i])
                    if not row:
                        break
                    rows.append(row)
                    i += 1
            return rows
        objs = self.browse(ids, context={})
        rows = _write_objs(objs)
        for row in rows:
            data = []
            for path in exp_fields:
                v = row.get(path)
                if v is None:
                    v = ""
                data.append(v)
            wr.writerow(data)
        data = out.getvalue()
        return data

    def import_data(self, data, context={}):
        f = StringIO(data)
        rd = csv.reader(f)
        headers = next(rd)
        headers = [h.strip() for h in headers]
        rows = [r for r in rd]

        def _string_to_field(m, s):
            if s == "Database ID":
                return "id"
            strings = dict([(f.string, n) for n, f in m._fields.items()])
            n = strings.get(s.replace("&#47;", "/").strip())
            if not n:
                raise Exception("Field not found: '%s' in '%s'" % (s,m._name))
            return n

        def _get_prefix_model(prefix):
            model = self._name
            for s in prefix.split("/")[:-1]:
                m = get_model(model)
                n = _string_to_field(m, s)
                f = m._fields[n]
                model = f.relation
            return model

        def _get_vals(line, prefix):
            row = rows[line]
            model = _get_prefix_model(prefix)
            m = get_model(model)
            vals = {}
            empty = True
            for h, v in zip(headers, row):
                if not h:
                    continue
                if not h.startswith(prefix):
                    continue
                s = h[len(prefix):]
                if s.find("/") != -1:
                    continue
                n = _string_to_field(m, s)
                v = v.strip()
                if v == "":
                    v = None
                f = m._fields.get(n)
                if not f and n != "id":
                    raise Exception("Invalid field: %s" % n)
                if v:
                    if n == "id":
                        v = int(v)
                    elif isinstance(f, fields.Float):
                        v = float(v.replace(",", ""))
                    elif isinstance(f, fields.Selection):
                        found = None
                        for k, s in f.selection:
                            if v == s:
                                found = k
                                break
                        if found is None:
                            raise Exception("Invalid value for field %s: '%s'" % (h, v))
                        v = found
                    elif isinstance(f, fields.Date):
                        dt = dateutil.parser.parse(v)
                        v = dt.strftime("%Y-%m-%d")
                    elif isinstance(f, fields.Many2One):
                        mr = get_model(f.relation)
                        ctx = {
                            "parent_vals": vals,
                        }
                        res = mr.import_get(v, context=ctx)
                        if not res:
                            raise Exception("Invalid value for field %s: '%s'" % (h, v))
                        v = res
                    elif isinstance(f, fields.Many2Many):
                        rnames = v.split(",")
                        rids = []
                        mr = get_model(f.relation)
                        for rname in rnames:
                            rname = rname.strip()
                            res = mr.import_get(rname)
                            rids.append(res)
                        v = [("set", rids)]
                else:
                    if isinstance(f, (fields.One2Many,)):
                        raise Exception("Invalid column '%s'" % s)
                if v is not None:
                    empty = False
                if not v and isinstance(f, fields.Many2Many):
                    v = [("set", [])]
                vals[n] = v
            if empty:
                return None
            return vals

        def _get_subfields(prefix):
            strings = []
            for h in headers:
                if not h:
                    continue
                if not h.startswith(prefix):
                    continue
                rest = h[len(prefix):]
                i = rest.find("/")
                if i == -1:
                    continue
                s = rest[:i]
                if s not in strings:
                    strings.append(s)
            model = _get_prefix_model(prefix)
            m = get_model(model)
            fields = []
            for s in strings:
                n = _string_to_field(m, s)
                fields.append((n, s))
            return fields

        def _has_vals(line, prefix=""):
            row = rows[line]
            for h, v in zip(headers, row):
                if not h:
                    continue
                if not h.startswith(prefix):
                    continue
                s = h[len(prefix):]
                if s.find("/") != -1:
                    continue
                v = v.strip()
                if v:
                    return True
            return False

        def _read_objs(line_start=0, line_end=len(rows), prefix=""):
            blocks = []
            line = line_start
            while line < line_end:
                vals = _get_vals(line, prefix)
                if vals:
                    if blocks:
                        blocks[-1]["line_end"] = line
                    blocks.append({"vals": vals, "line_start": line})
                line += 1
            if not blocks:
                return []
            blocks[-1]["line_end"] = line_end
            all_vals = []
            for block in blocks:
                vals = block["vals"]
                all_vals.append(vals)
                line_start = block["line_start"]
                line_end = block["line_end"]
                todo = _get_subfields(prefix)
                for n, s in todo:
                    vals[n] = [("delete_all",)]
                    res = _read_objs(line_start, line_end, prefix + s + "/")
                    for vals2 in res:
                        vals[n].append(("create", vals2))
            return all_vals
        line = 0
        while line < len(rows):
            while line < len(rows) and not _has_vals(line):
                line += 1
            if line == len(rows):
                break
            line_start = line
            line += 1
            while line < len(rows) and not _has_vals(line):
                line += 1
            line_end = line
            try:
                res = _read_objs(line_start=line_start, line_end=line_end)
                assert len(res) == 1
                self.merge(res[0])
            except Exception as e:
                raise Exception("Error row %d: %s" % (line_start + 2, e))

    def audit_log(self, operation, params, context={}):
        if not self._audit_log:
            return
        related_id=None
        if self._string:
            model_name = self._string
        else:
            model_name = self._name
        if operation == "create":
            msg = "%s %d created" % (model_name, params["id"])
            details = utils.json_dumps(params["vals"])
            related_id="%s,%d"%(self._name,params["id"])
        elif operation == "delete":
            msg = "%s %s deleted" % (model_name, ",".join([str(x) for x in params["ids"]]))
            details = ""
        elif operation == "write":
            vals = params["vals"]
            if not vals:
                return
            msg = "%s %s changed" % (model_name, ",".join([str(x) for x in params["ids"]]))
            details = utils.json_dumps(params["vals"])
            if params["ids"]:
                related_id="%s,%d"%(self._name,params["ids"][0]) # XXX
        if operation == "sync_create":
            msg = "%s %d created by remote sync" % (model_name, params["id"])
            details = utils.json_dumps(params["vals"])
        elif operation == "sync_delete":
            msg = "%s %s deleted by remote_sync" % (model_name, ",".join([str(x) for x in params["ids"]]))
            details = ""
        elif operation == "sync_write":
            vals = params["vals"]
            if not vals:
                return
            msg = "%s %s changed by remote sync" % (model_name, ",".join([str(x) for x in params["ids"]]))
            details = utils.json_dumps(params["vals"])
        netforce.logger.audit_log(msg, details, related_id=related_id)

    def get_view(self, name=None, type=None, context={}):  # XXX: remove this
        #print("get_view model=%s name=%s type=%s"%(self._name,name,type))
        if name:
            res = get_model("view").search([["name", "=", name]])
            if not res:
                raise Exception("View not found: %s" % name)
            view_id = res[0]
        elif type:
            res = get_model("view").search([["model", "=", self._name], ["type", "=", type]])
            if not res:
                raise Exception("View not found: %s/%s" % (self._name, type))
            view_id = res[0]
        view = get_model("view").browse(view_id)
        fields = {}
        doc = etree.fromstring(view.layout)
        for el in doc.iterfind(".//field"):
            name = el.attrib["name"]
            f = self._fields.get(name)
            if not f:
                raise Exception("No such field %s in %s" % (name, self._name))
            fields[name] = f.get_meta()
        view_opts = {
            "name": view.name,
            "type": view.type,
            "layout": view.layout,
            "model": self._name,
            "model_string": self._string,
            "fields": fields,
        }
        return view_opts

    def call_onchange(self, method, context={}):
        #print("call_onchange",self._name,method)
        data=context.get("data",{})
        def _conv_decimal(m,vals):
            for n,v in vals.items():
                f=m._fields.get(n)
                if not f:
                    continue
                if isinstance(f,fields.Decimal) and isinstance(v,float):
                    vals[n]=Decimal(v)
                elif isinstance(f,fields.One2Many) and isinstance(v,list):
                    mr=get_model(f.relation)
                    for line_vals in v:
                        _conv_decimal(mr,line_vals)
        _conv_decimal(self,data)
        f = getattr(self, method)
        res = f(context=context)
        if res is None:
            res = {}
        if "data" in res or "field_attrs" in res or "alert" in res:
            out=res
        else:
            out={"data":res}
        def _fill_m2o(m, vals):
            for k, v in vals.items():
                if not v:
                    continue
                f = m._fields[k]
                if isinstance(f, fields.Many2One):
                    if isinstance(v, int):
                        mr = get_model(f.relation)
                        vals[k] = mr.name_get([v])[0]
                elif isinstance(f, fields.One2Many):
                    mr = get_model(f.relation)
                    for v2 in v:
                        _fill_m2o(mr, v2)
        if out.get("data"):
            _fill_m2o(self, out["data"])
        return out

    def _check_cycle(self, ids, context={}):
        for obj in self.browse(ids):
            count = 0
            p = obj.parent_id
            while p:
                count += 1
                if count > 100:
                    raise Exception("Cycle detected!")
                p = p.parent_id

    def trigger(self, ids, event, context={}):
        #print(">>> TRIGGER",self._name,ids,event)
        db = database.get_connection()
        res = db.query(
            "SELECT r.id,r.condition_method,r.condition_args,am.name AS action_model,r.action_method,r.action_args FROM wkf_rule r,model tm,model am WHERE tm.id=r.trigger_model_id AND am.id=r.action_model_id AND tm.name=%s AND r.trigger_event=%s AND r.state='active'", self._name, event)
        for r in res:
            try:
                if r.condition_method:
                    f = getattr(self, r.condition_method)
                    if r.condition_args:
                        try:
                            args = utils.json_loads(r.condition_args)
                        except:
                            raise Exception("Invalid condition arguments: %s" % r.condition_args)
                    else:
                        args = {}
                    trigger_ids = f(ids, **args)
                else:
                    trigger_ids = ids
                if trigger_ids:
                    am = get_model(r.action_model)
                    f = getattr(am, r.action_method)
                    if r.action_args:
                        try:
                            args = utils.json_loads(r.action_args)
                        except:
                            raise Exception("Invalid action arguments: %s" % r.action_args)
                    else:
                        args = {}
                    ctx = context.copy()
                    ctx.update({
                        "trigger_model": self._name,
                        "trigger_ids": trigger_ids,
                    })
                    f(context=ctx, **args)
            except Exception as e:
                import traceback
                traceback.print_exc()
                db.execute("UPDATE wkf_rule SET state='inactive',error=%s WHERE id=%s", str(e), r.id)

    def check_condition(self, ids, condition=None, context={}):
        cond = []
        if ids:
            cond.append(["id", "in", ids])
        if condition:
            cond.append(condition)
        res = self.search(cond, context=context)
        return res

    def archive(self, ids, context={}):
        self.write(ids, {"active": False})

    def get_export_field(self):
        try_fields=[self._export_field,self._code_field,"code",self._name_field,"name"]
        for f in try_fields:
            if f and f in self._fields:
                return f
        raise Exception("No export field for model %s"%self._name)

    def import_get(self, name, context={}):
        exp_field = self.get_export_field()
        res = self.search([[exp_field, "=", name]])
        if not res:
            return None
        if len(res) > 1:
            raise Exception("Duplicate records named '%s' of %s" % (name, self._name))
        return res[0]

    def get_report_data(self, ids, context={}):
        print("get_report_data", self._name, ids)
        settings = get_model("settings").browse(1)
        objs = self.browse(ids)
        data = {
            "settings": settings,
            "objs": objs,
        }
        if objs:
            data["obj"] = objs[0]
        user_id = access.get_active_user()
        if user_id:
            user = get_model("base.user").browse(user_id)
            data["user"] = user
        company_id = access.get_active_company()
        if company_id:
            company = get_model("company").browse(company_id)
            data["company"] = company
        return data

    def get_report_data_old(self, context={}):  # XXX: remove this later
        print("get_report_data_old", self._name)
        refer_id = int(context["refer_id"])
        ids = [refer_id]
        return self.get_report_data(ids, context=context)

    def read_group(self, group_fields=[], agg_fields=[], condition=[], having=[], order=None, limit=None, offset=None, context={}):
        select_cols = []
        group_cols = []
        tbl_count = 1
        joins = []
        for n in group_fields:
            fnames = n.split(".")
            m = self
            tbl = "tbl0"
            for fname in fnames[:-1]:
                f = m.get_field(fname)
                mr = get_model(f.relation)
                rtbl = "tbl%d" % tbl_count
                tbl_count += 1
                if isinstance(f, fields.Many2One):
                    joins.append("JOIN %s %s ON %s.id=%s.%s" % (mr._table, rtbl, rtbl, tbl, fname))
                elif isinstance(f, fields.One2Many):
                    rf = mr.get_field(f.relfield)
                    if isinstance(rf, fields.Many2One):
                        joins.append("JOIN %s %s ON %s.%s=%s.id" % (mr._table, rtbl, rtbl, f.relfield, tbl))
                    elif isinstance(rf, fields.Reference):
                        joins.append("JOIN %s %s ON %s.%s='%s,'||%s.id" %
                                     (mr._table, rtbl, rtbl, f.relfield, m._name, tbl))
                    else:
                        raise Exception("Invalid relfield: %s" % f.relfield)
                else:
                    raise Exception("Invalid field path: %s" % n)
                m = mr
                tbl = rtbl
            fname = fnames[-1]
            f = m.get_field(fname)
            func = f.sql_function
            if func:
                op = func[0]
                param = func[1]
                if op == "year":
                    expr = "to_char(%s.\"%s\",'YYYY')" % (tbl, param)
                elif op == "quarter":
                    expr = "to_char(%s.\"%s\",'YYYY-Q')" % (tbl, param)
                elif op == "month":
                    expr = "to_char(%s.\"%s\",'YYYY-MM')" % (tbl, param)
                elif op == "week":
                    expr = "to_char(%s.\"%s\",'YYYY-IW')" % (tbl, param)
                else:
                    raise Exception("Invalid sql function: %s" % func)
            else:
                expr = "%s.\"%s\"" % (tbl, fname)
            select_cols.append("%s AS \"%s\"" % (expr, n))
            group_cols.append("\"%s\"" % n)
        select_cols.append("COUNT(*) AS _count")
        for n in agg_fields:
            f = self.get_field(n)
            func = f.agg_function
            if not func:
                raise Exception("Missing aggregate function for field: %s" % n)
            op = func[0]
            param = func[1]
            if op == "sum":
                col = "SUM(tbl0.\"%s\")" % param
            else:
                raise Exception("Invalid aggregate function: %s" % func)
            col += " AS \"%s\"" % n
            select_cols.append(col)
        q = "SELECT " + ",".join(select_cols)
        q += " FROM " + self._table + " tbl0"
        if joins:
            q += " " + " ".join(joins)
        cond=[condition]
        if "active" in self._fields and context.get("active_test") != False:
            if not self._check_condition_has_active(condition):
                cond.append(["active", "=", True])
        share_condition = access.get_filter(self._name, "read")
        if share_condition:
            cond.append(share_condition)
        joins, cond, args = self._where_calc(cond, context=context, tbl_count=tbl_count)
        if joins:
            q += " " + " ".join(joins)
        if cond:
            q += " WHERE (" + cond + ")"
        if group_cols:
            q += " GROUP BY " + ",".join(group_cols)
        db = database.get_connection()
        print("q", q)
        print("args", args)
        res = db.query(q, *args)
        res = [dict(r) for r in res]
        for n in group_fields:
            fnames = n.split(".")
            m = self
            for fname in fnames[:-1]:
                f = m.get_field(fname)
                if not isinstance(f, (fields.Many2One, fields.One2Many)):
                    raise Exception("Invalid field path: %s" % n)
                m = get_model(f.relation)
            fname = fnames[-1]
            f = m.get_field(fname)
            if isinstance(f, fields.Many2One):
                mr = get_model(f.relation)
                r_ids = [r[n] for r in res if r[n]]
                r_ids = list(set(r_ids))
                res2 = mr.name_get(r_ids)
                names = {}
                for r in res2:
                    names[r[0]] = r[1]
                for r in res:
                    r_id = r[n]
                    if r_id:
                        r[n] = [r_id, names.get(r_id, "Permission Denied")]

        def _sort_key(r):  # XXX: faster
            k = []
            for n in group_fields:
                v = r[n]
                fnames = n.split(".")
                m = self
                for fname in fnames[:-1]:
                    f = m.get_field(fname)
                    if not isinstance(f, (fields.Many2One, fields.One2Many)):
                        raise Exception("Invalid field path: %s" % n)
                    m = get_model(f.relation)
                fname = fnames[-1]
                f = m.get_field(fname)
                if v is None:
                    s = ""
                elif isinstance(f, fields.Many2One):
                    s = v[1]
                else:
                    s = str(v)
                k.append(s)
            return k
        res.sort(key=_sort_key)
        return res

    def read_path(self, ids, field_paths, context={}):
        print(">>> read_path %s %s %s"%(self._name,ids,field_paths))
        field_names=[]
        sub_paths={}
        for path in field_paths:
            if isinstance(path,str):
                n,_,paths=path.partition(".")
            elif isinstance(path,list):
                n=path[0]
                if not isinstance(n,str):
                    raise Exception("Invalid path field path %s for model %s"%(path,self._name))
                paths=path[1]
            f=self._fields[n]
            field_names.append(n)
            if paths:
                if not isinstance(f,(fields.Many2One,fields.One2Many,fields.Many2Many)):
                    raise Exception("Invalid path field path %s for model %s"%(path,self._name))
                sub_paths.setdefault(n,[])
                if isinstance(paths,str) :
                    sub_paths[n].append(paths)
                elif isinstance(paths,list) :
                    sub_paths[n]+=paths
        field_names=list(set(field_names))
        res=self.read(ids,field_names,context=context,load_m2o=False)
        for n in field_names:
            f=self._fields[n]
            rpaths=sub_paths.get(n)
            if rpaths:
                mr=get_model(f.relation)
                if isinstance(f,fields.Many2One):
                    rids=[]
                    for r in res:
                        v=r[n]
                        if v:
                            rids.append(v)
                    rids=list(set(rids))
                    res2=mr.read_path(rids,rpaths,context=context)
                    rvals={}
                    for r in res2:
                        rvals[r["id"]]=r
                    for r in res:
                        v=r[n]
                        if v:
                            r[n]=rvals[v]
                elif isinstance(f,(fields.One2Many,fields.Many2Many)):
                    rids=[]
                    for r in res:
                        rids+=r[n]
                    rids=list(set(rids))
                    res2=mr.read_path(rids,rpaths,context=context)
                    rvals={}
                    for r in res2:
                        rvals[r["id"]]=r
                    for r in res:
                        r[n]=[rvals[v] for v in r[n]]
        return res

    def search_read_path(self, condition, field_paths, context={}):
        ids=self.search(condition,context=context)
        return self.read_path(ids,field_paths,context=context)

    def save_data(self,data,context={}):
        print(">>> save_data %s %s"%(self._name,data))
        o2m_fields=[]
        obj_vals={}
        for n,v in data.items():
            if n=="id":
                continue
            f=self._fields[n]
            if isinstance(f,fields.One2Many):
                o2m_fields.append(n)
            else:
                obj_vals[n]=v
        obj_id=data.get("id")
        if obj_id:
            self.write([obj_id],obj_vals,context=context)
        else:
            obj_id=self.create(obj_vals,context=context)
        if o2m_fields:
            o2m_vals=self.read([obj_id],o2m_fields,context=context)[0]
            for n in o2m_fields:
                f=self._fields[n]
                mr=get_model(f.relation)
                new_rids=set()
                for rdata in data[n]:
                    rdata2=rdata.copy()
                    rdata2[f.relfield]=obj_id
                    rid=mr.save_data(rdata2,context={})
                    new_rids.add(rid)
                del_rids=[rid for rid in o2m_vals[n] if rid not in new_rids]
                if del_rids:
                    mr.delete(del_rids)
        return obj_id

    def sync_get_key(self, ids, context={}):
        if not self._key:
            raise Exception("Missing key fields (model=%s)" % self._name)
        obj = self.browse(ids[0])  # XXX: speed
        key = []
        for n in self._key:
            f = self._fields[n]
            v = obj[n]
            if isinstance(f, (fields.Many2One, fields.Reference)):
                v = v.sync_get_key() if v else None
            key.append(v)
        return tuple(key)

    def sync_list_keys(self, condition, context={}):
        ids = self.search(condition, order="write_time", context={"active_test": False})
        keys = []
        for obj in self.browse(ids):
            k = obj.sync_get_key()
            keys.append([k, obj.id, obj.write_time])
        return keys

    def sync_export(self, ids, context={}):
        # print("Model.sync_export",self._name,ids)
        data = []
        for obj in self.browse(ids):
            vals = {}
            for n in self._fields:
                f = self._fields[n]
                if not f.store and not isinstance(f, fields.Many2Many):
                    continue
                if isinstance(f, (fields.Char, fields.Text, fields.Float, fields.Integer, fields.Date, fields.DateTime, fields.Selection, fields.Boolean)):
                    vals[n] = obj[n]
                elif isinstance(f, fields.Many2One):
                    v = obj[n]
                    if v:
                        mr = get_model(f.relation)
                        if mr._key:
                            v = v.sync_get_key()
                        else:
                            v = None
                    else:
                        v = None
                    vals[n] = v
                elif isinstance(f, fields.Reference):
                    v = obj[n]
                    if v:
                        mr = get_model(v._model)
                        if mr._key:
                            v = [v._model, v.sync_get_key()]
                        else:
                            v = None
                    else:
                        v = None
                    vals[n] = v
                elif isinstance(f, fields.Many2Many):
                    v = obj[n]
                    vals[n] = [x.sync_get_key() for x in v]
            print(">" * 80)
            print("sync_export record", vals)
            data.append(vals)
        return data

    def sync_find_key(self, key, check_dup=False, context={}):
        if not self._key:
            raise Exception("Missing key fields (model=%s)" % self._name)
        cond = []
        for n, v in zip(self._key, key):
            f = self._fields[n]
            if isinstance(f, fields.Many2One):
                if v:
                    mr = get_model(f.relation)
                    v = mr.sync_find_key(v)
            elif isinstance(f, fields.Reference):
                if v:
                    mr = get_model(v[0])
                    v = mr.sync_find_key(v[1])
            cond.append([n, "=", v])
        ids = self.search(cond, context={"active_test": False})
        if not ids:
            return None
        if len(ids) > 1:
            if check_dup:
                raise Exception("Duplicate key (model=%s, key=%s)" % (self._name, key))
            else:
                return None
        return ids[0]

    def sync_import(self, data, context={}):
        # print("Model.sync_import",self._name,data)
        for rec in data:
            print("<" * 80)
            print("sync_import record", rec)
            try:
                vals = {}
                for n, v in rec.items():
                    f = self._fields[n]
                    if isinstance(f, (fields.Char, fields.Text, fields.Float, fields.Integer, fields.Decimal, fields.Date, fields.DateTime, fields.Selection, fields.Boolean)):
                        vals[n] = v
                    elif isinstance(f, fields.Many2One):
                        if v:
                            mr = get_model(f.relation)
                            vals[n] = mr.sync_find_key(v)
                        else:
                            vals[n] = None
                    elif isinstance(f, fields.Reference):
                        if v:
                            mr = get_model(v[0])
                            r_id = mr.sync_find_key(v[1])
                            vals[n] = "%s,%d" % (v[0], r_id) if r_id else None
                        else:
                            vals[n] = None
                    elif isinstance(f, fields.Many2Many):
                        mr = get_model(f.relation)
                        r_ids = []
                        for x in v:
                            r_id = mr.sync_find_key(x)
                            if r_id:
                                r_ids.append(r_id)
                        vals[n] = [("set", r_ids)]
                if not self._key:
                    raise Exception("Missing key fields (model=%s)" % self._name)
                for n in self._key:
                    if rec[n] and not vals[n]:
                        raise Exception("Key field not found: %s (%s)" % (rec[n], n))
                cond = [[n, "=", vals[n]] for n in self._key]
                ids = self.search(cond, context={"active_test": False})
                if not ids:
                    self.sync_create(vals)
                else:
                    if len(ids) > 1:
                        key = [rec[n] for n in self._key]
                        raise Exception("Duplicate key (model=%s, key=%s)" % (self._name, key))
                    self.sync_write(ids, vals)
            except Exception as e:
                import traceback
                traceback.print_exc()
                raise Exception("Error importing sync data: %s %s" % (e, rec))

    def sync_create(self, vals, context={}):
        # print("Model.sync_create",self._name,vals)
        # TODO: check perm
        cols = [n for n in vals if self._fields[n].store]
        q = "INSERT INTO " + self._table
        q += " (" + ",".join(['"%s"' % col for col in cols]) + ")"
        q += " VALUES (" + ",".join(["%s" for col in cols]) + ") RETURNING id"
        args = [vals[n] for n in cols]
        db = database.get_connection()
        res = db.get(q, *args)
        new_id = res.id
        for n in vals:
            f = self._fields[n]
            if isinstance(f, fields.Many2Many):
                mr = get_model(f.relation)
                ops = vals[n]
                for op in ops:
                    if op[0] == "set":
                        r_ids = op[1]
                        for r_id in r_ids:
                            db.execute("INSERT INTO %s (%s,%s) VALUES (%%s,%%s)" %
                                       (f.reltable, f.relfield, f.relfield_other), new_id, r_id)
                    else:
                        raise Exception("Invalid operation: %s" % op[0])
        self.audit_log("sync_create", {"id": new_id, "vals": vals})
        return new_id

    def sync_write(self, ids, vals, context={}):
        # print("Model.sync_write",ids,vals)
        # TODO: check perm
        if not ids or not vals:
            return
        db = database.get_connection()
        cols = [n for n in vals if self._fields[n].store]
        q = "UPDATE " + self._table
        q += " SET " + ",".join(['"%s"=%%s' % col for col in cols])
        q += " WHERE id IN (" + ",".join([str(int(id)) for id in ids]) + ")"
        args = [vals[n] for n in cols]
        db.execute(q, *args)
        for n in vals:
            f = self._fields[n]
            if isinstance(f, fields.Many2Many):
                mr = get_model(f.relation)
                ops = vals[n]
                for op in ops:
                    if op[0] == "set":
                        r_ids = op[1]
                        db.execute("DELETE FROM %s WHERE %s IN %%s" % (f.reltable, f.relfield), tuple(ids))
                        for id1 in ids:
                            for id2 in r_ids:
                                db.execute("INSERT INTO %s (%s,%s) VALUES (%%s,%%s)" %
                                           (f.reltable, f.relfield, f.relfield_other), id1, id2)
                    else:
                        raise Exception("Invalid operation: %s" % op[0])
        self.audit_log("sync_write", {"ids": ids, "vals": vals})

    def sync_delete(self, ids, context={}):
        # TODO: check perm
        if not ids:
            return
        q = "DELETE FROM " + self._table + " WHERE id IN (" + ",".join([str(int(id)) for id in ids]) + ")"
        db = database.get_connection()
        try:
            db.execute(q)
        except psycopg2.Error as e:
            code = e.pgcode
            if code == "23502":
                raise Exception(
                    "Can't delete item because it is still being referenced (model=%s, ids=%s)" % (self._name, ids))
        self.audit_log("sync_delete", {"ids": ids})

    def _clean_references(self,ids,context={}):
        print("_clean_references",self._name,ids)
        field_names = [n for n, f in self._fields.items() if isinstance(f,fields.Reference)]
        print("field_names",field_names)
        res=self.read(ids,field_names,load_m2o=False)
        ref_ids={}
        for r in res:
            for n in field_names:
                v=r[n]
                if not v:
                    continue
                model,model_id=v.split(",")
                model_id=int(model_id)
                ref_ids.setdefault(model,[]).append(model_id)
        print("ref_ids",ref_ids)
        invalid_refs=set()
        for model,rids in ref_ids.items():
            rids2=get_model(model).search([["id","in",rids]])
            rids2=set(rids2)
            for rid in rids:
                if rid not in rids2:
                    invalid_refs.add("%s,%d"%(model,rid))
        print("invalid_refs",invalid_refs)
        for r in res:
            for n in field_names:
                v=r[n]
                if not v:
                    continue
                if v in invalid_refs:
                    print("cleaning field %s of %s.%d..."%(n,model,r["id"]))
                    self.write([r["id"]],{n:None})

class BrowseList(object):  # TODO: optimize for speed

    def __init__(self, model, ids, related_ids, context={}, browse_cache=None):
        self.model = model
        self.ids = ids
        self.related_ids = related_ids
        self.browse_cache = browse_cache
        self.context = context
        self.records = [
            BrowseRecord(model, id, related_ids, context=context, browse_cache=self.browse_cache) for id in ids]
        self.id_records = {obj.id: obj for obj in self.records}

    def __len__(self):
        return len(self.records)

    def __iter__(self):
        for obj in self.records:
            yield obj

    def get(self, key, default=None):
        return self[key]

    def __getattr__(self, name):
        return self[name]

    def by_id(self, obj_id):
        return self.id_records[obj_id]

    def __getitem__(self, key):
        if key == "_count":
            return len(self.ids)
        elif isinstance(key, int):
            return self.records[key]
        elif isinstance(key, slice):
            return self.records[key]
        elif isinstance(key, str):
            m = get_model(self.model)
            f = getattr(m, key, None)
            if f and hasattr(f, "__call__"):
                def call(*a, **kw):
                    return f(self.ids, *a, **kw)
                return call
            id = m.get_by_code(key)
            obj = BrowseRecord(self.model, id, [id], context=self.context, browse_cache=self.browse_cache)
            return obj
        else:
            raise Exception("Invalid browse key: %s" % key)


class BrowseRecord(object):

    def __init__(self, model, id, related_ids, context={}, browse_cache=None):
        if browse_cache is None:
            browse_cache = {}
        self._model = model
        self.id = id
        self.related_ids = related_ids
        self.context = context
        self.browse_cache = browse_cache

    def get(self, key, default=None):
        return self[key]

    def __getattr__(self, name):
        return self[name]

    def __getitem__(self, name):
        if name == "id":
            return self.id
        if name == "_model":
            return self._model
        if not self.id:
            return None
        m = get_model(self._model)
        fld = m._fields.get(name)
        if not fld:
            f = getattr(m, name, None)
            if not f or not hasattr(f, "__call__"):
                #raise Exception("No such attribute %s in %s"%(name,self._model))
                return None  # XXX: check if safe to do this, need it for report...

            def call(*a, **kw):
                #print("BrowseRecord call %s %s %s"%(m._name,self.id,name))
                return f([self.id], *a, **kw)
            return call
        model_cache = self.browse_cache.setdefault(self._model, {})
        cache = model_cache.setdefault(self.id, {})
        if not name in cache:
            missing_ids = [id for id in self.related_ids if id not in model_cache or name not in model_cache[id]]
            missing_ids = list(set(missing_ids))
            field_names = [name]
            if fld.eager_load:
                for n, f in m._fields.items():
                    if f.eager_load and n != name:
                        field_names.append(n)
            #print("BrowseRecord read %s %s %s"%(m._name,missing_ids,field_names))
            res = m.read(missing_ids, field_names, load_m2o=False, context=self.context)
            for n in field_names:
                fld = m._fields.get(n)
                if isinstance(fld, fields.Many2One):
                    ids2 = [r[n] for r in res if r[n]]
                    ids2 = list(set(ids2))
                    for r in res:
                        val = r[n]
                        r[n] = BrowseRecord(
                            fld.relation, val, ids2, context=self.context, browse_cache=self.browse_cache)
                elif isinstance(fld, (fields.One2Many, fields.Many2Many)):
                    ids2 = []
                    for r in res:
                        ids2 += r[n]
                    ids2 = list(set(ids2))
                    for r in res:
                        val = r[n]
                        r[n] = BrowseList(
                            fld.relation, val, related_ids=ids2, context=self.context, browse_cache=self.browse_cache)
                elif isinstance(fld, fields.Reference):
                    r_model_ids = {}
                    for r in res:
                        val = r[n]
                        if val:
                            r_model, r_id = val.split(",")
                            r_id = int(r_id)
                            r_model_ids.setdefault(r_model, []).append(r_id)
                    for r_model, r_ids in r_model_ids.items():
                        r_model_ids[r_model] = list(set(r_ids))
                    for r in res:
                        val = r[n]
                        if val:
                            r_model, r_id = val.split(",")
                            r_id = int(r_id)
                            r_ids = r_model_ids[r_model]
                            r[n] = BrowseRecord(
                                r_model, r_id, r_ids, context=self.context, browse_cache=self.browse_cache)
                        else:
                            r[n] = BrowseRecord(None, None, [], context=self.context, browse_cache=self.browse_cache)
            for r in res:
                model_cache.setdefault(r["id"], {}).update(r)
        val = cache[name]
        return val

    def __bool__(self):
        return self.id != None


def update_db(force=False):
    print("update_db")
    access.set_active_user(1)
    db_version = utils.get_db_version() or "0"
    mod_version = netforce.get_module_version()
    if utils.compare_version(db_version, mod_version) == 0:
        print("Database is already at version %s" % mod_version)
        if not force:
            return
        print("Upgrading anyway...")
    if utils.compare_version(db_version, mod_version) > 0:
        print("Database is at a newer version (%s)" % db_version)
        if not force:
            return
        print("Upgrading anyway...")
    print("Upgrading database from version %s to %s" % (db_version, mod_version))
    for model in sorted(models):
        m = models[model]
        if not m._store:
            continue
        m.update_db()
    for model in sorted(models):
        try:
            m = models[model]
            if not m._store:
                continue
            for field in sorted(m._fields):
                f = m._fields[field]
                f.update_db()
        except Exception as e:
            print("Failed to update fields of %s" % model)
            raise e
    for model in sorted(models):
        try:
            m = models[model]
            if not m._store:
                continue
            m.update_db_constraints()
        except Exception as e:
            print("Failed to update constraints of %s" % model)
            raise e
    for model in sorted(models):
        try:
            m = models[model]
            if not m._store:
                continue
            m.update_db_indexes()
        except Exception as e:
            print("Failed to update indexes of %s" % model)
            raise e
    if utils.is_empty_db():
        print("Initializing empty database...")
        utils.init_db()
    utils.set_db_version(mod_version)
    print("Upgrade completed")


def delete_transient():
    pass  # XXX


def models_to_json():
    data = {}
    for name, m in models.items():
        res = model_to_json(m)
        data[name] = res
    return data


def model_to_json(m):
    data = {}
    if m._string:
        data["string"] = m._string
    if m._offline:
        data["offline"] = True
    data["fields"] = {}
    for n, f in m._fields.items():
        f_data = {}
        f_data["string"] = f.string
        if isinstance(f, fields.Char):
            f_data["type"] = "char"
        elif isinstance(f, fields.Text):
            f_data["type"] = "text"
        elif isinstance(f, fields.Float):
            f_data["type"] = "float"
        elif isinstance(f, fields.Decimal):
            f_data["type"] = "decimal"
            if f.scale != 2:
                f_data["scale"] = f.scale
            if f.precision != 16:
                f_data["precision"] = f.precision
        elif isinstance(f, fields.Integer):
            f_data["type"] = "integer"
        elif isinstance(f, fields.Boolean):
            f_data["type"] = "boolean"
        elif isinstance(f, fields.Date):
            f_data["type"] = "date"
        elif isinstance(f, fields.DateTime):
            f_data["type"] = "datetime"
        elif isinstance(f, fields.Selection):
            f_data["type"] = "selection"
            f_data["selection"] = f.selection
        elif isinstance(f, fields.File):
            f_data["type"] = "file"
        elif isinstance(f, fields.Json):
            f_data["type"] = "json"
        elif isinstance(f, fields.Many2One):
            f_data["type"] = "many2one"
            f_data["relation"] = f.relation
            if f.condition:
                f_data["condition"] = f.condition
        elif isinstance(f, fields.One2Many):
            f_data["type"] = "one2many"
            f_data["relation"] = f.relation
            f_data["relfield"] = f.relfield
            if f.condition:
                f_data["condition"] = f.condition
            if f.order:
                f_data["order"] = f.order
        elif isinstance(f, fields.Many2Many):
            f_data["type"] = "many2many"
            f_data["relation"] = f.relation
        elif isinstance(f, fields.Reference):
            f_data["type"] = "reference"
            f_data["selection"] = f.selection
        else:
            raise Exception("Invalid field: %s.%s" % (m._name, n))
        if f.required:
            f_data["required"] = True
        if f.readonly:
            f_data["readonly"] = True
        if f.search:
            f_data["search"] = True
        if f.store:
            f_data["store"] = True
        data["fields"][n] = f_data
    return data


def add_method(model):
    def decorator(f):
        m = get_model(model)
        setattr(m.__class__, f.__name__, f)
        return f
    return decorator


def add_default(model, field):
    def decorator(f):
        m = get_model(model)
        setattr(m.__class__, f.__name__, f)
        m._defaults[field] = f
        return f
    return decorator
