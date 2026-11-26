import kivy
kivy.require('2.1.0')

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
import threading
import socket
import json
import random

# --- ИГРОВАЯ ЛОГИКА (твой код) ---
PIECE_VALUES = {'P': 100, 'N': 320, 'B': 330, 'R': 500, 'Q': 900, 'K': 20000}
MATERIAL_PTS = {'P': 1, 'N': 3, 'B': 3, 'R': 5, 'Q': 9, 'K': 0}
UNICODE_PIECES = {
    'wK': '♔', 'wQ': '♕', 'wR': '♖', 'wB': '♗', 'wN': '♘', 'wP': '♙',
    'bK': '♚', 'bQ': '♛', 'bR': '♜', 'bB': '♝', 'bN': '♞', 'bP': '♟', '--': ''
}

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
        self.game_over = False
        self.move_count = 1

    def in_bounds(self, r, c):
        return 0 <= r < 8 and 0 <= c < 8

    def get_pseudo_moves(self, r, c, board):
        piece = board[r][c]
        if piece == '--': return []
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
            dirs = []
            if p_type in ['R', 'Q']: dirs.extend([(-1, 0), (1, 0), (0, -1), (0, 1)])
            if p_type in ['B', 'Q']: dirs.extend([(-1, -1), (-1, 1), (1, -1), (1, 1)])
            for dr, dc in dirs:
                nr, nc = r + dr, c + dc
                while self.in_bounds(nr, nc):
                    if board[nr][nc] == '--': moves.append((nr, nc))
                    elif board[nr][nc][0] != color:
                        moves.append((nr, nc))
                        break
                    else: break
                    nr += dr; nc += dc
        elif p_type == 'N':
            for dr, dc in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
                nr, nc = r + dr, c + dc
                if self.in_bounds(nr, nc) and (board[nr][nc] == '--' or board[nr][nc][0] != color):
                    moves.append((nr, nc))
        elif p_type == 'K':
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0: continue
                    nr, nc = r + dr, c + dc
                    if self.in_bounds(nr, nc) and (board[nr][nc] == '--' or board[nr][nc][0] != color):
                        moves.append((nr, nc))
        return moves

    def find_king(self, color, board):
        for r in range(8):
            for c in range(8):
                if board[r][c] == color + 'K': return (r, c)
        return None

    def is_in_check(self, color, board):
        king_pos = self.find_king(color, board)
        if not king_pos: return False
        enemy = 'b' if color == 'w' else 'w'
        for r in range(8):
            for c in range(8):
                if board[r][c][0] == enemy:
                    if king_pos in self.get_pseudo_moves(r, c, board): return True
        return False

    def get_legal_moves(self, r, c, board, turn):
        piece = board[r][c]
        if piece == '--' or piece[0] != turn: return []
        legal = []
        for nr, nc in self.get_pseudo_moves(r, c, board):
            temp = [row[:] for row in board]
            temp[nr][nc] = temp[r][c]; temp[r][c] = '--'
            if not self.is_in_check(turn, temp): legal.append((nr, nc))
        return legal

    def get_all_legal_moves(self, color, board):
        all_moves = []
        for r in range(8):
            for c in range(8):
                if board[r][c][0] == color:
                    for move in self.get_legal_moves(r, c, board, color):
                        all_moves.append(((r, c), move))
        return all_moves

    def make_move(self, start, end):
        sr, sc = start; er, ec = end
        piece = self.board[sr][sc]
        self.board[er][ec] = piece; self.board[sr][sc] = '--'
        if piece == 'wP' and er == 0: self.board[er][ec] = 'wQ'
        elif piece == 'bP' and er == 7: self.board[er][ec] = 'bQ'
        if self.turn == 'b': self.move_count += 1
        self.turn = 'b' if self.turn == 'w' else 'w'

    def get_best_ai_move(self):
        moves = self.get_all_legal_moves('b', self.board)
        if not moves: return None
        best_score = -999999
        best_moves = []
        for start, end in moves:
            temp = [row[:] for row in self.board]
            sr, sc = start; er, ec = end
            temp[er][ec] = temp[sr][sc]; temp[sr][sc] = '--'
            score = 0
            target = self.board[er][ec]
            if target != '--': score += PIECE_VALUES[target[1]] * 10
            score += (3.5 - abs(3.5 - er)) + (3.5 - abs(3.5 - ec))
            if score > best_score:
                best_score = score; best_moves = [(start, end)]
            elif score == best_score:
                best_moves.append((start, end))
        return random.choice(best_moves)

