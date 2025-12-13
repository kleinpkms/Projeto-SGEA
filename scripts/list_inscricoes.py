import sqlite3
conn = sqlite3.connect('db.sqlite3')
cur = conn.cursor()
cur.execute("select id, participante_id, evento_id, certificado_evento_nome from core_inscricao order by id desc limit 5")
for r in cur.fetchall():
    print(r)
conn.close()
