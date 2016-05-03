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

import netforce
from netforce import database
from netforce import utils

_active_user = None
_active_company = None


def set_active_user(uid):
    global _active_user
    _active_user = uid


def set_active_company(company_id):
    global _active_company
    _active_company = company_id


def clear_active_user():
    global _active_user
    _active_user = None


def clear_active_company():
    global _active_company
    _active_user = company


def get_active_user():
    return _active_user


def get_active_company():
    return _active_company


def get_active_profile():
    uid = get_active_user()
    db = database.get_connection()
    if uid:
        res = db.get("SELECT profile_id FROM base_user WHERE id=%s", uid)
        profile_id = res.profile_id if res else None
    else:
        res = db.get("SELECT anon_profile_id FROM settings WHERE id=1")
        profile_id = res.anon_profile_id if res else None
    return profile_id


def get_active_role():
    uid = get_active_user()
    db = database.get_connection()
    res = db.get("SELECT role_id FROM base_user WHERE id=%s", uid)
    role_id = res.role_id if res else None
    return role_id

_ip_addr = None


def set_ip_addr(ip):
    global _ip_addr
    _ip_addr = ip


def clear_ip_addr():
    global _ip_addr
    _ip_addr = None


def get_ip_addr():
    return _ip_addr


def get_permissions(model):
    uid = get_active_user()
    if uid == 1:
        return {
            "read": True,
            "create": True,
            "write": True,
            "delete": True,
            "view_all": True,
            "modif_all": True,
        }
    db = database.get_connection()
    if uid:
        res = db.get("SELECT profile_id FROM base_user WHERE id=%s", uid)
        profile_id = res.profile_id if res else None
    else:
        res = db.get("SELECT anon_profile_id FROM settings WHERE id=1")
        profile_id = res.anon_profile_id if res else None
    if not profile_id:
        return {
            "read": False,
            "create": False,
            "write": False,
            "delete": False,
            "view_all": False,
            "modif_all": False,
        }
    res = db.get(
        "SELECT a.* FROM profile_access a JOIN model m ON m.id=a.model_id WHERE a.profile_id=%s AND m.name=%s", profile_id, model)
    if res:
        perms = {
            "read": res.perm_read,
            "create": res.perm_create,
            "write": res.perm_write,
            "delete": res.perm_delete,
            "view_all": res.view_all,
            "modif_all": res.modif_all,
        }
    else:
        res = db.get("SELECT default_model_perms FROM profile WHERE id=%s", profile_id)
        if res.default_model_perms == "full":
            perms = {
                "read": True,
                "create": True,
                "write": True,
                "delete": True,
                "view_all": False,
                "modif_all": False,
            }
        else:
            perms = {
                "read": False,
                "create": False,
                "write": False,
                "delete": False,
                "view_all": False,
                "modif_all": False,
            }
    return perms


def get_share_settings(model):
    db = database.get_connection()
    res = db.get("SELECT a.* FROM share_access a JOIN model m ON m.id=a.model_id WHERE m.name=%s", model)
    if res:
        share = {
            "default_access": res.default_access,
            "grant_parent": res.grant_parent,
        }
    else:
        share = {
            "default_access": "public_rw",
            "grant_parent": False,
        }
    return share


def check_permission(model, method, ids=None):
    #print("check_permission model=%s method=%s ids=%s"%(model,method,ids))
    user_id = get_active_user()
    if user_id == 1:
        return True
    perms = get_permissions(model)
    #print("  perms",perms)
    if not perms[method]:
        return False
    if method == "create":
        return True
    if not ids:
        return True
    condition = get_filter(model, method)
    return check_condition(model, ids, condition)


def check_condition(model, ids, condition):
    # print("check_condition",model,ids,condition)
    if not condition:
        return True
    m = netforce.model.get_model(model)
    ids = list(set(ids))
    check_cond = [["id", "in", ids], condition]
    joins, cond, args = m._where_calc(check_cond)
    q = "SELECT tbl0.id FROM " + m._table + " tbl0"
    if joins:
        q += " " + " ".join(joins)
    if cond:
        q += " WHERE " + cond
    db = database.get_connection()
    res = db.query(q, *args)
    if len(res) != len(ids):
        #print("=> False")
        ok_ids = [r.id for r in res]
        #print("check_condition failed: %s %s"%(model,[id for id in ids if id not in ok_ids]))
        return False
    #print("=> True")
    return True


