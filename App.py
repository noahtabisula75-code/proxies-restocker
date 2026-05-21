from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import os

app = Flask(__name__)
DATABASE = 'proxies.db'

# ------------------- Database -------------------
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS proxies
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  proxy_string TEXT NOT NULL,
                  active INTEGER DEFAULT 1,
                  fail_count INTEGER DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# ------------------- Dashboard -------------------
@app.route('/')
def index():
    conn = get_db()
    proxies = conn.execute('SELECT * FROM proxies ORDER BY active DESC, id DESC').fetchall()
    conn.close()
    return render_template('index.html', proxies=proxies)

@app.route('/add', methods=['POST'])
def add_proxy():
    proxy = request.form.get('proxy', '').strip()
    if proxy and proxy.count(':') == 3:   # host:port:user:pass
        conn = get_db()
        conn.execute('INSERT INTO proxies (proxy_string) VALUES (?)', (proxy,))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return redirect(url_for('index', error='invalid'))

@app.route('/delete/<int:proxy_id>')
def delete_proxy(proxy_id):
    conn = get_db()
    conn.execute('DELETE FROM proxies WHERE id = ?', (proxy_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/toggle/<int:proxy_id>')
def toggle_proxy(proxy_id):
    conn = get_db()
    proxy = conn.execute('SELECT active FROM proxies WHERE id = ?', (proxy_id,)).fetchone()
    if proxy:
        new_status = 0 if proxy['active'] else 1
        conn.execute('UPDATE proxies SET active = ? WHERE id = ?', (new_status, proxy_id))
        conn.commit()
    conn.close()
    return redirect(url_for('index'))

# ------------------- API for your checker -------------------
@app.route('/api/proxy')
def get_proxy():
    conn = get_db()
    proxies = conn.execute(
        'SELECT proxy_string FROM proxies WHERE active = 1 ORDER BY RANDOM() LIMIT 1'
    ).fetchall()
    conn.close()
    if proxies:
        return jsonify({'proxy': proxies[0]['proxy_string']})
    return jsonify({'error': 'No active proxies available'}), 404

@app.route('/api/proxy/block', methods=['POST'])
def block_proxy():
    data = request.get_json()
    proxy_str = data.get('proxy', '') if data else ''
    if not proxy_str:
        return jsonify({'error': 'No proxy string provided'}), 400
    conn = get_db()
    conn.execute('UPDATE proxies SET active = 0 WHERE proxy_string = ?', (proxy_str,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'blocked'})

@app.route('/api/proxy/list')
def list_proxies():
    conn = get_db()
    rows = conn.execute('SELECT * FROM proxies ORDER BY id DESC').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/stats')
def stats():
    conn = get_db()
    total = conn.execute('SELECT COUNT(*) FROM proxies').fetchone()[0]
    active = conn.execute('SELECT COUNT(*) FROM proxies WHERE active=1').fetchone()[0]
    blocked = total - active
    conn.close()
    return jsonify({'total': total, 'active': active, 'blocked': blocked})

# ------------------- Main -------------------
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