# --- СЕТЬ ---
class NetworkManager:
    def __init__(self):
        self.sock = None; self.conn = None; self.connected = False
        self.is_host = False; self.incoming_moves = []; self.running = False

    def start_host(self, code):
        self.is_host = True; self.running = True
        port = 10000 + int(code)
        def _host():
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.sock.bind(("0.0.0.0", port))
                self.sock.listen(1)
                self.conn, _ = self.sock.accept()
                self.connected = True; self._listen()
            except Exception: pass
        threading.Thread(target=_host, daemon=True).start()

    def connect(self, code, ip):
        self.running = True; port = 10000 + int(code)
        def _client():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((ip, port)); self.conn = s
                self.connected = True; self._listen()
            except Exception: pass
        threading.Thread(target=_client, daemon=True).start()

    def _listen(self):
        buf = ""
        while self.running and self.connected:
            try:
                data = self.conn.recv(1024).decode("utf-8")
                if not data: break
                buf += data
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    if line.strip(): self.incoming_moves.append(json.loads(line))
            except Exception: break

    def send(self, start, end):
        if self.connected and self.conn:
            try: self.conn.sendall((json.dumps({"start": start, "end": end}) + "\n").encode("utf-8"))
            except Exception: pass

# --- KIVY ИНТЕРФЕЙС ---
class MainMenu(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        layout = BoxLayout(orientation='vertical', padding=40, spacing=20)
        layout.add_widget(Label(text="[size=45][color=ffd700]♔ CHESS MASTER ♚[/color][/size]", markup=True, font_size='30sp'))
        
        btn_1x1 = Button(text="1x1 Локально", size_hint_y=None, height=70, background_color=(0.2,0.4,0.7,1), font_size='20sp')
        btn_1x1.bind(on_press=self.start_1x1)
        btn_bot = Button(text="Против ИИ", size_hint_y=None, height=70, background_color=(0.2,0.6,0.3,1), font_size='20sp')
        btn_bot.bind(on_press=self.start_bot)
        btn_online = Button(text="По сети", size_hint_y=None, height=70, background_color=(0.5,0.2,0.6,1), font_size='20sp')
        btn_online.bind(on_press=self.start_online)

        layout.add_widget(btn_1x1); layout.add_widget(btn_bot); layout.add_widget(btn_online)
        self.add_widget(layout)

    def start_1x1(self, i): self.manager.game = ChessGame(mode="1x1"); self.manager.current = 'game'
    def start_bot(self, i): self.manager.game = ChessGame(mode="bot"); self.manager.current = 'game'
    def start_online(self, i): self.manager.current = 'lobby'

class OnlineLobby(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        layout = BoxLayout(orientation='vertical', padding=30, spacing=15)
        self.status = Label(text="Введите код (4 цифры)")
        self.code_input = TextInput(hint_text="1234", input_filter='int', multiline=False, size_hint_y=None, height=60)
        self.ip_input = TextInput(hint_text="IP (127.0.0.1)", multiline=False, size_hint_y=None, height=60)
        
        btn_host = Button(text="Создать", size_hint_y=None, height=60, background_color=(0.2,0.6,0.3,1))
        btn_host.bind(on_press=self.host_game)
        btn_join = Button(text="Подключиться", size_hint_y=None, height=60, background_color=(0.2,0.4,0.7,1))
        btn_join.bind(on_press=self.join_game)
        btn_back = Button(text="Назад", size_hint_y=None, height=60, background_color=(0.6,0.2,0.2,1))
        btn_back.bind(on_press=self.go_back)

        layout.add_widget(self.status); layout.add_widget(self.code_input)
        layout.add_widget(self.ip_input); layout.add_widget(btn_host)
        layout.add_widget(btn_join); layout.add_widget(btn_back)
        self.add_widget(layout)

    def host_game(self, i):
        code = self.code_input.text
        if len(code) != 4: self.status.text = "Нужен код 4 цифры"; return
        self.manager.net = NetworkManager(); self.manager.net.start_host(code)
        self.status.text = f"Ожидание... Код: {code}"
        Clock.schedule_interval(self.check, 1)

    def join_game(self, i):
        code = self.code_input.text; ip = self.ip_input.text
        if len(code) != 4 or not ip: self.status.text = "Код и IP!"; return
        self.manager.net = NetworkManager(); self.manager.net.connect(code, ip)
        self.status.text = "Подключение..."
        Clock.schedule_interval(self.check, 1)

    def check(self, dt):
        if self.manager.net and self.manager.net.connected:
            my_col = "w" if self.manager.net.is_host else "b"
            self.manager.game = ChessGame(mode="online", my_color=my_col)
            self.manager.current = 'game'; return False
        return True

    def go_back(self, i): self.manager.current = 'menu'

class GameScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.layout = BoxLayout(orientation='vertical')
        
        self.status_label = Label(text="Ход белых", size_hint_y=0.1, font_size='24sp', bold=True)
        self.layout.add_widget(self.status_label)
        
        self.board_layout = GridLayout(cols=8, size_hint_y=0.75, spacing=2, padding=5)
        self.buttons = [[None for _ in range(8)] for _ in range(8)]
        for r in range(8):
            for c in range(8):
                btn = Button(font_size='35sp', background_normal='')
                btn.bind(on_press=lambda x, row=r, col=c: self.on_press(row, col))
                self.buttons[r][c] = btn
                self.board_layout.add_widget(btn)
        self.layout.add_widget(self.board_layout)
        
        bottom = BoxLayout(size_hint_y=0.15, spacing=10, padding=10)
        b_menu = Button(text="Меню", background_color=(0.3,0.3,0.3,1), font_size='18sp')
        b_menu.bind(on_press=lambda x: setattr(self.manager, 'current', 'menu'))
        b_res = Button(text="Сброс", background_color=(0.5,0.2,0.2,1), font_size='18sp')
        b_res.bind(on_press=self.reset)
        bottom.add_widget(b_menu); bottom.add_widget(b_res)
        self.layout.add_widget(bottom)
        self.add_widget(self.layout)

    def on_enter(self):
        self.update_board()
        Clock.schedule_interval(self.game_loop, 0.1)

    def on_leave(self):
        Clock.unschedule(self.game_loop)

    def game_loop(self, dt):
        game = self.manager.game
        if game.mode == "online" and self.manager.net:
            while self.manager.net.incoming_moves:
                m = self.manager.net.incoming_moves.pop(0)
                game.make_move(tuple(m["start"]), tuple(m["end"]))
                self.update_board()
        if game.mode == "bot" and game.turn == 'b' and not game.game_over:
            Clock.schedule_once(self.ai_move, 0.5)
        self.update_status()

    def ai_move(self, dt):
        game = self.manager.game
        if game.mode == "bot" and game.turn == 'b' and not game.game_over:
            m = game.get_best_ai_move()
            if m:
                game.make_move(m[0], m[1]); self.update_board()

    def on_press(self, r, c):
        game = self.manager.game
        if game.game_over: return
        if game.mode == "online" and game.turn != game.my_color: return

        if game.selected:
            if (r, c) in game.valid_moves:
                start = game.selected; game.selected = None; game.valid_moves = []
                game.make_move(start, (r, c))
                if game.mode == "online" and self.manager.net: self.manager.net.send(start, (r, c))
                self.update_board(); self.check_over()
            elif game.board[r][c][0] == game.turn:
                game.selected = (r, c); game.valid_moves = game.get_legal_moves(r, c, game.board, game.turn)
                self.update_board()
            else:
                game.selected = None; game.valid_moves = []; self.update_board()
        else:
            if game.board[r][c][0] == game.turn:
                game.selected = (r, c); game.valid_moves = game.get_legal_moves(r, c, game.board, game.turn)
                self.update_board()

    def update_board(self):
        game = self.manager.game
        flip = (game.mode == "online" and game.my_color == "b")
        for r in range(8):
            for c in range(8):
                ar = 7 - r if flip else r; ac = 7 - c if flip else c
                piece = game.board[ar][ac]
                self.buttons[r][c].text = UNICODE_PIECES[piece]
                self.buttons[r][c].color = (1,1,1,1) if piece[0] == 'w' else (0,0,0,1)
                
                col = (0.9,0.9,0.9,1) if (ar+ac)%2==0 else (0.45,0.45,0.45,1)
                if game.selected == (ar, ac): col = (0.9, 0.9, 0.2, 1)
                elif (ar, ac) in game.valid_moves: col = (0.4, 0.8, 0.4, 1)
                self.buttons[r][c].background_color = col

    def update_status(self):
        game = self.manager.game
        if game.game_over: self.status_label.text = "Игра окончена!"
        else:
            if game.is_in_check(game.turn, game.board):
                self.status_label.text = f"ШАХ {'белым' if game.turn == 'w' else 'черным'}! (Ход {game.move_count})"
            else:
                self.status_label.text = f"Ход {'белых' if game.turn == 'w' else 'черных'} (Ход {game.move_count})"

    def check_over(self):
        game = self.manager.game
        if not game.get_all_legal_moves(game.turn, game.board):
            game.game_over = True
            self.status_label.text = "МАТ!" if game.is_in_check(game.turn, game.board) else "ПАТ (Ничья)!"

    def reset(self, i):
        self.manager.game.reset(); self.update_board()

class ChessApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(MainMenu(name='menu'))
        sm.add_widget(OnlineLobby(name='lobby'))
        sm.add_widget(GameScreen(name='game'))
        sm.game = None; sm.net = None
        Window.clearcolor = (0.1, 0.1, 0.15, 1)
        return sm

if __name__ == '__main__':
    ChessApp().run()