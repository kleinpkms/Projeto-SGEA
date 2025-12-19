import sqlite3, urllib.request, json, time

db='db.sqlite3'
conn=sqlite3.connect(db)
row=conn.execute('select key from authtoken_token where user_id=(select id from auth_user where username=?)',('apitest',)).fetchone()
if not row:
    print('NO_TOKEN')
    raise SystemExit(1)
token=row[0]
url='http://127.0.0.1:8000/api/eventos/'
headers={'Authorization':'Token '+token, 'Accept':'application/json'}

for i in range(1,23):
    req=urllib.request.Request(url, headers=headers, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            status=r.getcode()
            data=r.read().decode('utf-8')
            print(f"{i} => {status}")
    except urllib.error.HTTPError as e:
        print(f"{i} => {e.code} {e.reason}")
    except Exception as e:
        print(f"{i} => ERROR {e}")
    time.sleep(0.2)
