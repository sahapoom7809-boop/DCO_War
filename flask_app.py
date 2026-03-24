from flask import Flask, render_template, request, jsonify
import time
import random
import math
import threading

app = Flask(__name__)

# --- เวิลด์สเตทและพารามิเตอร์ของเวิลด์ ---
WORLD = { 'w': 4000, 'h': 3500 }
players_state = {}
shots_state = []

# --- ระบบหัวหน้า ( Global Bosses ) ---
bossProfiles = {
    "พี่ตุ๊": { 'radius': 35, 'speed': 3.2, 'color': "#d32f2f", 'text': "แจกงานด่วน!", 'stunTime': 15, 'rageMult': 2.0, 'seeThrough': False, 'vision': 650, 'canShoot': True, 'invisible': False, 'isSupreme': True }, 
    "พี่พงษ์": { 'radius': 30, 'speed': 3.5, 'color': "#1976d2", 'text': "แก้ตรงนี้นิดนึง", 'stunTime': 45, 'rageMult': 1.5, 'seeThrough': True, 'vision': 900, 'canShoot': False, 'invisible': False, 'isSupreme': False }, 
    
    # 🚨 อัปเกรดพี่เอ: เดินไว 3.8 / โกรธคูณ 1.5 / ยิงลูกซองแป้ง
    "พี่เอ": { 'radius': 55, 'speed': 3.8, 'color': "#388e3c", 'text': "เอาแป้งไปกิน!", 'stunTime': 0, 'rageMult': 1.5, 'seeThrough': False, 'vision': 700, 'canShoot': True, 'invisible': False, 'isSupreme': False }, 
    
    "พี่หนู": { 'radius': 25, 'speed': 2.6, 'color': "#e91e63", 'text': "แอบอยู่นี่เอง~", 'stunTime': 30, 'rageMult': 1.2, 'seeThrough': False, 'vision': 500, 'canShoot': False, 'invisible': True, 'isSupreme': False }, 
    "พี่โอ๋": { 'radius': 30, 'speed': 5.5, 'color': "#f57c00", 'text': "ด่วนๆๆ เอาเดี๋ยวนี้!", 'stunTime': 40, 'rageMult': 1.3, 'seeThrough': False, 'vision': 600, 'canShoot': False, 'invisible': False, 'isSupreme': False } 
}

bosses_state = []
last_tick_time = time.time()

def create_global_bosses():
    bosses_state.clear()
    for name, prof in bossProfiles.items():
        bosses_state.append({
            'name': "🕴️ " + name,
            'color': prof['color'],
            'radius': prof['radius'],
            'isSupreme': prof['isSupreme'],
            'invisible': prof['invisible'],
            'x': random.uniform(200, WORLD['w'] - 200),
            'y': random.uniform(200, WORLD['h'] - 200),
            'angle': random.uniform(0, math.pi * 2),
            'stunTimer': 0,
            'rageTimer': 0,
            'shootTimer': 0,
            'text': prof['text'],
            'textTimer': 90,
            'life': 999999,
            'profile': name
        })

create_global_bosses()

