import sqlite3
conn = sqlite3.connect('db.sqlite3')
cur = conn.cursor()
cur.execute("PRAGMA table_info('core_inscricao')")
cols = cur.fetchall()
for c in cols:
    print(c)
conn.close()
