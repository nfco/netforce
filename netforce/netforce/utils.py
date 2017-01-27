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

import urllib.parse
import pkg_resources
import tempfile
from netforce import database
import os
import random
import string
import json
import hmac
import hashlib
import base64
import time
import sys
from struct import Struct
from operator import xor
from itertools import starmap
import binascii
import signal
import platform
import re
import math
import decimal
import calendar

try:
    import dns.resolver
    HAS_DNS = True
except:
    HAS_DNS = False
from . import config
import xmlrpc.client


def get_data_path(data, path, default=None, parent=False):
    if not path:
        return data
    val = data
    fields = path.split(".")
    if parent:
        fields = fields[:-1]
    for field in fields:
        if not field.isdigit():
            if not isinstance(val, dict):
                return default
            val = val.get(field, default)
        else:
            ind = int(field)
            if not isinstance(val, list) or ind >= len(val):
                return default
            val = val[ind]
    return val


def set_data_path(data, path, val):
    fields = path.split(".")
    if data is None:
        if not fields[0].isdigit() and fields[0] != "[]":
            data = {}
        else:
            data = []
    obj = data
    for i, field in enumerate(fields):
        if i < len(fields) - 1:
            next_field = fields[i + 1]
            if not next_field.isdigit() and next_field != "[]":
                v = {}
            else:
                v = []
            last = False
        else:
            v = val
            last = True
        if not field.isdigit() and field != "[]":
            if last:
                obj[field] = v
            else:
                obj = obj.setdefault(field, v)
        else:
            if field == "[]":
                obj.append(v)
            else:
                ind = int(field)
                while len(obj) <= ind:
                    obj.append(None)
                if last:
                    obj[ind] = v
                else:
                    if obj[ind] is None:
                        obj[ind] = v
                    obj = obj[ind]
    return data


def is_sub_url(url, base_url):
    o1 = urllib.parse.urlparse(base_url)
    o2 = urllib.parse.urlparse(url)
    if o2.path != o1.path:
        return False
    q1 = urllib.parse.parse_qs(o1.query)
    q2 = urllib.parse.parse_qs(o2.query)
    for k, v1 in q1.items():
        v2 = q2.get(k)
        if v2 != v1:
            return False
    return True

def get_ip_country(ip): # TODO: remove this
    return None

def rmdup(seq):
    seen = set()
    seen_add = seen.add
    return [x for x in seq if x not in seen and not seen_add(x)]


def get_file_path(fname):
    if not fname:
        return None
    dbname = database.get_active_db()
    if not dbname:
        return None
    path = os.path.join(os.getcwd(), "static", "db", dbname, "files", fname)
    return path


def gen_passwd(n=8, numeric=False):
    if numeric:
        chars = string.digits
    else:
        chars = string.ascii_letters + string.digits
    return "".join([random.choice(chars) for i in range(n)])


def eval_json(expr, ctx):
    def _eval_var(name):
        if name in ("true", "false", "null"):
            return name
        comps = name.split(".")
        v = ctx
        for n in comps:
            v = v.get(n)
            if not isinstance(v, dict):
                return v
        return v
    chunks = []
    state = "other"
    start = 0
    for i, c in enumerate(expr):
        if state == "other":
            if c == "\"":
                state = "string"
            elif c.isalpha() or c == "_":
                chunks.append(expr[start:i])
                state = "var"
                start = i
        elif state == "string":
            if c == "\"":
                state = "other"
            elif c == "\\":
                state = "escape"
        elif state == "escape":
            state = "string"
        elif state == "var":
            if not c.isalnum() and c != "_" and c != ".":
                n = expr[start:i].strip()
                v = _eval_var(n)
                if v is None:
                    s="null"
                else:
                    s=str(v)
                chunks.append(s)
                state = "other"
                start = i
    chunks.append(expr[start:])
    data = "".join(chunks)
    return json.loads(data)

_UTF8_TYPES = (bytes, type(None))


def utf8(value):
    if isinstance(value, _UTF8_TYPES):
        return value
    assert isinstance(value, str)
    return value.encode("utf-8")

_TO_UNICODE_TYPES = (str, type(None))


def to_unicode(value):
    if isinstance(value, _TO_UNICODE_TYPES):
        return value
    assert isinstance(value, bytes)
    return value.decode("utf-8")