def tick_bosses():
    global last_tick_time, shots_state
    now = time.time()
    dt = now - last_tick_time
    
    if dt <= 0.001: return 
    last_tick_time = now
    
    frames = dt * 60.0 
    if frames > 10: frames = 10 
    
    current_players = list(players_state.items())
    if not current_players: return

    for boss in bosses_state:
        prof = bossProfiles[boss['profile']]

        if boss['stunTimer'] > 0:
            boss['stunTimer'] -= frames
            continue
        
        currentBossSpeed = prof['speed']
        if boss['rageTimer'] > 0:
            currentBossSpeed *= prof['rageMult']
            boss['rageTimer'] -= frames

        targetX, targetY = None, None
        minDist = prof['vision']
        
        for name, p in current_players:
            if p['hp'] > 0 and (now - p['last_update'] < 2):
                if p.get('x') is None or p.get('y') is None: continue 
                
                canSee = prof['seeThrough'] or (not p.get('is_hidden', False))
                if canSee:
                    d = math.hypot(p['x'] - boss['x'], p['y'] - boss['y'])
                    if d < minDist:
                        minDist = d
                        targetX = p['x']
                        targetY = p['y']

        if targetX is not None:
            boss['angle'] = math.atan2(targetY - boss['y'], targetX - boss['x'])
            
            # สกิลพี่ตุ๊ ยิงกระสุน 8 ทิศ
            if prof['isSupreme']:
                boss['shootTimer'] -= frames
                if boss['shootTimer'] <= 0:
                    for i in range(8):
                        a = (math.pi / 4) * i
                        shots_state.append({
                            'owner': boss['name'],
                            'x': boss['x'], 'y': boss['y'],
                            'tx': boss['x'] + math.cos(a) * 500,
                            'ty': boss['y'] + math.sin(a) * 500,
                            't': time.time()
                        })
                    boss['shootTimer'] = 150 
                    boss['rageTimer'] = 0
            
            # 🚨 สกิลพี่เอ ยิงแป้งลูกซอง 3 แฉก!
            elif prof['canShoot']:
                boss['shootTimer'] -= frames
                if boss['shootTimer'] <= 0 and minDist < 700:
                    isPowder = (boss['profile'] == "พี่เอ")
                    if isPowder:
                        # ปาแป้งกระจาย 3 ทิศทาง
                        for offset in [-0.3, 0, 0.3]:
                            a = boss['angle'] + offset
                            tx = boss['x'] + math.cos(a) * 600
                            ty = boss['y'] + math.sin(a) * 600
                            shots_state.append({
                                'owner': boss['name'],
                                'x': boss['x'], 'y': boss['y'],
                                'tx': tx + 100000, # ส่งไปพร้อมรหัสแป้ง (+100000)
                                'ty': ty,
                                't': time.time()
                            })
                        boss['shootTimer'] = 45 # ปารัวมาก (0.75 วิ)
                    else:
                        shots_state.append({
                            'owner': boss['name'],
                            'x': boss['x'], 'y': boss['y'],
                            'tx': targetX, 'ty': targetY,
                            't': time.time()
                        })
                        boss['shootTimer'] = 80
        else:
            if random.random() < (0.02 * frames):
                boss['angle'] += random.uniform(-1.0, 1.0)
            currentBossSpeed *= 0.6

        boss['x'] += math.cos(boss['angle']) * currentBossSpeed * frames
        boss['y'] += math.sin(boss['angle']) * currentBossSpeed * frames

        r = boss['radius']
        if boss['x'] < r: boss['x'] = r; boss['angle'] += math.pi
        if boss['x'] > WORLD['w'] - r: boss['x'] = WORLD['w'] - r; boss['angle'] += math.pi
        if boss['y'] < r: boss['y'] = r; boss['angle'] += math.pi
        if boss['y'] > WORLD['h'] - r: boss['y'] = WORLD['h'] - r; boss['angle'] += math.pi

        if boss['textTimer'] > 0: boss['textTimer'] -= frames

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/update', methods=['POST'])
def update_player():
    data = request.json
    name = data.get('name')
    if not name: return jsonify({"status": "error"})
    
    current_score = players_state.get(name, {}).get('score', 0)
    players_state[name] = {
        'name': name, 'x': data.get('x'), 'y': data.get('y'),
        'hp': data.get('hp'), 'score': current_score,
        'is_hidden': data.get('is_hidden'), 'last_update': time.time()
    }
    return jsonify({"status": "ok"})

@app.route('/shoot', methods=['POST'])
def shoot():
    data = request.json
    shots_state.append({
        'owner': data.get('name'), 'x': data.get('x'), 'y': data.get('y'),
        'tx': data.get('tx'), 'ty': data.get('ty'), 't': time.time()
    })
    return jsonify({"status": "ok"})

@app.route('/boss_hit', methods=['POST'])
def boss_hit():
    data = request.json
    p_name, boss_index = data.get('name'), data.get('boss_id')
    
    if 0 <= boss_index < len(bosses_state):
        boss = bosses_state[boss_index]
        prof = bossProfiles[boss['profile']]
        boss['stunTimer'] = prof['stunTime']
        boss['rageTimer'] = 180
        boss['text'] = "หน็อยแน่ะ!! 😡" if prof['stunTime'] > 0 else "สาดมาสาดกลับ!"
        boss['textTimer'] = 120
        
        if p_name in players_state:
            players_state[p_name]['score'] += 20
    return jsonify({"status": "ok"})

@app.route('/score_up', methods=['POST'])
def score_up():
    data = request.json
    shooter = data.get('shooter')
    if shooter in players_state:
        players_state[shooter]['score'] += 10
    return jsonify({"status": "ok"})

@app.route('/player_dead', methods=['POST'])
def player_dead():
    data = request.json
    name, boss_name = data.get('name'), data.get('boss_name')
    if name in players_state:
        players_state[name]['score'] = max(0, players_state[name]['score'] - 50)
        for boss in bosses_state:
            if boss['name'] == boss_name:
                boss['text'] = f"จับ {name} ได้แล้ว! 🎉"
                boss['textTimer'] = 150
                break
    return jsonify({"status": "ok"})

@app.route('/get_world', methods=['GET'])
def get_world():
    tick_bosses() 
    
    global shots_state
    now = time.time()
    active_players = []
    keys_to_delete = []
    
    for name, p in players_state.items():
        if now - p['last_update'] < 5: active_players.append(p)
        else: keys_to_delete.append(name)
            
    for name in keys_to_delete: del players_state[name]
        
    active_players.sort(key=lambda x: x['score'], reverse=True)
    shots_state = [s for s in shots_state if now - s['t'] < 1]
    
    return jsonify({
        "players": active_players,
        "shots": shots_state,
        "bosses": bosses_state
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
