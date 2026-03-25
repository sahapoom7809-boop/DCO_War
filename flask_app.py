import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template
from flask_socketio import SocketIO
import time
import random
import math
from threading import Lock # 🚨 นำเข้าตัวล็อค AI

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dco_secret_2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

WORLD = { 'w': 4000, 'h': 3500 }
players_state = {}
shots_state = []
bosses_state = []

# 🚨 ตัวแปรควบคุมสมองกล AI
thread = None
thread_lock = Lock()

bossProfiles = {
    "พี่ตุ๊": { 'radius': 35, 'speed': 3.2, 'color': "#d32f2f", 'text': "แจกงานด่วน!", 'stunTime': 15, 'rageMult': 2.0, 'seeThrough': False, 'vision': 650, 'canShoot': True, 'invisible': False, 'isSupreme': True }, 
    "พี่พงษ์": { 'radius': 30, 'speed': 3.5, 'color': "#1976d2", 'text': "แก้ตรงนี้นิดนึง", 'stunTime': 45, 'rageMult': 1.5, 'seeThrough': True, 'vision': 900, 'canShoot': False, 'invisible': False, 'isSupreme': False }, 
    "พี่เอ": { 'radius': 55, 'speed': 3.8, 'color': "#388e3c", 'text': "เอาแป้งไปกิน!", 'stunTime': 0, 'rageMult': 1.5, 'seeThrough': False, 'vision': 700, 'canShoot': True, 'invisible': False, 'isSupreme': False }, 
    "พี่หนู": { 'radius': 25, 'speed': 2.6, 'color': "#e91e63", 'text': "แอบอยู่นี่เอง~", 'stunTime': 30, 'rageMult': 1.2, 'seeThrough': False, 'vision': 500, 'canShoot': False, 'invisible': True, 'isSupreme': False }, 
    "พี่โอ๋": { 'radius': 30, 'speed': 5.5, 'color': "#f57c00", 'text': "ด่วนๆๆ เอาเดี๋ยวนี้!", 'stunTime': 40, 'rageMult': 1.3, 'seeThrough': False, 'vision': 600, 'canShoot': False, 'invisible': False, 'isSupreme': False } 
}

def create_global_bosses():
    bosses_state.clear()
    for name, prof in bossProfiles.items():
        bosses_state.append({
            'name': "🕴️ " + name,
            'color': prof['color'], 'radius': prof['radius'], 'isSupreme': prof['isSupreme'], 'invisible': prof['invisible'],
            'x': random.uniform(200, WORLD['w'] - 200), 'y': random.uniform(200, WORLD['h'] - 200),
            'angle': random.uniform(0, math.pi * 2),
            'stunTimer': 0, 'rageTimer': 0, 'shootTimer': 0, 'textTimer': 90,
            'text': prof['text'], 'profile': name
        })

create_global_bosses()

