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

import tornado.web
import mimetypes
from . import module
import os
import distutils.dir_util
import pkg_resources
import hashlib
from . import locale
from io import StringIO
from . import database
import json
from netforce.model import get_model, models_to_json
import glob
from netforce import model
from netforce import layout
from netforce import action
from netforce import template
import netforce
import tempfile
from netforce import config
from netforce.database import get_connection
from netforce import utils
from .access import get_active_user, set_active_user
import netforce

mimetypes.add_type("application/x-font-woff", ".woff")
mimetypes.add_type("font/opentype", ".ttf")
mimetypes.add_type("text/cache-manifest", ".appcache")
mimetypes.add_type("text/plain", ".log")


def get_static_data(path,req):
    print("get_static_data", path)
    if os.path.exists("static/" + path):
        data = open("static/" + path, "rb").read()
        return data
    data = module.read_module_file("static/" + path)
    if data:
        # if not config.DEV_MODE:
        #    write_static_data(path,data)
        return data
    comps = path.split("/")
    if comps[0] == "db" and comps[2] == "themes": # XXX
        theme_name = comps[3]
        file_path = "/".join(comps[4:])
        db = database.get_connection()
        try:
            data = get_theme_static_data(theme_name, file_path)
            db.commit()
        except:
            db.rollback()
        if data:
            if not config.DEV_MODE:
                write_static_data(path, data)
            return data
    raise Exception("Static file not found: %s" % path)


def write_static_data(path, data):
    print("write_static_data", path)
    dirname = os.path.join("static", os.path.dirname(path))
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    open(os.path.join("static", path), "wb").write(data)


def get_theme_static_data(theme_name, path):
    print("get_theme_static_data", theme_name, path)
    db = database.get_connection()
    if not db:
        return None
    res = db.get("SELECT file FROM cms_theme WHERE name=%s", theme_name)
    if not res:
        return None
    if res.file:
        zip_path = utils.get_file_path(res.file)
        zip_data = open(zip_path, "rb").read()
        f = BytesIO(zip_data)
        zf = zipfile.ZipFile(f)
        try:
            data = zf.read("static/" + path)
            return data
        except:
            return None
    else:
        data = module.read_module_file("themes/" + theme_name + "/static/" + path)
        if data:
            return data
    return None


class StaticHandler(tornado.web.StaticFileHandler):

    def get(self, path, **kwargs):
        try:
            mime_type, encoding = mimetypes.guess_type(path)
            self.set_header("Content-Type", mime_type)
            data = get_static_data(path,self.request)
            self.write(data)
        except Exception as e:
            print("ERROR: failed to get static file (%s)" % path)
            import traceback
            traceback.print_exc()

    def compute_etag(self):  # XXX
        return None


def export_file(m, f, root=None):  # XXX: deprecated
    #print("XXX export_file",m,f,root)
    path = os.path.join(root, f) if root else f
    if pkg_resources.resource_isdir(m, path):
        if not os.path.exists(path):
            os.mkdir(path)
        for f in pkg_resources.resource_listdir(m, path):
            if not f:
                continue
            export_file(m, f, path)
    else:
        print("  " + path)
        data = pkg_resources.resource_string(m, path)
        open(path, "wb").write(data)


def export_static():  # XXX: deprecated
    loaded_modules = module.get_loaded_modules()
    for m in loaded_modules:
        print(m)
        if not pkg_resources.resource_exists(m, "static"):
            continue
        export_file(m, "static")


def export_module_file(m, mod_path, fs_path):
    print("export_module_file", m, mod_path, fs_path)
    if pkg_resources.resource_isdir(m, mod_path):
        print("dir")
        if not os.path.exists(fs_path):
            os.makedirs(fs_path)
        for f in pkg_resources.resource_listdir(m, mod_path):
            if not f:
                continue
            export_module_file(m, mod_path + "/" + f, fs_path + "/" + f)
    else:
        print("file")
        data = pkg_resources.resource_string(m, mod_path)
        open(fs_path, "wb").write(data)


def export_module_file_all(mod_path, fs_path):
    print("export_module_file_all", mod_path, fs_path)
    loaded_modules = module.get_loaded_modules()
    for m in loaded_modules:
        if not pkg_resources.resource_exists(m, mod_path):
            continue
        export_module_file(m, mod_path, fs_path)

_css_file = None
_js_file = None


def get_css_file():
    return _css_file


def get_js_file():
    return _js_file


def clear_js():
    print("clear_js")
    global js_hash
    js_hash = None


