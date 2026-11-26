import pygame
import sys
import random
import math
import array
import socket
import threading
import json

# Инициализация Pygame и звука
pygame.mixer.pre_init(22050, -16, 1, 512)
pygame.init()

# Настройка экрана
info = pygame.display.Info()
WIDTH = min(info.current_w, info.current_h)
HEIGHT = max(info.current_w, info.current_h)
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Chess Grandmaster UI")

# Размеры доски с местом под шкалу перевеса (Eval Bar)
EVAL_BAR_W = max(10, WIDTH // 38)
BOARD_SIZE = int(WIDTH * 0.90)
BOARD_SIZE -= BOARD_SIZE % 8
SQ_SIZE = BOARD_SIZE // 8
TOTAL_W = BOARD_SIZE + EVAL_BAR_W + 6
OFFSET_X = (WIDTH - TOTAL_W) // 2 + EVAL_BAR_W + 6
OFFSET_Y = (HEIGHT - BOARD_SIZE) // 2

# Премиальные темы оформления
THEMES = [
    {
        'name': 'Турнирный Изумруд',
        'bg': (18, 20, 26), 'card': (28, 32, 40), 'card_border': (48, 54, 68),
        'light': (238, 238, 210), 'dark': (118, 150, 86),
        'last_l': (246, 246, 105), 'last_d': (186, 202, 43),
        'text': (245, 247, 250), 'subtext': (150, 158, 175), 'accent': (86, 195, 115)
    },
    {
        'name': 'Королевский Орех',
        'bg': (28, 21, 16), 'card': (44, 33, 25), 'card_border': (75, 56, 42),
        'light': (240, 217, 181), 'dark': (181, 136, 99),
        'last_l': (247, 247, 130), 'last_d': (200, 160, 80),
        'text': (255, 248, 235), 'subtext': (185, 165, 145), 'accent': (230, 165, 65)
    },
    {
        'name': 'Неон Киберпанк',
        'bg': (11, 10, 22), 'card': (22, 18, 42), 'card_border': (55, 42, 105),
        'light': (54, 48, 88), 'dark': (24, 20, 46),
        'last_l': (0, 240, 190), 'last_d': (0, 145, 115),
        'text': (230, 255, 250), 'subtext': (130, 140, 185), 'accent': (0, 240, 190)
    },
    {
        'name': 'Обсидиан и Золото',
        'bg': (14, 14, 16), 'card': (24, 24, 28), 'card_border': (55, 50, 40),
        'light': (210, 210, 215), 'dark': (75, 78, 88),
        'last_l': (235, 195, 75), 'last_d': (175, 140, 45),
        'text': (250, 245, 230), 'subtext': (155, 155, 165), 'accent': (235, 195, 75)
    }
]
current_theme_idx = 0
ai_difficulty = "Средний"

# Шрифты
TITLE_FONT = pygame.font.SysFont('arial', max(34, WIDTH // 10), bold=True)
SUBTITLE_FONT = pygame.font.SysFont('arial', max(14, WIDTH // 28), bold=False)
BTN_FONT = pygame.font.SysFont('arial', max(19, WIDTH // 20), bold=True)
UI_FONT = pygame.font.SysFont('arial', max(17, WIDTH // 24), bold=True)
SMALL_FONT = pygame.font.SysFont('arial', max(13, WIDTH // 32), bold=True)
COORD_FONT = pygame.font.SysFont('arial', max(10, SQ_SIZE // 6), bold=True)


# --- СИНТЕЗАТОР ЗВУКОВ ---
def make_sound(freq, duration_ms, volume=0.25):
    try:
        sample_rate = 22050
        n_samples = int(sample_rate * duration_ms / 1000.0)
        buf = array.array('h')
        for i in range(n_samples):
            t = i / sample_rate
            decay = math.exp(-t * 25)
            val = int(32767 * volume * decay * math.sin(2 * math.pi * freq * t))
            buf.append(val)
        return pygame.mixer.Sound(buffer=buf)
    except Exception:
        return None


SND_MOVE = make_sound(340, 65, 0.25)
SND_CAPTURE = make_sound(175, 110, 0.35)
SND_CHECK = make_sound(640, 180, 0.30)
SND_CLICK = make_sound(520, 35, 0.18)


def play_snd(snd):
    if snd:
        try:
            snd.play()
        except Exception:
            pass


# --- ЧАСТИЦЫ И ФОНОВАЯ АНИМАЦИЯ МЕНЮ ---
particles = []
menu_bg_pieces = [
    {'piece': random.choice(['wN', 'bQ', 'wR', 'bB', 'wK', 'bN']),
     'x': random.randint(0, WIDTH),
     'y': random.randint(0, HEIGHT),
     'vy': random.uniform(-0.6, -0.2),
     'size': random.randint(36, 68)}
    for _ in range(12)
]


def add_particles(x, y, color):
    for _ in range(20):
        angle = random.uniform(0, math.pi * 2)
        speed = random.uniform(2, 8.5)
        particles.append({
            'x': x, 'y': y,
            'vx': math.cos(angle) * speed,
            'vy': math.sin(angle) * speed,
            'color': color,
            'life': random.randint(18, 30)
        })


def update_and_draw_particles(surface):
    for p in particles[:]:
        p['x'] += p['vx']
        p['y'] += p['vy']
        p['life'] -= 1
        pygame.draw.circle(surface, p['color'], (int(p['x']), int(p['y'])), max(1, p['life'] // 4))
        if p['life'] <= 0:
            particles.remove(p)


# --- СЕТЕВАЯ СИСТЕМА ПО КОДАМ ---
ACTIVE_CODES = set()


def generate_unique_code():
    while True:
        code = str(random.randint(1000, 9999))
        if code not in ACTIVE_CODES:
            ACTIVE_CODES.add(code)
            return code


class CodeNetworkManager:
    def __init__(self):
        self.sock = None
        self.conn = None
        self.connected = False
        self.is_host = False
        self.error = ""
        self.incoming_moves = []
        self.running = False
        self.current_code = ""

    def close(self):
        self.running = False
        self.connected = False
        if self.current_code in ACTIVE_CODES:
            ACTIVE_CODES.remove(self.current_code)
        for s in (self.conn, self.sock):
            if s:
                try:
                    s.close()
                except Exception:
                    pass
        self.conn = None
        self.sock = None

    def start_host(self):
        self.close()
        self.is_host = True
        self.error = ""
        self.running = True
        self.current_code = generate_unique_code()
        port = 10000 + int(self.current_code)

        def _host_thread():
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.sock.bind(("0.0.0.0", port))
                self.sock.listen(1)
                self.sock.settimeout(1.0)
                while self.running and not self.connected:
                    try:
                        conn, _ = self.sock.accept()
                        self.conn = conn
                        self.connected = True
                        self._listen_loop()
                    except socket.timeout:
                        continue
            except Exception as e:
                self.error = f"Ошибка хоста: {e}"

        threading.Thread(target=_host_thread, daemon=True).start()

    def connect_with_code(self, code, host_ip):
        self.close()
        self.is_host = False
        self.error = ""
        self.running = True
        port = 10000 + int(code)

        def _client_thread():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(6.0)
                s.connect((host_ip.strip(), port))
                s.settimeout(None)
                self.conn = s
                self.connected = True
                self._listen_loop()
            except Exception:
                self.error = "Неверный код или IP хоста!"

        threading.Thread(target=_client_thread, daemon=True).start()

    def _listen_loop(self):
        buffer = ""
        while self.running and self.connected:
            try:
                data = self.conn.recv(1024).decode("utf-8")
                if not data:
                    self.connected = False
                    self.error = "Соперник отключился"
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        msg = json.loads(line)
                        self.incoming_moves.append(msg)
            except Exception:
                self.connected = False
                self.error = "Связь потеряна"
                break

    def send_move(self, start, end):
        if self.connected and self.conn:
            try:
                payload = json.dumps({"start": list(start), "end": list(end)}) + "\n"
                self.conn.sendall(payload.encode("utf-8"))
            except Exception:
                self.connected = False


# --- ОТРИСОВКА ФИГУР ---
def draw_chess_piece(surface, piece, x, y, size, alpha=255):
    if alpha < 255:
        temp = pygame.Surface((size, size), pygame.SRCALPHA)
        draw_chess_piece(temp, piece, 0, 0, size, 255)
        temp.set_alpha(alpha)
        surface.blit(temp, (x, y))
        return

    cx = x + size // 2
    s = size * 0.86
    is_white = piece[0] == 'w'
    p_type = piece[1]

    fill = (252, 252, 250) if is_white else (34, 36, 42)
    outline = (25, 25, 30) if is_white else (235, 235, 240)
    detail = (170, 170, 175) if is_white else (120, 125, 135)

    shadow_surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow_surf, (0, 0, 0, 75), (size * 0.18, size * 0.78, size * 0.64, size * 0.14))
    surface.blit(shadow_surf, (x, y))

    base_y = y + size * 0.82
    base_w = s * 0.68
    base_h = s * 0.11

    def draw_base():
        rect1 = pygame.Rect(cx - base_w / 2, base_y - base_h, base_w, base_h)
        rect2 = pygame.Rect(cx - base_w * 0.42, base_y - base_h * 1.7, base_w * 0.84, base_h * 0.8)
        pygame.draw.rect(surface, fill, rect1, border_radius=4)
        pygame.draw.rect(surface, outline, rect1, 2, border_radius=4)
        pygame.draw.rect(surface, fill, rect2, border_radius=3)
        pygame.draw.rect(surface, outline, rect2, 2, border_radius=3)

    if p_type == 'P':
        draw_base()
        body = [(cx - s * 0.22, base_y - base_h * 1.6), (cx + s * 0.22, base_y - base_h * 1.6),
                (cx + s * 0.11, y + size * 0.44), (cx - s * 0.11, y + size * 0.44)]
        pygame.draw.polygon(surface, fill, body)
        pygame.draw.polygon(surface, outline, body, 2)
        collar = pygame.Rect(cx - s * 0.16, y + size * 0.42, s * 0.32, s * 0.06)
        pygame.draw.rect(surface, fill, collar, border_radius=2)
        pygame.draw.rect(surface, outline, collar, 2, border_radius=2)
        pygame.draw.circle(surface, fill, (int(cx), int(y + size * 0.31)), int(s * 0.15))
        pygame.draw.circle(surface, outline, (int(cx), int(y + size * 0.31)), int(s * 0.15), 2)
    elif p_type == 'R':
        draw_base()
        tower = [(cx - s * 0.24, base_y - base_h * 1.6), (cx + s * 0.24, base_y - base_h * 1.6),
                 (cx + s * 0.19, y + size * 0.34), (cx - s * 0.19, y + size * 0.34)]
        pygame.draw.polygon(surface, fill, tower)
        pygame.draw.polygon(surface, outline, tower, 2)
        top_y = y + size * 0.21
        top_h = size * 0.14
        top_w = s * 0.48
        pygame.draw.rect(surface, fill, (cx - top_w / 2, top_y + top_h * 0.35, top_w, top_h * 0.65))
        pygame.draw.rect(surface, outline, (cx - top_w / 2, top_y + top_h * 0.35, top_w, top_h * 0.65), 2)
        tooth_w = top_w / 5
        for i in [0, 2, 4]:
            tx = cx - top_w / 2 + i * tooth_w
            pygame.draw.rect(surface, fill, (tx, top_y, tooth_w, top_h * 0.45))
            pygame.draw.rect(surface, outline, (tx, top_y, tooth_w, top_h * 0.45), 2)
    elif p_type == 'N':
        draw_base()
        horse = [(cx - s * 0.23, base_y - base_h * 1.6), (cx + s * 0.24, base_y - base_h * 1.6),
                 (cx + s * 0.22, y + size * 0.48), (cx + s * 0.08, y + size * 0.38),
                 (cx + s * 0.27, y + size * 0.34), (cx + s * 0.24, y + size * 0.23),
                 (cx + s * 0.05, y + size * 0.15), (cx - s * 0.04, y + size * 0.20),
                 (cx - s * 0.22, y + size * 0.33), (cx - s * 0.26, y + size * 0.54)]
        pygame.draw.polygon(surface, fill, horse)
        pygame.draw.polygon(surface, outline, horse, 2)
        pygame.draw.circle(surface, outline, (int(cx + s * 0.11), int(y + size * 0.25)), max(2, int(s * 0.03)))
        pygame.draw.line(surface, detail, (cx - s * 0.13, y + size * 0.34), (cx - s * 0.16, y + size * 0.55), 2)
    elif p_type == 'B':
        draw_base()
        body = [(cx - s * 0.24, base_y - base_h * 1.6), (cx + s * 0.24, base_y - base_h * 1.6),
                (cx + s * 0.14, y + size * 0.44), (cx - s * 0.14, y + size * 0.44)]
        pygame.draw.polygon(surface, fill, body)
        pygame.draw.polygon(surface, outline, body, 2)
        mitre = [(cx, y + size * 0.16), (cx + s * 0.19, y + size * 0.33),
                 (cx + s * 0.13, y + size * 0.45), (cx - s * 0.13, y + size * 0.45), (cx - s * 0.19, y + size * 0.33)]
        pygame.draw.polygon(surface, fill, mitre)
        pygame.draw.polygon(surface, outline, mitre, 2)
        pygame.draw.line(surface, outline, (cx - s * 0.03, y + size * 0.26), (cx + s * 0.06, y + size * 0.35), 2)
        pygame.draw.circle(surface, fill, (int(cx), int(y + size * 0.13)), int(s * 0.05))
        pygame.draw.circle(surface, outline, (int(cx), int(y + size * 0.13)), int(s * 0.05), 2)
    elif p_type == 'Q':
        draw_base()
        crown = [(cx - s * 0.23, base_y - base_h * 1.6), (cx + s * 0.23, base_y - base_h * 1.6),
                 (cx + s * 0.30, y + size * 0.25), (cx + s * 0.15, y + size * 0.38),
                 (cx + s * 0.12, y + size * 0.20), (cx, y + size * 0.36),
                 (cx - s * 0.12, y + size * 0.20), (cx - s * 0.15, y + size * 0.38), (cx - s * 0.30, y + size * 0.25)]
        pygame.draw.polygon(surface, fill, crown)
        pygame.draw.polygon(surface, outline, crown, 2)
        for tx, ty in [(cx - s * 0.30, y + size * 0.23), (cx - s * 0.12, y + size * 0.18), (cx, y + size * 0.15),
                       (cx + s * 0.12, y + size * 0.18), (cx + s * 0.30, y + size * 0.23)]:
            pygame.draw.circle(surface, fill, (int(tx), int(ty)), int(s * 0.045))
            pygame.draw.circle(surface, outline, (int(tx), int(ty)), int(s * 0.045), 2)
    elif p_type == 'K':
        draw_base()
        body = [(cx - s * 0.25, base_y - base_h * 1.6), (cx + s * 0.25, base_y - base_h * 1.6),
                (cx + s * 0.29, y + size * 0.32), (cx, y + size * 0.24), (cx - s * 0.29, y + size * 0.32)]
        pygame.draw.polygon(surface, fill, body)
        pygame.draw.polygon(surface, outline, body, 2)
        pygame.draw.line(surface, detail, (cx, y + size * 0.26), (cx, base_y - base_h * 1.8), 2)
        cw = max(3, int(s * 0.06))
        ch = int(s * 0.17)
        cross_y = y + size * 0.09
        pygame.draw.rect(surface, outline, (cx - cw // 2 - 1, cross_y - 1, cw + 2, ch + 2))
        pygame.draw.rect(surface, outline, (cx - ch // 2 - 1, cross_y + ch // 3 - 1, ch + 2, cw + 2))
        pygame.draw.rect(surface, fill, (cx - cw // 2, cross_y, cw, ch))
        pygame.draw.rect(surface, fill, (cx - ch // 2, cross_y + ch // 3, ch, cw))


# --- ЛОГИКА ИГРЫ ---
PIECE_VALUES = {'P': 100, 'N': 320, 'B': 330, 'R': 500, 'Q': 900, 'K': 20000}
MATERIAL_PTS = {'P': 1, 'N': 3, 'B': 3, 'R': 5, 'Q': 9, 'K': 0}


class ChessGame:
    def __init__(self, mode="bot", my_color="w"):
        self.mode = mode
        self.my_color = my_color
        self.reset()

    def reset(self):
        self.board = [
            ['bR', 'bN', 'bB', 'bQ', 'bK', 'bB', 'bN', 'bR'],
            ['bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP'],
            ['--', '--', '--', '--', '--', '--', '--', '--'],
            ['--', '--', '--', '--', '--', '--', '--', '--'],
            ['--', '--', '--', '--', '--', '--', '--', '--'],
            ['--', '--', '--', '--', '--', '--', '--', '--'],
            ['wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP'],
            ['wR', 'wN', 'wB', 'wQ', 'wK', 'wB', 'wN', 'wR']
        ]
        self.turn = 'w'
        self.selected = None
        self.valid_moves = []
        self.last_move = None
        self.history = []
        self.captured_w = []
        self.captured_b = []
        self.game_over = False
        self.move_count = 1
        self.update_status()

    def get_material_diff(self):
        """Возвращает разницу в очках: >0 в пользу белых, <0 в пользу черных"""
        w_pts, b_pts = 0, 0
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p != '--':
                    if p[0] == 'w':
                        w_pts += MATERIAL_PTS[p[1]]
                    else:
                        b_pts += MATERIAL_PTS[p[1]]
        return w_pts - b_pts

    def in_bounds(self, r, c):
        return 0 <= r < 8 and 0 <= c < 8

    def get_pseudo_moves(self, r, c, board):
        piece = board[r][c]
        if piece == '--':
            return []
        color, p_type = piece[0], piece[1]
        moves = []

        if p_type == 'P':
            direction = -1 if color == 'w' else 1
            start_row = 6 if color == 'w' else 1
            if self.in_bounds(r + direction, c) and board[r + direction][c] == '--':
                moves.append((r + direction, c))
                if r == start_row and board[r + 2 * direction][c] == '--':
                    moves.append((r + 2 * direction, c))
            for dc in [-1, 1]:
                nr, nc = r + direction, c + dc
                if self.in_bounds(nr, nc) and board[nr][nc] != '--' and board[nr][nc][0] != color:
                    moves.append((nr, nc))
        elif p_type in ['R', 'B', 'Q']:
            directions = []
            if p_type in ['R', 'Q']:
                directions.extend([(-1, 0), (1, 0), (0, -1), (0, 1)])
            if p_type in ['B', 'Q']:
                directions.extend([(-1, -1), (-1, 1), (1, -1), (1, 1)])
            for dr, dc in directions:
                nr, nc = r + dr, c + dc
                while self.in_bounds(nr, nc):
                    if board[nr][nc] == '--':
                        moves.append((nr, nc))
                    elif board[nr][nc][0] != color:
                        moves.append((nr, nc))
                        break
                    else:
                        break
                    nr += dr
                    nc += dc
        elif p_type == 'N':
            for dr, dc in [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]:
                nr, nc = r + dr, c + dc
                if self.in_bounds(nr, nc) and (board[nr][nc] == '--' or board[nr][nc][0] != color):
                    moves.append((nr, nc))
        elif p_type == 'K':
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if self.in_bounds(nr, nc) and (board[nr][nc] == '--' or board[nr][nc][0] != color):
                        moves.append((nr, nc))
        return moves

    def find_king(self, color, board):
        for r in range(8):
            for c in range(8):
                if board[r][c] == color + 'K':
                    return (r, c)
        return None

    def is_in_check(self, color, board):
        king_pos = self.find_king(color, board)
        enemy = 'b' if color == 'w' else 'w'
        for r in range(8):
            for c in range(8):
                if board[r][c][0] == enemy:
                    if king_pos in self.get_pseudo_moves(r, c, board):
                        return True
        return False

    def get_legal_moves_for_board(self, r, c, board, turn):
        piece = board[r][c]
        if piece == '--' or piece[0] != turn:
            return []
        legal = []
        for nr, nc in self.get_pseudo_moves(r, c, board):
            temp = [row[:] for row in board]
            temp[nr][nc] = temp[r][c]
            temp[r][c] = '--'
            if not self.is_in_check(turn, temp):
                legal.append((nr, nc))
        return legal

    def get_legal_moves(self, r, c):
        return self.get_legal_moves_for_board(r, c, self.board, self.turn)

    def get_all_legal_moves(self, color, board):
        all_moves = []
        for r in range(8):
            for c in range(8):
                if board[r][c][0] == color:
                    for move in self.get_legal_moves_for_board(r, c, board, color):
                        all_moves.append(((r, c), move))
        return all_moves

    def make_move(self, start, end):
        self.history.append(([row[:] for row in self.board], self.turn, self.last_move,
                             self.captured_w[:], self.captured_b[:], self.status_text, self.move_count))
        sr, sc = start
        er, ec = end
        piece = self.board[sr][sc]
        target = self.board[er][ec]

        if target != '--':
            if target[0] == 'w':
                self.captured_w.append(target)
            else:
                self.captured_b.append(target)
            play_snd(SND_CAPTURE)
            disp_r = 7 - er if (self.mode == "online" and self.my_color == "b") else er
            disp_c = 7 - ec if (self.mode == "online" and self.my_color == "b") else ec
            add_particles(OFFSET_X + disp_c * SQ_SIZE + SQ_SIZE // 2,
                          OFFSET_Y + disp_r * SQ_SIZE + SQ_SIZE // 2, (255, 210, 60))
        else:
            play_snd(SND_MOVE)

        self.board[er][ec] = piece
        self.board[sr][sc] = '--'

        if piece == 'wP' and er == 0:
            self.board[er][ec] = 'wQ'
        elif piece == 'bP' and er == 7:
            self.board[er][ec] = 'bQ'

        if self.turn == 'b':
            self.move_count += 1

        self.last_move = (start, end)
        self.turn = 'b' if self.turn == 'w' else 'w'
        self.update_status()

    def undo_move(self):
        if self.mode == "online" or not self.history:
            return
        steps = 2 if (self.mode == "bot" and self.turn == 'w' and len(self.history) >= 2) else 1
        for _ in range(steps):
            if self.history:
                state = self.history.pop()
                self.board, self.turn, self.last_move, self.captured_w, self.captured_b, self.status_text, self.move_count = state
        self.selected = None
        self.valid_moves = []
        self.game_over = False

    def update_status(self):
        moves = self.get_all_legal_moves(self.turn, self.board)
        in_check = self.is_in_check(self.turn, self.board)
        if not moves:
            self.game_over = True
            if in_check:
                winner = "Белые" if self.turn == 'b' else "Черные"
                self.status_text = f"МАТ! Победили {winner}!"
                play_snd(SND_CHECK)
            else:
                self.status_text = "ПАТ! Ничья!"
        else:
            if in_check:
                play_snd(SND_CHECK)
                who = "белым" if self.turn == 'w' else "черным"
                self.status_text = f"ШАХ {who}!"
            else:
                if self.mode == "bot":
                    self.status_text = "Ваш ход" if self.turn == 'w' else "ИИ думает..."
                elif self.mode == "online":
                    self.status_text = "Ваш ход" if self.turn == self.my_color else "Ход соперника..."
                else:
                    self.status_text = "Ход белых" if self.turn == 'w' else "Ход черных"

    def get_best_ai_move(self):
        moves = self.get_all_legal_moves('b', self.board)
        if not moves:
            return None
        if ai_difficulty == "Лёгкий":
            return random.choice(moves)

        best_score = -999999
        best_moves = []
        for start, end in moves:
            temp = [row[:] for row in self.board]
            sr, sc = start
            er, ec = end
            temp[er][ec] = temp[sr][sc]
            temp[sr][sc] = '--'
            score = 0
            target = self.board[er][ec]
            if target != '--':
                score += PIECE_VALUES[target[1]] * (20 if ai_difficulty == "Сложный" else 10)
            if ai_difficulty == "Сложный":
                for r in range(8):
                    for c in range(8):
                        p = temp[r][c]
                        if p != '--':
                            val = PIECE_VALUES[p[1]]
                            center = (3.5 - abs(3.5 - r)) + (3.5 - abs(3.5 - c))
                            score += (val + int(center * 5)) if p[0] == 'b' else -(val + int(center * 5))
            else:
                score += (3.5 - abs(3.5 - er)) + (3.5 - abs(3.5 - ec))

            if score > best_score:
                best_score = score
                best_moves = [(start, end)]
            elif score == best_score:
                best_moves.append((start, end))
        return random.choice(best_moves)


# --- СОВРЕМЕННЫЕ UI-КОМПОНЕНТЫ (3D КНОПКИ, ИКОНКИ, КАРТОЧКИ) ---
def draw_3d_button(surface, rect, text, base_color, font=BTN_FONT, subtext=None, icon_type=None, pressed=False):
    # Тень и нижняя 3D-грань
    depth = 2 if pressed else 5
    draw_rect = rect.move(0, 3 if pressed else 0)

    dark_color = tuple(max(0, c - 45) for c in base_color[:3])
    light_border = tuple(min(255, c + 35) for c in base_color[:3])

    shadow_rect = draw_rect.move(0, depth)
    pygame.draw.rect(surface, dark_color, shadow_rect, border_radius=16)
    pygame.draw.rect(surface, base_color, draw_rect, border_radius=16)
    pygame.draw.rect(surface, light_border, draw_rect, 2, border_radius=16)

    text_x = draw_rect.centerx
    if icon_type:
        icon_cx = draw_rect.x + 34
        icon_cy = draw_rect.centery
        pygame.draw.circle(surface, (255, 255, 255, 35), (icon_cx, icon_cy), 20)
        if icon_type == "1x1":
            pygame.draw.circle(surface, (255, 255, 255), (icon_cx - 5, icon_cy - 3), 5)
            pygame.draw.circle(surface, (255, 255, 255), (icon_cx + 6, icon_cy + 3), 5)
        elif icon_type == "bot":
            pygame.draw.rect(surface, (255, 255, 255), (icon_cx - 8, icon_cy - 7, 16, 14), 2, border_radius=3)
            pygame.draw.circle(surface, (255, 255, 255), (icon_cx - 3, icon_cy - 1), 2)
            pygame.draw.circle(surface, (255, 255, 255), (icon_cx + 3, icon_cy - 1), 2)
        elif icon_type == "online":
            pygame.draw.circle(surface, (255, 255, 255), (icon_cx, icon_cy), 9, 2)
            pygame.draw.ellipse(surface, (255, 255, 255), (icon_cx - 4, icon_cy - 9, 8, 18), 1)
        text_x = draw_rect.x + 68

    if subtext:
        t1 = font.render(text, True, (255, 255, 255))
        t2 = SMALL_FONT.render(subtext, True, (220, 230, 240))
        if icon_type:
            surface.blit(t1, (text_x, draw_rect.centery - t1.get_height() + 2))
            surface.blit(t2, (text_x, draw_rect.centery + 2))
        else:
            surface.blit(t1, (draw_rect.centerx - t1.get_width() // 2, draw_rect.centery - t1.get_height() + 2))
            surface.blit(t2, (draw_rect.centerx - t2.get_width() // 2, draw_rect.centery + 2))
    else:
        txt = font.render(text, True, (255, 255, 255))
        tx = text_x if icon_type else (draw_rect.centerx - txt.get_width() // 2)
        surface.blit(txt, (tx, draw_rect.centery - txt.get_height() // 2))


def draw_player_card(surface, rect, name, subtitle, is_active, is_white_side, captured_pieces, advantage_pts, theme):
    # Карточка профиля игрока (сверху или снизу доски)
    pygame.draw.rect(surface, theme['card'], rect, border_radius=12)
    border_col = theme['accent'] if is_active else theme['card_border']
    pygame.draw.rect(surface, border_col, rect, 2 if is_active else 1, border_radius=12)

    # Аватарка
    av_size = rect.height - 12
    av_rect = pygame.Rect(rect.x + 6, rect.y + 6, av_size, av_size)
    av_bg = (235, 235, 240) if is_white_side else (42, 46, 56)
    pygame.draw.rect(surface, av_bg, av_rect, border_radius=8)
    draw_chess_piece(surface, 'wK' if is_white_side else 'bK', av_rect.x, av_rect.y, av_size)

    # Имя и статус
    name_s = UI_FONT.render(name, True, theme['text'])
    surface.blit(name_s, (av_rect.right + 10, rect.y + 6))

    # Сбитые фигуры в ряд
    mini_size = max(16, av_size // 2)
    cap_x = av_rect.right + 10
    cap_y = rect.bottom - mini_size - 4
    for i, p in enumerate(captured_pieces[-10:]):
        draw_chess_piece(surface, p, cap_x + i * int(mini_size * 0.68), cap_y, mini_size)

    # Очки материального перевеса (+3, +5 и т.д.)
    if advantage_pts > 0:
        adv_x = cap_x + min(len(captured_pieces), 10) * int(mini_size * 0.68) + 4
        adv_s = SMALL_FONT.render(f"+{advantage_pts}", True, theme['accent'])
        surface.blit(adv_s, (adv_x, cap_y + 1))

    # Индикатор активного хода справа
    if is_active:
        dot_x = rect.right - 16
        dot_y = rect.centery
        pygame.draw.circle(surface, theme['accent'], (dot_x, dot_y), 6)


# --- ГЛАВНОЕ МЕНЮ ---
def draw_main_menu(screen):
    theme = THEMES[current_theme_idx]
    screen.fill(theme['bg'])

    # Анимированные плавающие фигуры на фоне
    for item in menu_bg_pieces:
        item['y'] += item['vy']
        if item['y'] < -80:
            item['y'] = HEIGHT + 20
            item['x'] = random.randint(0, WIDTH)
        draw_chess_piece(screen, item['piece'], int(item['x']), int(item['y']), item['size'], alpha=32)

    # Центральный герб / логотип
    logo_y = int(HEIGHT * 0.08)
    deco_size = int(WIDTH * 0.20)
    pygame.draw.circle(screen, theme['card'], (WIDTH // 2, logo_y + deco_size // 2), int(deco_size * 0.72))
    pygame.draw.circle(screen, theme['accent'], (WIDTH // 2, logo_y + deco_size // 2), int(deco_size * 0.72), 2)
    draw_chess_piece(screen, 'wK', WIDTH // 2 - deco_size // 2, logo_y, deco_size)

    title = TITLE_FONT.render("CHESS MASTER", True, theme['text'])
    badge_txt = SMALL_FONT.render("GRANDMASTER EDITION", True, theme['accent'])
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, logo_y + deco_size + 12))
    screen.blit(badge_txt, (WIDTH // 2 - badge_txt.get_width() // 2, logo_y + deco_size + 16 + title.get_height()))

    # Карточки режимов игры
    btn_w = int(WIDTH * 0.84)
    btn_h = max(62, HEIGHT // 13)
    start_y = int(HEIGHT * 0.37)
    gap = 14

    btn_1x1 = pygame.Rect(WIDTH // 2 - btn_w // 2, start_y, btn_w, btn_h)
    btn_bot = pygame.Rect(WIDTH // 2 - btn_w // 2, start_y + btn_h + gap, btn_w, btn_h)
    btn_online = pygame.Rect(WIDTH // 2 - btn_w // 2, start_y + (btn_h + gap) * 2, btn_w, btn_h)

    draw_3d_button(screen, btn_1x1, "1 x 1 Локально", (48, 108, 185), BTN_FONT,
                   "Два игрока на одном телефоне", icon_type="1x1")
    draw_3d_button(screen, btn_bot, "1 x BOT (Против ИИ)", (42, 148, 92), BTN_FONT,
                   f"Уровень интеллекта: {ai_difficulty}", icon_type="bot")
    draw_3d_button(screen, btn_online, "1 x 1 ONLINE", (142, 68, 178), BTN_FONT,
                   "Подключение по секретному коду", icon_type="online")

    # Нижний ряд настроек (Сложность ИИ и Тема доски)
    sub_y = start_y + (btn_h + gap) * 3 + 6
    sub_h = max(48, int(btn_h * 0.78))
    half_w = (btn_w - 12) // 2

    btn_diff = pygame.Rect(WIDTH // 2 - btn_w // 2, sub_y, half_w, sub_h)
    btn_theme = pygame.Rect(WIDTH // 2 - btn_w // 2 + half_w + 12, sub_y, half_w, sub_h)

    draw_3d_button(screen, btn_diff, f"ИИ: {ai_difficulty}", (175, 115, 38), SMALL_FONT)
    draw_3d_button(screen, btn_theme, f"Тема: {theme['name'].split()[0]}", theme['card'], SMALL_FONT)

    return btn_1x1, btn_bot, btn_diff, btn_online, btn_theme


# --- ЛОББИ КОДОВ ДОСТУПА ---
def draw_code_lobby(screen, net, lobby_mode, entered_code, ip_host_input, active_field):
    theme = THEMES[current_theme_idx]
    screen.fill(theme['bg'])

    title = TITLE_FONT.render("СЕТЬ ПО КОДУ", True, theme['accent'])
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, int(HEIGHT * 0.07)))

    btn_w = int(WIDTH * 0.84)
    back_btn = pygame.Rect(WIDTH // 2 - btn_w // 2, int(HEIGHT * 0.88), btn_w, 50)
    draw_3d_button(screen, back_btn, "В главное меню", (125, 52, 62), SMALL_FONT)

    if lobby_mode == "select":
        host_btn = pygame.Rect(WIDTH // 2 - btn_w // 2, int(HEIGHT * 0.30), btn_w, 72)
        join_btn = pygame.Rect(WIDTH // 2 - btn_w // 2, int(HEIGHT * 0.44), btn_w, 72)
        draw_3d_button(screen, host_btn, "Создать комнату", (42, 148, 92), BTN_FONT,
                       "Получить уникальный 4-значный код")
        draw_3d_button(screen, join_btn, "Войти по коду", (48, 108, 185), BTN_FONT,
                       "Ввести код созданной игры")
        return {"back": back_btn, "host": host_btn, "join": join_btn}

    elif lobby_mode == "hosting":
        box = pygame.Rect(WIDTH // 2 - btn_w // 2, int(HEIGHT * 0.24), btn_w, 220)
        pygame.draw.rect(screen, theme['card'], box, border_radius=18)
        pygame.draw.rect(screen, theme['accent'], box, 2, border_radius=18)

        t1 = SMALL_FONT.render("СЕКРЕТНЫЙ КОД КОМНАТЫ", True, theme['subtext'])
        t2 = TITLE_FONT.render(" ".join(net.current_code), True, (255, 215, 0))
        t3 = SMALL_FONT.render("Передайте эти 4 цифры второму игроку", True, theme['text'])
        t4 = UI_FONT.render("Ожидание соперника...", True, theme['accent'])

        screen.blit(t1, (box.centerx - t1.get_width() // 2, box.y + 22))
        screen.blit(t2, (box.centerx - t2.get_width() // 2, box.y + 62))
        screen.blit(t3, (box.centerx - t3.get_width() // 2, box.y + 132))
        screen.blit(t4, (box.centerx - t4.get_width() // 2, box.y + 170))
        return {"back": back_btn}

    elif lobby_mode == "joining":
        # Поле кода
        c_box = pygame.Rect(WIDTH // 2 - btn_w // 2, int(HEIGHT * 0.18), btn_w, 54)
        pygame.draw.rect(screen, theme['card'], c_box, border_radius=14)
        pygame.draw.rect(screen, theme['accent'] if active_field == "code" else theme['card_border'], c_box, 2, border_radius=14)
        disp_c = " ".join(entered_code) if entered_code else "Код комнаты (4 цифры)"
        c_txt = BTN_FONT.render(disp_c, True, theme['text'] if entered_code else theme['subtext'])
        screen.blit(c_txt, (c_box.centerx - c_txt.get_width() // 2, c_box.centery - c_txt.get_height() // 2))

        # Поле IP
        ip_box = pygame.Rect(WIDTH // 2 - btn_w // 2, int(HEIGHT * 0.265), btn_w, 46)
        pygame.draw.rect(screen, theme['card'], ip_box, border_radius=12)
        pygame.draw.rect(screen, theme['accent'] if active_field == "ip" else theme['card_border'], ip_box, 2, border_radius=12)
        disp_ip = ip_host_input if ip_host_input else "IP хоста (например 192.168.1.5)"
        ip_txt = SMALL_FONT.render(disp_ip, True, theme['text'] if ip_host_input else theme['subtext'])
        screen.blit(ip_txt, (ip_box.centerx - ip_txt.get_width() // 2, ip_box.centery - ip_txt.get_height() // 2))

        if net.error:
            err_s = SMALL_FONT.render(net.error, True, (255, 95, 95))
            screen.blit(err_s, (WIDTH // 2 - err_s.get_width() // 2, ip_box.bottom + 6))

        keys = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], [".", "0", "<-"]]
        pad_w = btn_w
        key_gap = 8
        kw = (pad_w - key_gap * 2) // 3
        kh = 46
        pad_y = int(HEIGHT * 0.355)
        key_rects = {}

        for r_idx, row in enumerate(keys):
            for c_idx, k in enumerate(row):
                kr = pygame.Rect(WIDTH // 2 - pad_w // 2 + c_idx * (kw + key_gap),
                                 pad_y + r_idx * (kh + key_gap), kw, kh)
                draw_3d_button(screen, kr, k, (52, 58, 72), BTN_FONT)
                key_rects[k] = kr

        connect_btn = pygame.Rect(WIDTH // 2 - btn_w // 2, pad_y + 4 * (kh + key_gap) + 8, btn_w, 52)
        draw_3d_button(screen, connect_btn, "Подключиться", (42, 148, 92), BTN_FONT)
        return {"back": back_btn, "connect": connect_btn, "keys": key_rects, "code_box": c_box, "ip_box": ip_box}


# --- ИГРОВОЙ ЭКРАН ---
def draw_game_scene(screen, game, anim_data=None):
    theme = THEMES[current_theme_idx]
    screen.fill(theme['bg'])

    flip = (game.mode == "online" and game.my_color == "b")
    mat_diff = game.get_material_diff()  # >0 белые впереди, <0 черные впереди

    # 1. Верхняя панель статуса / навигации
    top_bar_y = max(12, OFFSET_Y - 122)
    status_pill = pygame.Rect(OFFSET_X - EVAL_BAR_W - 6, top_bar_y, TOTAL_W, 34)
    pygame.draw.rect(screen, theme['card'], status_pill, border_radius=10)
    pygame.draw.rect(screen, theme['card_border'], status_pill, 1, border_radius=10)

    move_lbl = SMALL_FONT.render(f"Ход {game.move_count}", True, theme['subtext'])
    status_s = UI_FONT.render(game.status_text, True, theme['text'])
    screen.blit(move_lbl, (status_pill.x + 12, status_pill.centery - move_lbl.get_height() // 2))
    screen.blit(status_s, (status_pill.centerx - status_s.get_width() // 2 + 15,
                           status_pill.centery - status_s.get_height() // 2))

    # 2. Карточка верхнего игрока
    top_card_rect = pygame.Rect(OFFSET_X - EVAL_BAR_W - 6, OFFSET_Y - 80, TOTAL_W, 68)
    if flip:
        top_name = "Вы (Чёрные)"
        top_cap = game.captured_w
        top_adv = max(0, -mat_diff)
        top_active = (game.turn == 'b' and not game.game_over)
        top_white = False
    else:
        top_name = f"Бот ({ai_difficulty})" if game.mode == "bot" else ("Соперник" if game.mode == "online" else "Чёрные")
        top_cap = game.captured_w
        top_adv = max(0, -mat_diff)
        top_active = (game.turn == 'b' and not game.game_over)
        top_white = False

    if flip:
        top_name = "Соперник (Белые)"
        top_cap = game.captured_b
        top_adv = max(0, mat_diff)
        top_active = (game.turn == 'w' and not game.game_over)
        top_white = True

    draw_player_card(screen, top_card_rect, top_name, "", top_active, top_white, top_cap, top_adv, theme)

    # 3. Шкала оценки позиции (Eval Bar) слева от доски
    eval_rect = pygame.Rect(OFFSET_X - EVAL_BAR_W - 6, OFFSET_Y, EVAL_BAR_W, BOARD_SIZE)
    pygame.draw.rect(screen, (35, 38, 45), eval_rect, border_radius=5)
    # Процент заполнения белыми (от 10% до 90%)
    white_ratio = max(0.1, min(0.9, 0.5 + mat_diff * 0.035))
    white_h = int(BOARD_SIZE * white_ratio)
    if not flip:
        w_bar = pygame.Rect(eval_rect.x, eval_rect.bottom - white_h, EVAL_BAR_W, white_h)
    else:
        w_bar = pygame.Rect(eval_rect.x, eval_rect.y, EVAL_BAR_W, white_h)
    pygame.draw.rect(screen, (240, 240, 235), w_bar, border_radius=4)
    pygame.draw.rect(screen, theme['card_border'], eval_rect, 1, border_radius=5)

    # 4. Рамка и клетки шахматной доски
    frame_rect = pygame.Rect(OFFSET_X - 4, OFFSET_Y - 4, BOARD_SIZE + 8, BOARD_SIZE + 8)
    pygame.draw.rect(screen, theme['card'], frame_rect, border_radius=8)
    pygame.draw.rect(screen, theme['card_border'], frame_rect, 2, border_radius=8)

    king_in_check = game.find_king(game.turn, game.board) if game.is_in_check(game.turn, game.board) else None

    for disp_r in range(8):
        for disp_c in range(8):
            r = 7 - disp_r if flip else disp_r
            c = 7 - disp_c if flip else disp_c

            is_light = (r + c) % 2 == 0
            sq_color = theme['light'] if is_light else theme['dark']

            if game.last_move and ((r, c) == game.last_move[0] or (r, c) == game.last_move[1]):
                sq_color = theme['last_l'] if is_light else theme['last_d']

            rect = pygame.Rect(OFFSET_X + disp_c * SQ_SIZE, OFFSET_Y + disp_r * SQ_SIZE, SQ_SIZE, SQ_SIZE)
            pygame.draw.rect(screen, sq_color, rect)

            # Координаты на крайних клетках
            coord_col = theme['dark'] if is_light else theme['light']
            if disp_c == 0:
                c_num = COORD_FONT.render(str(8 - r), True, coord_col)
                screen.blit(c_num, (rect.x + 3, rect.y + 2))
            if disp_r == 7:
                c_let = COORD_FONT.render("abcdefgh"[c], True, coord_col)
                screen.blit(c_let, (rect.right - c_let.get_width() - 3, rect.bottom - c_let.get_height() - 1))

            if king_in_check == (r, c):
                s = pygame.Surface((SQ_SIZE, SQ_SIZE), pygame.SRCALPHA)
                s.fill((235, 50, 50, 185))
                screen.blit(s, rect.topleft)

            if game.selected == (r, c):
                s = pygame.Surface((SQ_SIZE, SQ_SIZE), pygame.SRCALPHA)
                s.fill((255, 215, 0, 145))
                screen.blit(s, rect.topleft)

            if (r, c) in game.valid_moves:
                dot_s = pygame.Surface((SQ_SIZE, SQ_SIZE), pygame.SRCALPHA)
                if game.board[r][c] == '--':
                    pygame.draw.circle(dot_s, (0, 0, 0, 75), (SQ_SIZE // 2, SQ_SIZE // 2), SQ_SIZE // 6)
                else:
                    pygame.draw.circle(dot_s, (0, 0, 0, 95), (SQ_SIZE // 2, SQ_SIZE // 2), int(SQ_SIZE * 0.44), 4)
                screen.blit(dot_s, rect.topleft)

            piece = game.board[r][c]
            if piece != '--':
                if anim_data and anim_data['hide_pos'] == (r, c):
                    continue
                draw_chess_piece(screen, piece, rect.x, rect.y, SQ_SIZE)

    if anim_data:
        draw_chess_piece(screen, anim_data['piece'], anim_data['x'], anim_data['y'], SQ_SIZE)

    update_and_draw_particles(screen)

    # 5. Карточка нижнего игрока
    bot_card_rect = pygame.Rect(OFFSET_X - EVAL_BAR_W - 6, OFFSET_Y + BOARD_SIZE + 12, TOTAL_W, 68)
    if flip:
        bot_name = "Вы (Чёрные)"
        bot_cap = game.captured_w
        bot_adv = max(0, -mat_diff)
        bot_active = (game.turn == 'b' and not game.game_over)
        bot_white = False
    else:
        bot_name = "Вы (Белые)" if game.mode != "1x1" else "Белые"
        bot_cap = game.captured_b
        bot_adv = max(0, mat_diff)
        bot_active = (game.turn == 'w' and not game.game_over)
        bot_white = True

    draw_player_card(screen, bot_card_rect, bot_name, "", bot_active, bot_white, bot_cap, bot_adv, theme)

    # 6. Нижняя панель 3D-кнопок управления
    btn_y = bot_card_rect.bottom + 12
    btn_h = 44
    gap = 8
    btn_w = (TOTAL_W - gap * 3) // 4
    start_btn_x = OFFSET_X - EVAL_BAR_W - 6

    menu_rect = pygame.Rect(start_btn_x, btn_y, btn_w, btn_h)
    undo_rect = pygame.Rect(start_btn_x + btn_w + gap, btn_y, btn_w, btn_h)
    theme_rect = pygame.Rect(start_btn_x + (btn_w + gap) * 2, btn_y, btn_w, btn_h)
    reset_rect = pygame.Rect(start_btn_x + (btn_w + gap) * 3, btn_y, btn_w, btn_h)

    draw_3d_button(screen, menu_rect, "Меню", (52, 95, 155), SMALL_FONT)
    draw_3d_button(screen, undo_rect, "Назад", (68, 75, 92) if game.mode != "online" else (38, 42, 50), SMALL_FONT)
    draw_3d_button(screen, theme_rect, "Тема", (98, 62, 125), SMALL_FONT)
    draw_3d_button(screen, reset_rect, "Сброс", (135, 58, 65) if game.mode != "online" else (38, 42, 50), SMALL_FONT)

    # Модальное окно конца игры
    if game.game_over:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        screen.blit(overlay, (0, 0))

        modal_w = int(TOTAL_W * 0.88)
        modal_h = 185
        modal_rect = pygame.Rect(WIDTH // 2 - modal_w // 2, HEIGHT // 2 - modal_h // 2, modal_w, modal_h)
        pygame.draw.rect(screen, theme['card'], modal_rect, border_radius=20)
        pygame.draw.rect(screen, (255, 215, 0), modal_rect, 3, border_radius=20)

        msg = UI_FONT.render(game.status_text, True, (255, 255, 255))
        sub_m = SMALL_FONT.render(f"Партия завершена на {game.move_count}-м ходу", True, theme['subtext'])
        screen.blit(msg, (modal_rect.centerx - msg.get_width() // 2, modal_rect.y + 30))
        screen.blit(sub_m, (modal_rect.centerx - sub_m.get_width() // 2, modal_rect.y + 64))

        ok_btn = pygame.Rect(modal_rect.centerx - 105, modal_rect.bottom - 62, 210, 44)
        draw_3d_button(screen, ok_btn, "В главное меню", (42, 148, 92), SMALL_FONT)
        return menu_rect, undo_rect, theme_rect, reset_rect, ok_btn

    return menu_rect, undo_rect, theme_rect, reset_rect, None


def animate_move(screen, game, start, end, clock):
    flip = (game.mode == "online" and game.my_color == "b")
    sr, sc = start
    er, ec = end
    piece = game.board[sr][sc]

    dsr = 7 - sr if flip else sr
    dsc = 7 - sc if flip else sc
    der = 7 - er if flip else er
    dec = 7 - ec if flip else ec

    start_x = OFFSET_X + dsc * SQ_SIZE
    start_y = OFFSET_Y + dsr * SQ_SIZE
    end_x = OFFSET_X + dec * SQ_SIZE
    end_y = OFFSET_Y + der * SQ_SIZE

    for i in range(1, 7):
        t = i / 6
        ease = 1 - (1 - t) ** 2
        cur_x = start_x + (end_x - start_x) * ease
        cur_y = start_y + (end_y - start_y) * ease
        draw_game_scene(screen, game, {'piece': piece, 'x': cur_x, 'y': cur_y, 'hide_pos': start})
        pygame.display.flip()
        clock.tick(60)


def main():
    global current_theme_idx, ai_difficulty
    clock = pygame.time.Clock()
    screen_state = "menu"
    game = None
    net = CodeNetworkManager()
    lobby_mode = "select"
    entered_code = ""
    ip_host_input = ""
    active_input_field = "code"
    ai_timer = 0

    while True:
        if screen_state == "menu":
            btn_1x1, btn_bot, btn_diff, btn_online, btn_theme = draw_main_menu(screen)
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos
                    if btn_1x1.collidepoint(mx, my):
                        play_snd(SND_CLICK)
                        game = ChessGame(mode="1x1")
                        screen_state = "game"
                    elif btn_bot.collidepoint(mx, my):
                        play_snd(SND_CLICK)
                        game = ChessGame(mode="bot")
                        screen_state = "game"
                    elif btn_diff.collidepoint(mx, my):
                        play_snd(SND_CLICK)
                        if ai_difficulty == "Лёгкий":
                            ai_difficulty = "Средний"
                        elif ai_difficulty == "Средний":
                            ai_difficulty = "Сложный"
                        else:
                            ai_difficulty = "Лёгкий"
                    elif btn_online.collidepoint(mx, my):
                        play_snd(SND_CLICK)
                        lobby_mode = "select"
                        entered_code = ""
                        ip_host_input = ""
                        active_input_field = "code"
                        net.close()
                        screen_state = "lobby"
                    elif btn_theme.collidepoint(mx, my):
                        play_snd(SND_CLICK)
                        current_theme_idx = (current_theme_idx + 1) % len(THEMES)

        elif screen_state == "lobby":
            ui = draw_code_lobby(screen, net, lobby_mode, entered_code, ip_host_input, active_input_field)
            pygame.display.flip()

            if net.connected:
                my_col = "w" if net.is_host else "b"
                game = ChessGame(mode="online", my_color=my_col)
                screen_state = "game"
                continue

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    net.close()
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos
                    if ui["back"].collidepoint(mx, my):
                        play_snd(SND_CLICK)
                        net.close()
                        screen_state = "menu"
                    elif lobby_mode == "select":
                        if ui["host"].collidepoint(mx, my):
                            play_snd(SND_CLICK)
                            lobby_mode = "hosting"
                            net.start_host()
                        elif ui["join"].collidepoint(mx, my):
                            play_snd(SND_CLICK)
                            lobby_mode = "joining"
                    elif lobby_mode == "joining":
                        if "code_box" in ui and ui["code_box"].collidepoint(mx, my):
                            play_snd(SND_CLICK)
                            active_input_field = "code"
                        elif "ip_box" in ui and ui["ip_box"].collidepoint(mx, my):
                            play_snd(SND_CLICK)
                            active_input_field = "ip"
                        else:
                            for k, kr in ui["keys"].items():
                                if kr.collidepoint(mx, my):
                                    play_snd(SND_CLICK)
                                    if active_input_field == "code":
                                        if k == "<-":
                                            entered_code = entered_code[:-1]
                                        elif k.isdigit() and len(entered_code) < 4:
                                            entered_code += k
                                            if len(entered_code) == 4 and not ip_host_input:
                                                active_input_field = "ip"
                                    elif active_input_field == "ip":
                                        if k == "<-":
                                            ip_host_input = ip_host_input[:-1]
                                        elif k != "<-" and len(ip_host_input) < 15:
                                            ip_host_input += k

                        if ui["connect"].collidepoint(mx, my) and len(entered_code) == 4 and ip_host_input:
                            play_snd(SND_CLICK)
                            net.connect_with_code(entered_code, ip_host_input)

        elif screen_state == "game":
            menu_rect, undo_rect, theme_rect, reset_rect, ok_btn = draw_game_scene(screen, game)
            pygame.display.flip()

            if game.mode == "online":
                if not net.connected and not game.game_over:
                    game.game_over = True
                    game.status_text = net.error or "Соединение разорвано"
                while net.incoming_moves:
                    msg = net.incoming_moves.pop(0)
                    s_pos = tuple(msg["start"])
                    e_pos = tuple(msg["end"])
                    animate_move(screen, game, s_pos, e_pos, clock)
                    game.make_move(s_pos, e_pos)

            if game.mode == "bot" and game.turn == 'b' and not game.game_over:
                ai_timer += 1
                if ai_timer >= 5:
                    ai_timer = 0
                    ai_move = game.get_best_ai_move()
                    if ai_move:
                        animate_move(screen, game, ai_move[0], ai_move[1], clock)
                        game.make_move(ai_move[0], ai_move[1])
                clock.tick(30)
                continue

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    net.close()
                    pygame.quit()
                    sys.exit()

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos

                    if game.game_over and ok_btn and ok_btn.collidepoint(mx, my):
                        play_snd(SND_CLICK)
                        net.close()
                        screen_state = "menu"
                        continue

                    if menu_rect.collidepoint(mx, my):
                        play_snd(SND_CLICK)
                        net.close()
                        screen_state = "menu"
                        continue

                    if theme_rect.collidepoint(mx, my):
                        play_snd(SND_CLICK)
                        current_theme_idx = (current_theme_idx + 1) % len(THEMES)
                        continue

                    if game.mode != "online":
                        if undo_rect.collidepoint(mx, my):
                            play_snd(SND_CLICK)
                            game.undo_move()
                            continue
                        if reset_rect.collidepoint(mx, my):
                            play_snd(SND_CLICK)
                            game.reset()
                            continue

                    if game.game_over:
                        continue

                    if game.mode == "online" and game.turn != game.my_color:
                        continue

                    if OFFSET_X <= mx < OFFSET_X + BOARD_SIZE and OFFSET_Y <= my < OFFSET_Y + BOARD_SIZE:
                        disp_c = (mx - OFFSET_X) // SQ_SIZE
                        disp_r = (my - OFFSET_Y) // SQ_SIZE
                        flip = (game.mode == "online" and game.my_color == "b")
                        row = 7 - disp_r if flip else disp_r
                        col = 7 - disp_c if flip else disp_c

                        if game.selected:
                            if (row, col) in game.valid_moves:
                                start_pos = game.selected
                                game.selected = None
                                game.valid_moves = []
                                animate_move(screen, game, start_pos, (row, col), clock)
                                game.make_move(start_pos, (row, col))
                                if game.mode == "online":
                                    net.send_move(start_pos, (row, col))
                                ai_timer = 0
                            elif game.board[row][col][0] == game.turn:
                                game.selected = (row, col)
                                game.valid_moves = game.get_legal_moves(row, col)
                            else:
                                game.selected = None
                                game.valid_moves = []
                        else:
                            if game.board[row][col][0] == game.turn:
                                game.selected = (row, col)
                                game.valid_moves = game.get_legal_moves(row, col)

        clock.tick(30)


if __name__ == "__main__":
    main()