def get_filter_no_company(model, method):
    # print("get_filter_no_company",model,method)
    user_id = get_active_user()
    if user_id == 1:
        return []
    perms = get_permissions(model)
    if perms["view_all"] and method == "read":
        return []
    elif perms["modif_all"] and method in ("write", "delete"):
        return []
    profile_id = get_active_profile()
    role_id = get_active_role()  # XXX: speed
    company_id = get_active_company()  # XXX: speed
    db = database.get_connection()
    res = db.query(
        "SELECT * FROM share_access a JOIN model m ON m.id=a.model_id WHERE m.name=%s AND a.active=true AND (a.select_profile='all' OR (a.select_profile='include' AND a.id IN (SELECT share_id FROM m2m_share_profile WHERE profile_id=%s)) OR (a.select_profile='exclude' AND a.id NOT IN (SELECT share_id FROM m2m_share_excl_profile WHERE profile_id=%s)))", model, profile_id, profile_id)
    condition = []
    for share in res:
        if share.default_access == "private":
            cond = [["user_id", "=", user_id]]
            if share.grant_parent:
                cond = ["or", cond, ["user_id.role_id", "child_of<", role_id]]
        elif share.default_access == "public_ro":
            if method == "read":
                cond = []
            else:
                cond = [["user_id", "=", user_id]]
                if share.grant_parent:
                    cond = ["or", cond, ["user_id.role_id", "child_of<", role_id]]
        elif share.default_access == "public_rw":
            cond = []
        elif share.default_access == "custom":
            if share.filter_type == "w" and method == "read":
                return []
            res = db.get("SELECT * FROM base_user WHERE id=%s", user_id)
            ctx = {
                "user_id": user_id,
            }
            if res:
                ctx.update({
                    "role_id": res.role_id,  # XXX: deprecated
                    "contact_id": res.contact_id,  # XXX: deprecated
                    "user": dict(res) if res else None,
                    "company_id": company_id,
                })
            try:
                cond = utils.eval_json(share.condition, ctx)
            except:
                raise Exception("Invalid filter in sharing setting #%s: %s" % (share.id, share.condition))
        condition.append(cond)
    res = db.query("SELECT * FROM share_record s WHERE s.user_id=%s AND s.related_id LIKE %s", user_id, model+",%%")  # XXX: speed
    share_ids = [int(r.related_id.split(",")[1]) for r in res]
    if share_ids:
        condition = ["or", condition, ["id", "in", share_ids]]
    return condition


def get_filter(model, method):
    condition = get_filter_no_company(model, method)
    m = netforce.model.get_model(model)
    if m._multi_company:
        company_id = get_active_company()
        if company_id:
            condition = [condition, ["or", ["company_id", "=", None], ["company_id", "child_of", company_id]]]
    #print("=> condition",condition)
    return condition


def check_group(group):
    uid = get_active_user()
    db = database.get_connection()
    res = db.get(
        "SELECT * FROM user_group g, m2m_base_user_user_group r WHERE g.name=%s AND r.user_group_id=g.id AND r.base_user_id=%s", group, uid)
    if res:
        return True
    else:
        return False


def check_permission_other(perm):
    user_id = get_active_user()
    if user_id == 1:
        return True
    profile_id = get_active_profile()
    db = database.get_connection()
    res = db.get(
        "SELECT * FROM permission p, m2m_permission_profile r WHERE p.code=%s AND r.permission_id=p.id AND r.profile_id=%s", perm, profile_id)
    if res:
        return True
    else:
        return False

def allow_create_transaction():
    db = database.get_connection()
    allow=True
    if _active_company:
        res=db.query("select prevent_trans from company where id=%s"%(_active_company))
        if res:
            allow=not res[0]['prevent_trans']
    return allow