def make_js(minify=False):
    print("building js...")
    global _js_file
    data = []
    loaded_modules = module.get_loaded_modules()
    for m in loaded_modules:
        if pkg_resources.resource_exists(m, "js"):
            for fname in sorted(pkg_resources.resource_listdir(m, "js")):
                if not fname.endswith("js"):
                    continue
                try:
                    res = pkg_resources.resource_string(m, "js/"+fname).decode("utf-8")
                except:
                    raise Exception("Failed to load file %s"%fname)
                data.append(res)
        if pkg_resources.resource_exists(m, "views"): # XXX: merge this with js dir?
            for fname in sorted(pkg_resources.resource_listdir(m, "views")):
                if not fname.endswith("js"):
                    continue
                res = pkg_resources.resource_string(m, "views/"+fname).decode("utf-8")
                data.append(res)
    print("  %d js files loaded"%len(data))
    if data:
        buf = ("\n".join(data)).encode("utf-8")
        m = hashlib.new("md5")
        m.update(buf)
        h = m.hexdigest()[:8]
        if not os.path.exists("static/js"):
            os.makedirs("static/js")
        open("static/js/netforce-%s.js"%h, "wb").write(buf)
        if minify:
            if not os.path.exists("static/js/netforce-%s-min.js"%h):
                print("  minifying js...")
                #os.system("closure static/js/netforce-%s.js > static/js/netforce-%s-min.js" %(h,h))
                os.system("yui-compressor --type js static/js/netforce-%s.js > static/js/netforce-%s-min.js" %(h,h))
            _js_file="netforce-%s-min.js"%h
        else:    
            _js_file="netforce-%s.js"%h
        print("  => static/js/%s" % _js_file)

def make_css(minify=False):
    print("building css...")
    global _css_file
    data = []
    loaded_modules = module.get_loaded_modules()
    for m in loaded_modules:
        if not pkg_resources.resource_exists(m, "css"):
            continue
        for fname in sorted(pkg_resources.resource_listdir(m, "css")):
            if not fname.endswith("css"):
                continue
            res = pkg_resources.resource_string(m, "css/"+fname).decode("utf-8")
            data.append(res)
    print("  %d css files loaded"%len(data))
    if data:
        buf = ("\n".join(data)).encode("utf-8")
        m = hashlib.new("md5")
        m.update(buf)
        h = m.hexdigest()[:8]
        if not os.path.exists("static/css"):
            os.makedirs("static/css")
        open("static/css/netforce-%s.css"%h, "wb").write(buf)
        if minify:
            if not os.path.exists("static/css/netforce-%s-min.css"%h):
                print("  minifying css...")
                os.system("yui-compressor --type css static/css/netforce-%s.css > static/css/netforce-%s-min.css" %(h,h))
            _css_file="netforce-%s-min.css"%h
        else:    
            _css_file="netforce-%s.css"%h
        print("  => static/css/%s" % _css_file)


def make_ui_params():
    print("building ui_params...")
    data = {}
    data["version"] = netforce.get_module_version()
    data["models"] = model.models_to_json()
    data["actions"] = action.actions_to_json()
    data["layouts"] = layout.layouts_to_json()
    data["templates"] = template.templates_to_json()
    if data:
        if not os.path.exists("static"):
            os.makedirs("static")
        print("  => static/ui_params.json")
        s = json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))
        open("static/ui_params.json", "w").write(s)


def check_ui_params_db():
    dbname = database.get_active_db()
    if not dbname:
        return ""
    res = glob.glob("static/db/%s/ui_params_db.json" % dbname)
    if not res:
        make_ui_params_db()


def make_ui_params_db():
    print("building ui_params_db...")
    user_id = get_active_user()
    set_active_user(1)
    try:
        data = {}
        data["active_languages"] = get_model("language").get_active_langs()
        trans = {}
        db = database.get_connection()
        res = db.query("SELECT l.code,t.original,t.translation FROM translation t JOIN language l ON l.id=t.lang_id")
        for r in res:
            trans.setdefault(r.code, {})[r.original] = r.translation
        data["translations"] = trans
        settings = get_model("settings").browse(1)
        data["date_format"] = settings.date_format or "YYYY-MM-DD"
        data["use_buddhist_date"] = settings.use_buddhist_date and True or False
        res = db.query("SELECT action FROM inline_help")
        data["inline_help"] = {r.action: True for r in res}
        data["layouts"] = get_model("view.layout").layouts_to_json()
        data["actions"] = get_model("action").actions_to_json()
        data["menu_icon"] = settings.menu_icon
        dbname = database.get_active_db()
        if not os.path.exists("static/db/%s" % dbname):
            os.makedirs("static/db/%s" % dbname)
        s = json.dumps(data, sort_keys=True, indent=4, separators=(',', ': '))
        print("  => static/db/%s/ui_params_db.json" % dbname)
        open("static/db/%s/ui_params_db.json" % dbname, "w").write(s)
    finally:
        set_active_user(user_id)


def clear_translations():
    print("clear_translations")
    dbname = database.get_active_db()
    res = glob.glob("static/db/%s/ui_params_db.json" % dbname)
    for f in res:
        os.remove(f)