def _create_signature(secret, *parts):
    hash = hmac.new(utf8(secret), digestmod=hashlib.sha1)
    for part in parts:
        hash.update(utf8(part))
    return utf8(hash.hexdigest())


def _time_independent_equals(a, b):
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= x ^ y
    return result == 0


def _decode_signed_value(secret, name, value, max_age_days=31):
    if not value:
        return None
    parts = utf8(value).split(b"|")
    if len(parts) != 3:
        return None
    signature = _create_signature(secret, name, parts[0], parts[1])
    if not _time_independent_equals(parts[2], signature):
        print("WARNING: Invalid cookie signature %r" % value)
        return None
    timestamp = int(parts[1])
    if timestamp < time.time() - max_age_days * 86400:
        print("WARNING: Expired cookie %r" % value)
        return None
    if timestamp > time.time() + 31 * 86400:
        # _cookie_signature does not hash a delimiter between the
        # parts of the cookie, so an attacker could transfer trailing
        # digits from the payload to the timestamp without altering the
        # signature.  For backwards compatibility, sanity-check timestamp
        # here instead of modifying _cookie_signature.
        print("WARNING: Cookie timestamp in future; possible tampering %r" % value)
        return None
    if parts[1].startswith(b"0"):
        print("WARNING: Tampered cookie %r" % value)
    try:
        return base64.b64decode(parts[0])
    except Exception:
        return None


def _create_signed_value(secret, name, value):
    timestamp = utf8(str(int(time.time())))
    value = base64.b64encode(utf8(value))
    signature = _create_signature(secret, name, value, timestamp)
    value = b"|".join([value, timestamp, signature])
    return value

_token_secret=None

def get_token_secret():
    global _token_secret
    if _token_secret is not None:
        return _token_secret
    path=".token_secret"
    if os.path.exists(path):
        _token_secret=open(path).read()
    else:
        _token_secret=gen_passwd(20)
        open(path,"w").write(_token_secret)
    return _token_secret

def new_token(dbname, user_id):
    user = "%s %s" % (dbname, user_id)
    secret=get_token_secret()
    token = to_unicode(_create_signed_value(secret, "user", user))
    return token


def check_token(dbname, user_id, token):
    # print("check_token",dbname,user_id,token)
    user = "%s %s" % (dbname, user_id)
    secret=get_token_secret()
    val = to_unicode(_decode_signed_value(secret, "user", token))
    return val == user


def url_escape(value):
    return urllib.parse.quote_plus(utf8(value))


def url_unescape(value, encoding='utf-8'):  # XXX: check tornado
    return urllib.parse.unquote_plus(value, encoding=encoding)


def format_color(msg, color=None, bright=False):
    color_codes = {
        "black": 0,
        "red": 1,
        "green": 2,
        "yellow": 3,
        "blue": 4,
        "magenta": 5,
        "cyan": 6,
        "white": 7,
    }
    code = color_codes.get(color, 7)
    head = "\x1b[3%dm" % code
    if bright:
        head += "\x1b[1m"
    foot = "\x1b[39;49m"
    if bright:
        foot += "\x1b[22m"
    return head + msg + foot


def print_color(msg, color=None, bright=False):
    if sys.stdout.isatty():
        msg = format_color(msg, color=color, bright=bright)
    print(msg)


def compare_version(v1, v2):
    v1_ = [int(d) for d in v1.split(".")]
    v2_ = [int(d) for d in v2.split(".")]
    if v1_ < v2_:
        return -1
    if v1_ > v2_:
        return 1
    return 0


def get_db_version():
    db = database.get_connection()
    res = db.get("SELECT * FROM pg_class WHERE relname='settings'")
    if not res:
        return None
    res = db.get("SELECT * FROM settings WHERE id=1")
    if not res:
        return None
    return res.version


def set_db_version(version):
    db = database.get_connection()
    res = db.get("SELECT * FROM pg_class WHERE relname='settings'")
    if not res:
        raise Exception("Missing settings table")
    res = db.get("SELECT * FROM settings WHERE id=1")
    if not res:
        raise Exception("Missing settings record")
    db.execute("UPDATE settings SET version=%s WHERE id=1", version)


def is_empty_db():
    db = database.get_connection()
    res = db.get("SELECT * FROM pg_class WHERE relname='settings'")
    if not res:
        return True
    res = db.get("SELECT * FROM settings WHERE id=1")
    if not res:
        return True
    return False

