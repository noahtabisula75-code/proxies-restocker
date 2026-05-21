from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
import psycopg2
import psycopg2.extras

app = Flask(__name__)

# 🔧 Use DATABASE_URL environment variable (set on Render)
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set!")

# ------------------- Database helpers -------------------
def get_db():
    """Return a new database connection with RealDictCursor (dict-like rows)."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn

def init_db():
    """Create the proxies table if it doesn't exist."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS proxies (
                    id SERIAL PRIMARY KEY,
                    proxy_string TEXT NOT NULL,
                    active INTEGER DEFAULT 1,
                    fail_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')
        conn.commit()
    finally:
        conn.close()

# 🔧 Ensure table exists when module loads (before any request)
init_db()

# 🔧 Ensure templates folder exists
if not os.path.exists('templates'):
    os.makedirs('templates')

# ------------------- Dashboard -------------------
@app.route('/')
def index():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM proxies ORDER BY active DESC, id DESC')
            proxies = cur.fetchall()  # list of RealDictRow (works like dict)
    finally:
        conn.close()
    return render_template('index.html', proxies=proxies)

@app.route('/add', methods=['POST'])
def add_proxy():
    proxy = request.form.get('proxy', '').strip()
    if proxy and proxy.count(':') == 3:   # host:port:user:pass
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute('INSERT INTO proxies (proxy_string) VALUES (%s)', (proxy,))
            conn.commit()
        finally:
            conn.close()
        return redirect(url_for('index'))
    return redirect(url_for('index', error='invalid'))

@app.route('/delete/<int:proxy_id>')
def delete_proxy(proxy_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM proxies WHERE id = %s', (proxy_id,))
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for('index'))

@app.route('/toggle/<int:proxy_id>')
def toggle_proxy(proxy_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT active FROM proxies WHERE id = %s', (proxy_id,))
            proxy = cur.fetchone()
            if proxy:
                new_status = 0 if proxy['active'] else 1
                cur.execute('UPDATE proxies SET active = %s WHERE id = %s', (new_status, proxy_id))
                conn.commit()
    finally:
        conn.close()
    return redirect(url_for('index'))

# ------------------- API -------------------
@app.route('/api/proxy')
def get_proxy():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT proxy_string FROM proxies WHERE active = 1 ORDER BY RANDOM() LIMIT 1')
            row = cur.fetchone()
    finally:
        conn.close()
    if row:
        return jsonify({'proxy': row['proxy_string']})
    return jsonify({'error': 'No active proxies available'}), 404

@app.route('/api/proxy/block', methods=['POST'])
def block_proxy():
    data = request.get_json()
    proxy_str = data.get('proxy', '') if data else ''
    if not proxy_str:
        return jsonify({'error': 'No proxy string provided'}), 400
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE proxies SET active = 0 WHERE proxy_string = %s', (proxy_str,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'status': 'blocked'})

@app.route('/api/proxy/list')
def list_proxies():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM proxies ORDER BY id DESC')
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/stats')
def stats():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) as total FROM proxies')
            total = cur.fetchone()['total']
            cur.execute('SELECT COUNT(*) as active FROM proxies WHERE active = 1')
            active = cur.fetchone()['active']
    finally:
        conn.close()
    blocked = total - active
    return jsonify({'total': total, 'active': active, 'blocked': blocked})

# ------------------- Main -------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
