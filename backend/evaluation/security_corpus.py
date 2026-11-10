"""
Labelled code samples for measuring the security rules' precision and recall.

Each case: (case_id, expected CWE or None, Python source).
    expected CWE   the sample is vulnerable; detection = a finding with that CWE
    None           the sample is safe; any finding is a false alarm

Used by tests/test_metrics_security.py and evaluation/compare_security.py.
The samples cover taint flows (user input reaching a dangerous call),
pattern rules, and safe look-alikes that must NOT be flagged.
"""

from textwrap import dedent

ROUTE = "from fastapi import APIRouter, Depends, Request\nrouter = APIRouter()\n"

CASES = [
    # ── taint: user input reaches a dangerous call ──────────────────
    ("sql-fstring", 89, ROUTE + dedent('''
        @router.get("/users")
        async def find(name: str):
            cursor.execute(f"SELECT * FROM users WHERE name = '{name}'")
    ''')),
    ("sql-percent-variable", 89, ROUTE + dedent('''
        @router.get("/users")
        async def find(name: str):
            query = "SELECT * FROM users WHERE name = '%s'" % name
            cursor.execute(query)
    ''')),
    ("sql-branch-merge", 89, ROUTE + dedent('''
        @router.get("/users")
        async def find(name: str, exact: bool):
            if exact:
                query = "SELECT * FROM users WHERE name = '" + name + "'"
            else:
                query = "SELECT * FROM users"
            cursor.execute(query)
    ''')),
    ("sql-format", 89, ROUTE + dedent('''
        @router.post("/search")
        async def search(term: str):
            cursor.execute("SELECT * FROM t WHERE x = {}".format(term))
    ''')),
    ("sql-string-methods", 89, ROUTE + dedent('''
        @router.get("/users")
        async def find(name: str):
            cleaned = name.strip().lower()
            cursor.execute("SELECT * FROM users WHERE name = '" + cleaned + "'")
    ''')),
    ("sql-dict-item", 89, ROUTE + dedent('''
        @router.get("/users")
        async def find(name: str):
            data = {"q": name}
            cursor.execute(f"SELECT * FROM users WHERE name = '{data['q']}'")
    ''')),
    ("sql-body-attribute", 89, ROUTE + dedent('''
        @router.post("/users")
        async def create(body: UserIn):
            cursor.execute("INSERT INTO users VALUES ('" + body.name + "')")
    ''')),
    ("cmd-flask-args", 78, dedent('''
        from flask import Flask, request
        app = Flask(__name__)
        @app.route("/grep")
        def grep():
            pattern = request.args.get("q")
            os.system("grep " + pattern + " /var/log/app.log")
    ''')),
    ("cmd-subprocess-shell", 78, ROUTE + dedent('''
        @router.get("/ls")
        async def listing(path: str):
            subprocess.run(f"ls -la {path}", shell=True)
    ''')),
    ("cmd-loop", 78, ROUTE + dedent('''
        @router.post("/cleanup")
        async def cleanup(items: list):
            for item in items:
                command = "rm -rf " + item
                os.system(command)
    ''')),
    ("cmd-script-input", 78, dedent('''
        import os
        target = input("host? ")
        os.system("ping -c 1 " + target)
    ''')),
    ("eval-request-json", 95, ROUTE + dedent('''
        @router.post("/calc")
        async def calc(request: Request):
            payload = await request.json()
            return eval(payload["expr"])
    ''')),
    ("pickle-request-body", 502, ROUTE + dedent('''
        @router.post("/import")
        async def load(request: Request):
            return pickle.loads(await request.body())
    ''')),
    ("path-open", 22, ROUTE + dedent('''
        @router.get("/files")
        async def read(filename: str):
            with open("/srv/uploads/" + filename) as fh:
                return fh.read()
    ''')),
    ("path-pathlib", 22, ROUTE + dedent('''
        @router.get("/files")
        async def read(name: str):
            return Path(name).read_text()
    ''')),
    ("ssrf-requests", 918, ROUTE + dedent('''
        @router.get("/fetch")
        async def fetch(url: str):
            return requests.get(url).text
    ''')),
    ("ssti-template-string", 1336, dedent('''
        from flask import Flask, request, render_template_string
        app = Flask(__name__)
        @app.route("/hello")
        def hello():
            return render_template_string("<h1>" + request.args.get("name") + "</h1>")
    ''')),
    ("open-redirect", 601, ROUTE + dedent('''
        @router.get("/login/done")
        async def done(next_url: str):
            return RedirectResponse(next_url)
    ''')),
    ("mongo-where", 943, ROUTE + dedent('''
        @router.get("/users")
        async def find(name: str):
            return await col("users").find({"$where": f"this.name == '{name}'"}).to_list(10)
    ''')),
    ("mongo-regex", 943, ROUTE + dedent('''
        @router.get("/users")
        async def find(q: str):
            return await col("users").find({"name": {"$regex": q}}).to_list(10)
    ''')),
    ("redos-pattern", 1333, ROUTE + dedent('''
        @router.get("/match")
        async def match(pattern: str, text: str):
            return bool(re.search(pattern, text))
    ''')),
    # ── pattern rules: risky whatever the input ─────────────────────
    ("yaml-load", 502, "import yaml\nconfig = yaml.load(open('c.yml').read())\n"),
    ("tls-verify-false", 295, "import requests\nrequests.get('https://internal', verify=False)\n"),
    ("ssl-unverified", 295, "import ssl\nctx = ssl._create_unverified_context()\n"),
    ("md5-password", 327, "import hashlib\ndigest = hashlib.md5(password.encode()).hexdigest()\n"),
    ("random-token", 330, "import random, string\ntoken = ''.join(random.choice(string.ascii_letters) for _ in range(32))\n"),
    ("jwt-no-verify", 347, "import jwt\nclaims = jwt.decode(raw, options={'verify_signature': False})\n"),
    ("tempfile-mktemp", 377, "import tempfile\npath = tempfile.mktemp()\n"),
    ("debug-run", 489, "app.run(debug=True)\n"),
    ("shell-true-config", 78, "import subprocess\nsubprocess.call(settings.BACKUP_COMMAND, shell=True)\n"),
    ("sql-format-helper", 89, dedent('''
        def count_rows(cursor, table):
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
    ''')),
    ("pickle-file", 502, "import pickle\nwith open('model.pkl', 'rb') as fh:\n    model = pickle.load(fh)\n"),
    ("bind-all-interfaces", 605, "uvicorn.run(app, host='0.0.0.0', port=8000)\n"),
    # ── safe look-alikes: must not be flagged ───────────────────────
    ("safe-sql-parameterized", None, ROUTE + dedent('''
        @router.get("/users")
        async def find(name: str):
            cursor.execute("SELECT * FROM users WHERE name = %s", (name,))
    ''')),
    ("safe-subprocess-list", None, ROUTE + dedent('''
        @router.get("/ls")
        async def listing(path: str):
            subprocess.run(["ls", "-la", path])
    ''')),
    ("safe-yaml-safe-load", None, "import yaml\nconfig = yaml.safe_load(open('c.yml').read())\n"),
    ("safe-yaml-safe-loader", None, "import yaml\nconfig = yaml.load(raw, Loader=yaml.SafeLoader)\n"),
    ("safe-md5-checksum", None, "import hashlib\netag = hashlib.md5(body, usedforsecurity=False).hexdigest()\n"),
    ("safe-secrets-token", None, "import secrets\ntoken = secrets.token_urlsafe(32)\n"),
    ("safe-random-non-secret", None, "import random\ncolour = random.choice(['red', 'green'])\n"),
    ("safe-jwt-verified", None, "import jwt\nclaims = jwt.decode(raw, key, algorithms=['HS256'])\n"),
    ("safe-regex-escaped", None, ROUTE + dedent('''
        @router.get("/match")
        async def match(q: str, text: str):
            return bool(re.search(re.escape(q), text))
    ''')),
    ("safe-mongo-regex-escaped", None, ROUTE + dedent('''
        @router.get("/users")
        async def find(q: str):
            return await col("users").find({"name": {"$regex": re.escape(q), "$options": "i"}}).to_list(10)
    ''')),
    ("safe-fixed-host-url", None, ROUTE + dedent('''
        @router.get("/repo")
        async def repo(owner: str, name: str):
            return requests.get(f"https://api.github.com/repos/{owner}/{name}").json()
    ''')),
    ("safe-eval-constant", None, "result = eval('1 + 2')\n"),
    ("safe-depends-not-source", None, ROUTE + dedent('''
        @router.get("/me")
        async def me(user: dict = Depends(get_current_user)):
            with open(user["avatar_path"]) as fh:
                return fh.read()
    ''')),
    ("safe-reassigned", None, ROUTE + dedent('''
        @router.get("/report")
        async def report(name: str):
            name = "monthly.txt"
            with open(name) as fh:
                return fh.read()
    ''')),
    ("safe-int-sanitized", None, ROUTE + dedent('''
        @router.get("/page")
        async def page(n: str):
            index = int(n)
            with open("/srv/pages/" + str(index) + ".html") as fh:
                return fh.read()
    ''')),
    ("safe-basename", None, ROUTE + dedent('''
        @router.get("/files")
        async def read(filename: str):
            with open("/srv/uploads/" + os.path.basename(filename)) as fh:
                return fh.read()
    ''')),
    ("safe-redirect-constant", None, ROUTE + dedent('''
        @router.get("/logout")
        async def logout(user: dict = Depends(get_current_user)):
            return RedirectResponse("/login")
    ''')),
    ("safe-default-context", None, "import ssl\nctx = ssl.create_default_context()\n"),
    ("safe-localhost-bind", None, "uvicorn.run(app, host='127.0.0.1', port=8000)\n"),
]