def init_db():
    db = database.get_connection()
    db.execute("INSERT INTO settings (id) VALUES (1)")
    enc_pass=encrypt_password('1234')
    db.execute("INSERT INTO profile (id,name,code,active,default_model_perms) VALUES (1,'System Admin','ADMIN',true,'full')")
    db.execute("INSERT INTO base_user (id,login,password,name,profile_id,active) VALUES (1,'admin',%s,'Admin',1,true)",enc_pass)
    db.execute("INSERT INTO company (id,name) VALUES (1,'Test Company')")

    db.execute("ALTER SEQUENCE settings_id_seq RESTART WITH 2")
    db.execute("ALTER SEQUENCE base_user_id_seq RESTART WITH 2")
    db.execute("ALTER SEQUENCE company_id_seq RESTART WITH 2")
    db.execute("ALTER SEQUENCE profile_id_seq RESTART WITH 2")

_pack_int = Struct('>I').pack


def pbkdf2_hex(data, salt, iterations=1000, keylen=24, hashfunc=None):
    return binascii.hexlify(pbkdf2_bin(data, salt, iterations, keylen, hashfunc)).decode()


def pbkdf2_bin(data, salt, iterations=1000, keylen=24, hashfunc=None):
    if isinstance(data, str):
        data = data.encode("utf-8")
    if isinstance(salt, str):
        salt = salt.encode("utf-8")
    hashfunc = hashfunc or hashlib.sha1
    mac = hmac.new(data, None, hashfunc)

    def _pseudorandom(x, mac=mac):
        h = mac.copy()
        h.update(x)
        return h.digest()
    buf = []
    for block in range(1, -(-keylen // mac.digest_size) + 1):
        rv = u = _pseudorandom(salt + _pack_int(block))
        for i in range(iterations - 1):
            u = _pseudorandom(u)
            rv = starmap(xor, zip(rv, u))
        buf.extend(rv)
    return bytes(buf[:keylen])


def encrypt_password(password):
    algo = "pbkdf2"
    salt = binascii.hexlify(os.urandom(8)).decode()
    hsh = pbkdf2_hex(password, salt)
    return "%s$%s$%s" % (algo, salt, hsh)


def check_password(password, enc_password):
    master_pwd = config.get("master_password")
    if master_pwd and password == master_pwd:
        return True
    if not password or not enc_password:
        return False
    algo, salt, hsh = enc_password.split("$")
    if algo != "pbkdf2":
        raise Exception("Unknown password encryption algorithm")
    hsh2 = pbkdf2_hex(password, salt)
    return hsh2 == hsh


class timeout:  # XXX: doesn't seem to work yet... (some jsonrpc requests take more than 5min)

    def __init__(self, seconds=None):
        self.seconds = seconds

    def handle_timeout(self, signum, frame):
        raise Exception("Timeout!")

    def __enter__(self):
        if self.seconds and platform.system() != "Windows":
            signal.signal(signal.SIGALRM, self.handle_timeout)
            signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        if self.seconds and platform.system() != "Windows":
            signal.alarm(0)


def get_email_domain(email_addr):
    s = email_addr.strip()
    domain = s[s.find('@') + 1:].lower()
    return domain


def get_mx_records(domain):
    if not HAS_DNS:
        raise Exception("dnspython library not installed")
    try:
        res = dns.resolver.query(domain, "MX")
    except:
        return None
    records = sorted([(int(r.preference), str(r.exchange)) for r in res])
    return records

WSP = r'[ \t]'                                       # see 2.2.2. Structured Header Field Bodies
CRLF = r'(?:\r\n)'                                   # see 2.2.3. Long Header Fields
NO_WS_CTL = r'\x01-\x08\x0b\x0c\x0f-\x1f\x7f'        # see 3.2.1. Primitive Tokens
QUOTED_PAIR = r'(?:\\.)'                             # see 3.2.2. Quoted characters
FWS = r'(?:(?:' + WSP + r'*' + CRLF + r')?' + \
      WSP + r'+)'                                    # see 3.2.3. Folding white space and comments
CTEXT = r'[' + NO_WS_CTL + \
        r'\x21-\x27\x2a-\x5b\x5d-\x7e]'              # see 3.2.3
CCONTENT = r'(?:' + CTEXT + r'|' + \
           QUOTED_PAIR + r')'                        # see 3.2.3 (NB: The RFC includes COMMENT here
# as well, but that would be circular.)
COMMENT = r'\((?:' + FWS + r'?' + CCONTENT + \
          r')*' + FWS + r'?\)'                       # see 3.2.3
CFWS = r'(?:' + FWS + r'?' + COMMENT + ')*(?:' + \
       FWS + '?' + COMMENT + '|' + FWS + ')'         # see 3.2.3
ATEXT = r'[\w!#$%&\'\*\+\-/=\?\^`\{\|\}~]'           # see 3.2.4. Atom
ATOM = CFWS + r'?' + ATEXT + r'+' + CFWS + r'?'      # see 3.2.4
DOT_ATOM_TEXT = ATEXT + r'+(?:\.' + ATEXT + r'+)*'   # see 3.2.4
DOT_ATOM = CFWS + r'?' + DOT_ATOM_TEXT + CFWS + r'?'  # see 3.2.4
QTEXT = r'[' + NO_WS_CTL + \
        r'\x21\x23-\x5b\x5d-\x7e]'                   # see 3.2.5. Quoted strings
QCONTENT = r'(?:' + QTEXT + r'|' + \
           QUOTED_PAIR + r')'                        # see 3.2.5
QUOTED_STRING = CFWS + r'?' + r'"(?:' + FWS + \
    r'?' + QCONTENT + r')*' + FWS + \
    r'?' + r'"' + CFWS + r'?'
LOCAL_PART = r'(?:' + DOT_ATOM + r'|' + \
             QUOTED_STRING + r')'                    # see 3.4.1. Addr-spec specification
DTEXT = r'[' + NO_WS_CTL + r'\x21-\x5a\x5e-\x7e]'    # see 3.4.1
DCONTENT = r'(?:' + DTEXT + r'|' + \
           QUOTED_PAIR + r')'                        # see 3.4.1
DOMAIN_LITERAL = CFWS + r'?' + r'\[' + \
    r'(?:' + FWS + r'?' + DCONTENT + \
    r')*' + FWS + r'?\]' + CFWS + r'?'  # see 3.4.1
DOMAIN = r'(?:' + DOT_ATOM + r'|' + \
         DOMAIN_LITERAL + r')'                       # see 3.4.1
ADDR_SPEC = LOCAL_PART + r'@' + DOMAIN               # see 3.4.1

# A valid address will match exactly the 3.4.1 addr-spec.
VALID_ADDRESS_REGEXP = '^' + ADDR_SPEC + '$'


def check_email_syntax(email_addr):
    m = re.match(VALID_ADDRESS_REGEXP, email_addr)
    if not m:
        return False
    return True


def round_amount(amt, rounding, method="nearest"):
    if not rounding:
        return amt
    if method == "nearest":
        i = round((amt + 0.000001) / rounding)
    elif method == "lower":
        i = math.floor(amt / rounding)
    elif method == "upper":
        i = math.ceil(amt / rounding)
    else:
        raise Exception("Invalid rounding method")
    return i * rounding

def decimal_default(obj):
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    raise TypeError

def json_dumps(val):
    return json.dumps(val, default=decimal_default)

def json_loads(s):
    return json.loads(s, parse_float=decimal.Decimal)

class XmlRpcCookieTransport(xmlrpc.client.Transport):
    def __init__(self):
        super().__init__()
        self._cookies = []

    def send_headers(self, connection, headers):
        if self._cookies:
            connection.putheader("Cookie", "; ".join(self._cookies))
        print("cookies",self._cookies)
        super().send_headers(connection, headers)

    def parse_response(self, response):
        for header in response.msg.get_all("Set-Cookie") or []:
            cookie = header.split(";", 1)[0]
            self._cookies.append(cookie)
        return super().parse_response(response)

def create_thumbnails(fname):
    print("create_thumbnails",fname)
    dbname = database.get_active_db()
    if not dbname:
        return None
    fdir = os.path.join(os.getcwd(), "static", "db", dbname, "files")
    path=os.path.join(fdir,fname)
    basename,ext=os.path.splitext(fname)
    for s in [512,256,128,64,32]:
        fname_thumb = basename + "-resize-%s"%s + ext
        path_thumb = os.path.join(fdir, fname_thumb)
        print("path_thumb",path_thumb)
        os.system(r"convert -resize %sx%s\> '%s' '%s'" % (s,s,path, path_thumb))

def get_last_day(month):
    if isinstance(month,str):
        cal_year=int(month[0:4])
        cal_month=int(month[5:7])
        last_day=calendar.monthrange(cal_year,cal_month)[1]
        return last_day


currency={ 'th_TH': {'name': 'บาท',  'partial': 'สตางค์',  'end': 'ถ้วน'}
           , 'en_US': {'name': 'BAHT', 'partial': 'SATANG', 'end': 'ONLY'}
           }
sym={
    "en_US": {
        "positive": "",
        "negative": "MINUS",
        "sep": " ",
        "0": "ZERO",
        "x": ["ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE"],
        "1x": ["TEN", "ELEVEN", "TWELVE", "THIRTEEN", "FOURTEEN", "FIFTEEN", "SIXTEEN", "SEVENTEEN", "EIGHTEEN", "NINETEEN"],
        "x0": ["TWENTY", "THIRTY", "FORTY", "FIFTY", "SIXTY", "SEVENTY", "EIGHTY", "NINETY"],
        "100": "HUNDRED",
        "1K": "THOUSAND",
        "1M": "MILLION",
        "and": "AND",
    },
    "th_TH": {
        "positive": "",
        "negative": "ลบ",
        "sep": "",
        "0": "ศูนย์",
        "x": ["หนึ่ง","สอง","สาม","สี่","ห้า","หก","เจ็ด","แปด","เก้า"],
        "x0": ["สิบ","ยี่สิบ","สามสิบ","สี่สิบ","ห้าสิบ","หกสิบ","เจ็ดสิบ","แปดสิบ","เก้าสิบ"],
        "x1": "เอ็ด",
        "100": "ร้อย",
        "1K": "พัน",
        "10K": "หมื่น",
        "100K": "แสน",
        "1M": "ล้าน",
        "and": "",
    }
}

def _num2word(n,l="en_US"):
    number=n
    if number==0:
        return sym[l]["0"] + ""
    elif number<10:
        return sym[l]["x"][number-1]
    elif number<100:
        if l=="en_US":
            if number<20:
                return sym[l]["1x"][number-10]
            else:
                return sym[l]["x0"][int(number/10-2)]+(number%10 and sym[l]["sep"]+_num2word(number%10,l) or "")
        elif l=="th_TH":
            return sym[l]["x0"][int(number/10-1)]+(number%10 and (number%10==1 and sym[l]["x1"] or sym[l]["x"][number%10-1]) or "")
    elif number<1000:
        return sym[l]["x"][int(number/100-1)]+sym[l]["sep"]+sym[l]["100"]+(number%100 and sym[l]["sep"]+_num2word(number%100,l) or "")

    elif number<1000000:
        if l=="en_US":
            return _num2word(int(number/1000),l)+sym[l]["sep"]+sym[l]["1K"]+(number%1000 and sym[l]["sep"]+_num2word(number%1000,l) or "")
        elif l=="th_TH":
            if number<10000:
                return sym[l]["x"][int(number/1000-1)]+sym[l]["1K"]+(number%1000 and _num2word(number%1000,l) or "")
            elif number<100000:
                return sym[l]["x"][int(number/10000-1)]+sym[l]["10K"]+(number%10000 and _num2word(number%10000,l) or "")
            else:
                return sym[l]["x"][int(number/100000-1)]+sym[l]["100K"]+(number%100000 and _num2word(number%100000,l) or "")
    elif number<1000000000:
        return _num2word(int(number/1000000),l)+sym[l]["sep"]+sym[l]["1M"]+sym[l]["sep"]+(number%1000000 and _num2word(number%1000000,l) or "")
    else:
        return "N/A"

def num2word(n,l="th_TH"):
    '''
        >>> num2word(-666, 'en_US')
        'MINUS SIX HUNDRED SIXTY SIX BAHT ONLY'

        >>> print num2word(-1024, 'th_TH')
        ลบหนึ่งพันยี่สิบสี่บาทถ้วน

        >>> num2word(42.00, 'en_US')
        'FORTY TWO BAHT ONLY'

        >>> print num2word(42.00, 'th_TH')
        สี่สิบสองบาทถ้วน

        >>> num2word(29348.23, 'en_US')
        'TWENTY NINE THOUSAND THREE HUNDRED FORTY EIGHT BAHT AND TWENTY THREE SATANG'

        >>> print num2word(29348.23, 'th_TH')
        สองหมื่นเก้าพันสามร้อยสี่สิบแปดบาทยี่สิบสามสตางค์

        >>> num2word(293812913.12, 'en_US')
        'TWO HUNDRED NINETY THREE MILLION EIGHT HUNDRED TWELVE THOUSAND NINE HUNDRED THIRTEEN BAHT AND TWELVE SATANG'

        >>> print num2word(293812913.12, 'th_TH')
        สองร้อยเก้าสิบสามล้านแปดแสนหนึ่งหมื่นสองพันเก้าร้อยสิบสามบาทสิบสองสตางค์

        >>> print num2word(0.0, 'th_TH')
        ศูนย์บาทถ้วน

        >>> print num2word(0.75, 'th_TH')
        เจ็ดสิบห้าสตางค์
    '''

    base=0
    end=0
    number = n
    if type(n)  in (type(''),decimal.Decimal):
        number=float(n)
    word = ''
    if type(number) in (int, float):
        sign = 'positive' if number >= 0 else 'negative'
        number = abs(number)
        number = ('%.2f'%number).split('.')
        base = _num2word(int(number[0]),l=l) if int(number[0]) > 0 else 0
        if int(number[1])!=0:
            end = _num2word(int(number[1]),l=l)
        if base != 0 and end == 0:
            word = sym[l][sign] + sym[l]['sep'] + base + sym[l]['sep'] + currency[l]['name'] + sym[l]['sep'] + currency[l]['end']
        if base != 0 and end != 0:
            word = sym[l][sign] + sym[l]['sep'] + base + sym[l]['sep'] + currency[l]['name'] + sym[l]['sep'] + sym[l]['and'] + sym[l]['sep'] + end+sym[l]['sep'] + currency[l]['partial']
        if base == 0 and end != 0:
            word = sym[l][sign] + sym[l]['sep'] + sym[l]['and'] + sym[l]['sep'] + end+sym[l]['sep'] + currency[l]['partial']
        if base == 0 and end == 0:
            base = _num2word(0.00,l=l)
            word = sym[l][sign] + sym[l]['sep'] + base + sym[l]['sep'] + currency[l]['name'] + sym[l]['sep'] + currency[l]['end']
    return word.strip()

def get_last_day(month):
    if isinstance(month,str):
        cal_year=int(month[0:4])
        cal_month=int(month[5:7])
        last_day=calendar.monthrange(cal_year,cal_month)[1]
        return last_day

def date2thai(date, format='%(BY)s-%(m)s-%(d)s', lang='th_TH'):
    '''
        >>> date2thai('2011-12-31', lang='th_TH')
        '2554-12-31'
        >>> date2thai('2011-12-31', format='%(Td)s %(d)s %(Tm)s, %(By)s', lang='en_US')
        'Saturday 31 December, 54'
        >>> print date2thai('2011-12-31', format='%(Td)s %(d)s %(Tm)s, %(By)s', lang='th_TH')
        เสาร์ 31 ธันวาคม, 54
        >>> date2thai('2000-06-08', lang='th_TH')
        '2543-06-08'
        >>> date2thai('2000-06-08', format='%(Td)s %(d)s %(Tm)s, %(By)s', lang='en_US')
        'Thursday 08 June, 43'
        >>> print date2thai('2000-06-08', format='%(Td)s %(d)s %(Tm)s, %(By)s', lang='th_TH')
        พฤหัสบดี 08 มิถุนายน, 43
    '''

    if not date or not date.count('-') == 2:
        return ''

    year, month, day = date.split('-')

    #dow = DateTime.Date(int(year), int(month), int(day)).day_of_week
    dow = datetime(int(year),int(month),int(day)).weekday()

    return format % { 'BY': int(year) + 543
                    , 'By': int(year[2:]) + 43
                    , 'Tm': MONTHS[lang][int(month)]
                    , 'Td': DAYS[lang][dow]
                    , 'm':  month
                    , 'd':  day
                    }

def roundup(n,scale=2):
    if not n:
        return decimal.Decimal(n)
    if isinstance(n,decimal.Decimal):
        return decimal.Decimal(eval(('{:.%sf}'%scale).format(float(n)+0.00001)))
    else:
        return decimal.Decimal(eval(('{:.%sf}'%scale).format(n+0.00001)))