# --- หัวใจหลัก: Game Loop ของ Server ---
def game_loop():
    global shots_state
    last_time = time.time()
    
    while True:
        try:
            now = time.time()
            dt = now - last_time
            last_time = now
            
            frames = max(1.0, dt * 60.0)
            if frames > 10: frames = 10
            
            current_players = {k: v for k, v in list(players_state.items()) if now - v.get('last_update', 0) < 5}
            
            if current_players:
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
                    
                    for name, p in current_players.items():
                        if p['hp'] > 0 and p.get('x') is not None and p.get('y') is not None:
                            canSee = prof['seeThrough'] or (not p.get('is_hidden', False))
                            if canSee:
                                d = math.hypot(p['x'] - boss['x'], p['y'] - boss['y'])
                                if d < minDist:
                                    minDist = d; targetX = p['x']; targetY = p['y']

                    if targetX is not None:
                        boss['angle'] = math.atan2(targetY - boss['y'], targetX - boss['x'])
                        
                        if prof['isSupreme']:
                            boss['shootTimer'] -= frames
                            if boss['shootTimer'] <= 0:
                                for i in range(8):
                                    a = (math.pi / 4) * i
                                    shots_state.append({'owner': boss['name'], 'x': boss['x'], 'y': boss['y'], 'tx': boss['x'] + math.cos(a)*500, 'ty': boss['y'] + math.sin(a)*500, 't': time.time()})
                                boss['shootTimer'] = 150; boss['rageTimer'] = 0
                        
                        elif prof['canShoot']:
                            boss['shootTimer'] -= frames
                            if boss['shootTimer'] <= 0 and minDist < 700:
                                isPowder = (boss['profile'] == "พี่เอ")
                                if isPowder:
                                    for offset in [-0.3, 0, 0.3]:
                                        a = boss['angle'] + offset
                                        shots_state.append({'owner': boss['name'], 'x': boss['x'], 'y': boss['y'], 'tx': boss['x'] + math.cos(a)*600 + 100000, 'ty': boss['y'] + math.sin(a)*600, 't': time.time()})
                                    boss['shootTimer'] = 45
                                else:
                                    shots_state.append({'owner': boss['name'], 'x': boss['x'], 'y': boss['y'], 'tx': targetX, 'ty': targetY, 't': time.time()})
                                    boss['shootTimer'] = 80
                    else:
                        if random.random() < (0.02 * frames): boss['angle'] += random.uniform(-1.0, 1.0)
                        currentBossSpeed *= 0.6

                    boss['x'] += math.cos(boss['angle']) * currentBossSpeed * frames
                    boss['y'] += math.sin(boss['angle']) * currentBossSpeed * frames

                    r = boss['radius']
                    if boss['x'] < r or boss['x'] > WORLD['w']-r: boss['angle'] = math.pi - boss['angle']
                    if boss['y'] < r or boss['y'] > WORLD['h']-r: boss['angle'] = -boss['angle']
                    boss['x'] = max(r, min(WORLD['w']-r, boss['x']))
                    boss['y'] = max(r, min(WORLD['h']-r, boss['y']))

                    if boss['textTimer'] > 0: boss['textTimer'] -= frames

            shots_state = [s for s in shots_state if now - s['t'] < 1]
            
            sorted_players = sorted(current_players.values(), key=lambda x: x['score'], reverse=True)
            socketio.emit('world_update', {
                'players': sorted_players,
                'bosses': bosses_state,
                'shots': shots_state
            })
            
        except Exception as e:
            print(f"⚠️ [Game Loop Error] : {e}")
            
        socketio.sleep(0.05)

# 🚨 สวิตช์เปิด AI: จะทำงานเมื่อมีผู้เล่นคนแรกกดเข้าเว็บเท่านั้น!
@socketio.on('connect')
def on_connect():
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(game_loop)
            print("🎮 AI Boss Thread Started!")

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('player_update')
def handle_player_update(data):
    name = data.get('name')
    if not name: return
    current_score = players_state.get(name, {}).get('score', 0)
    players_state[name] = {
        'name': name, 'x': data.get('x'), 'y': data.get('y'),
        'hp': data.get('hp'), 'score': current_score,
        'is_hidden': data.get('is_hidden'), 'last_update': time.time()
    }

@socketio.on('player_shoot')
def handle_shoot(data):
    shots_state.append({
        'owner': data.get('name'), 'x': data.get('x'), 'y': data.get('y'),
        'tx': data.get('tx'), 'ty': data.get('ty'), 't': time.time()
    })

@socketio.on('boss_hit')
def handle_boss_hit(data):
    p_name, boss_index = data.get('name'), data.get('boss_id')
    if 0 <= boss_index < len(bosses_state):
        boss = bosses_state[boss_index]
        prof = bossProfiles[boss['profile']]
        boss['stunTimer'] = prof['stunTime']
        boss['rageTimer'] = 180
        boss['text'] = "หน็อยแน่ะ!! 😡" if prof['stunTime'] > 0 else "สาดมาสาดกลับ!"
        boss['textTimer'] = 120
        if p_name in players_state: players_state[p_name]['score'] += 20

@socketio.on('score_up')
def handle_score_up(data):
    shooter = data.get('shooter')
    if shooter in players_state: players_state[shooter]['score'] += 10

@socketio.on('player_dead')
def handle_player_dead(data):
    name, boss_name = data.get('name'), data.get('boss_name')
    if name in players_state:
        players_state[name]['score'] = max(0, players_state[name]['score'] - 50)
        for boss in bosses_state:
            if boss['name'] == boss_name:
                boss['text'] = f"จับ {name} ได้แล้ว! 🎉"
                boss['textTimer'] = 150
                break

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
