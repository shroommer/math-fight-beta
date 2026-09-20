"""Math Fight: a graph-powered arithmetic duel.

Run with: python main.py
The game uses only the Python standard library so it is easy to share.
"""

from __future__ import annotations

import math
import json
import os
import random
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
import pygame
import numpy as np

WIDTH, HEIGHT = 1280, 760
GRAPH = pygame.Rect(310, 118, 930, 590)
X_MIN, X_MAX = -10.0, 10.0
Y_MIN, Y_MAX = -6.0, 12.0

BG = (8, 13, 27)
PANEL = (17, 27, 48)
PANEL_LIGHT = (24, 38, 65)
TEXT = (215, 225, 240)
MUTED = (112, 132, 160)
CYAN = (103, 232, 249)
ORB_GREEN = (0, 255, 0)
GOLD = (251, 191, 36)
RED = (251, 113, 133)
TAGS = ("PLAYER", "SUPPORTER", "DEVELOPER", "ADMIN", "OWNER")
CPU_DAMAGE = 10
CPU_MOVE_STEP = 0.12
CPU_FIRE_INTERVAL = 2

PRESETS = [
	("RISING LINE", "x + 2", lambda x: x + 2),
	("FALLING LINE", "-x - 1", lambda x: -x - 1),
	("VORTEX", "x^2 - 3", lambda x: x * x - 3),
	("WAVE", "3 sin(x)", lambda x: 3 * np.sin(x)),
	("SHIELD ARC", "-0.35x^2 + 5", lambda x: -0.35 * x * x + 5),
	("ZIGZAG", "2 cos(1.5x)", lambda x: 2 * np.cos(1.5 * x)),
]

SHOP_PRESETS = [
	("LINE BOOST", "x + 4", lambda x: x + 4, 180, 0),
	("TWIN WAVE", "2 sin(1.6x)", lambda x: 2 * np.sin(1.6 * x), 260, 0),
	("FLARE ARC", "-0.6x^2 + 7", lambda x: -0.6 * x * x + 7, 420, 0),
	("CUSTOM PRESET", "x^2 - 2", lambda x: x * x - 2, 1000, 50),
]

RANKS = [
	"0 YEAR OLD",
	"NERD",
	"PRO",
	"ALFRED EINSTEIN",
	"ALBERT",
	"EINSTEIN",
	"ALBERT EINSTEIN",
	"ALBERT EINSTEIN 2X",
	"ALBERT EINSTEIN 3X",
	"ALBERT EINSTEIN 4X",
	"ALBERT EINSTEIN 5X",
]

@dataclass
class Fighter:
	name: str
	color: tuple[int, int, int]
	x: float
	y: float
	hp: int = 100

class MathFight:
	def __init__(self) -> None:
		pygame.init()
		pygame.display.set_caption("MATH FIGHT // graph arena")
		self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
		self.clock = pygame.time.Clock()
		self.font = pygame.font.Font(None, 26)
		self.small = pygame.font.Font(None, 20)
		self.title = pygame.font.Font(None, 64)
		self.mode = "menu"
		self.last_mode = "preset"
		self.result = ""
		self.reward_paid = False
		self.save_path = Path(__file__).with_name("math_fight_save.json")
		(
			self.coins,
			self.diamonds,
			self.mustache,
			self.unlocked_preset_names,
			self.custom_preset_unlocked,
			self.custom_preset_equation,
			self.total_wins,
			self.username,
			self.users,
			self.settings,
			self.achievements,
			self.best_combo,
			self.total_battles,
			self.best_streak,
			self.daily_challenge_index,
			self.daily_challenge_progress,
			self.daily_challenge_date,
		) = self.load_save()
		self.settings = self.settings or {
			"sound": True,
			"reduced_motion": False,
			"show_tips": True,
		}
		self.achievements = self.achievements or {
			"first_win": False,
			"showdown": False,
			"coin_collector": False,
			"graph_guru": False,
			"ranked_up": False,
			"legend": False,
		}
		self.shop_status = "Customize your orb."
		self.search_query = ""
		self.search_input_active = False
		self.name_edit_text = self.username
		self.name_edit_active = False
		self.saved_username = self.username
		self.owner_username = self.load_owner_username()
		self.user_tag = self.user_tag_for(self.username)
		self.tag_target_name = ""
		self.admin_selected_name = ""
		configured_server = os.environ.get("MATH_FIGHT_SERVER_URL", "").strip().rstrip("/")
		self.online_server_url = configured_server
		self.online_server_candidates = [
			candidate for candidate in [
				configured_server,
				"http://math-fight-pi.local:8765",
				"http://raspberrypi.local:8765",
				"http://127.0.0.1:8765",
			] if candidate
		]
		self.online_users: list[dict] = []
		self.online_status = "AUTO-CONNECT // searching for profile server..."
		self.level_name = "untitled_arena"
		self.level_description = ""
		self.level_points: list[tuple[float, float]] = []
		self.level_input_active = False
		self.level_status = "Click the arena to place targets."
		self.mustache_orb = self.load_mustache_orb()
		self.settings.setdefault("sound", True)
		self.settings.setdefault("reduced_motion", False)
		self.settings.setdefault("show_tips", True)
		self.achievements.setdefault("first_win", False)
		self.achievements.setdefault("showdown", False)
		self.achievements.setdefault("coin_collector", False)
		self.achievements.setdefault("graph_guru", False)
		self.achievements.setdefault("ranked_up", False)
		self.achievements.setdefault("legend", False)
		self.selected = 0
		self.input_text = "x^2 - 3"
		self.input_active = False
		self.preview_phase = 0.0
		self.tutorial_page = 0
		self.weapon_shop_status = "Buy new graph weapons for your arsenal."
		self.tutorial_pages = [
			(
				"WELCOME",
				[
					"Math Fight is a short arcade duel where you draw graphs to attack.",
					"Your orb starts on the left side of the arena, and the CPU starts on the right.",
					"Build a graph, fire it, and try to cross the enemy before they cross you.",
				],
			),
			(
				"CHOOSE YOUR WEAPON",
				[
					"Use a preset weapon for fast play or switch to hard mode to type your own equation.",
					"The preview updates live so you can test your curve before you commit to a shot.",
					"Try formulas such as x^2 - 3, x + 2, or 2*cos(1.5*x).",
				],
			),
			(
				"ATTACK & DAMAGE",
				[
					"If a graph crosses the enemy, it deals 25 damage.",
					"If the CPU crosses your orb, it deals 10 damage on its turn.",
					"A match lasts three rounds, and the fighter with more HP wins.",
				],
			),
			(
				"MOVE SMART",
				[
					"Use W, A, S, D or the arrow keys to shift your orb before firing.",
					"The CPU also advances toward you, so timing matters more than raw power.",
					"Aim for the enemy path, not just the center of the arena.",
				],
			),
			(
				"WIN A ROUND",
				[
					"Fire a graph, watch the preview, and make the curve pass through the target area.",
					"The best strategy is to predict the enemy lane and strike before they reach you.",
					"Press ENTER to fire, R to reset, and ESC to return to the menu.",
				],
			),
		]
		self.round_number = 1
		self.status = "Choose a graph weapon, then FIRE."
		self.player = Fighter("YOU", ORB_GREEN, -6.5, -3.7)
		self.cpu = Fighter("CPU", RED, 6.5, 3.7)
		self.cpu_equation = ""
		self.cpu_turn_number = 0
		self.player_curve: list[tuple[float, float]] = []
		self.cpu_curve: list[tuple[float, float]] = []

	def text(self, value: str, x: int, y: int, color=TEXT, font=None) -> None:
		surface = (font or self.font).render(value, True, color)
		self.screen.blit(surface, (x, y))

	def load_owner_username(self) -> str:
		try:
			data = json.loads(self.save_path.read_text(encoding="utf-8"))
			return str(data.get("owner_username") or self.username)
		except (OSError, ValueError, TypeError, json.JSONDecodeError):
			return self.username

	def user_tag_for(self, username: str) -> str:
		if username == self.owner_username:
			return "OWNER"
		for user in self.users:
			if isinstance(user, dict) and str(user.get("name", "")) == username:
				tag = str(user.get("tag", "PLAYER")).upper()
				return tag if tag in TAGS else "PLAYER"
		return "PLAYER"

	def owner_access(self) -> bool:
		if self.username == self.owner_username:
			return True
		return any(
			isinstance(user, dict)
			and str(user.get("name", "")) == self.username
			and str(user.get("tag", "")).upper() == "OWNER"
			for user in self.users
		)

	def online_request(self, method: str, path: str, payload: dict | None = None) -> object:
		body = None
		headers = {"Accept": "application/json"}
		if payload is not None:
			body = json.dumps(payload).encode("utf-8")
			headers["Content-Type"] = "application/json"
		request = urllib.request.Request(f"{self.online_server_url}{path}", data=body, headers=headers, method=method)
		with urllib.request.urlopen(request, timeout=2.5) as response:
			return json.loads(response.read().decode("utf-8"))

	def discover_online_server(self) -> bool:
		if self.online_server_url:
			return True
		for candidate in self.online_server_candidates:
			try:
				with urllib.request.urlopen(f"{candidate}/health", timeout=0.6) as response:
					if response.status == 200:
						self.online_server_url = candidate
						return True
			except (OSError, urllib.error.URLError):
				continue
		return False

	def sync_online_profile(self) -> None:
		if not self.discover_online_server():
			self.online_status = "OFFLINE // profile server not found"
			return
		try:
			self.online_request("POST", "/profiles", {
				"name": self.username,
				"tag": self.user_tag,
				"coins": self.coins,
				"diamonds": self.diamonds,
				"wins": self.total_wins,
			})
			self.online_status = f"ONLINE // {self.online_server_url}"
		except (OSError, ValueError, TypeError, json.JSONDecodeError, urllib.error.URLError):
			self.online_status = "OFFLINE // start math_fight_server.py on the host PC"

	def refresh_online_users(self) -> None:
		if not self.discover_online_server():
			self.online_users = []
			self.online_status = "OFFLINE // profile server not found"
			return
		try:
			query = urllib.parse.quote(self.search_query)
			result = self.online_request("GET", f"/profiles?q={query}")
			self.online_users = result if isinstance(result, list) else []
			self.online_status = f"ONLINE // {len(self.online_users)} shared profiles"
		except (OSError, ValueError, TypeError, json.JSONDecodeError, urllib.error.URLError):
			self.online_users = []
			self.online_status = "OFFLINE // start math_fight_server.py on the host PC"

	def assign_tag(self, username: str, tag: str) -> None:
		if not self.owner_access() or username == self.owner_username or tag not in TAGS[:-1]:
			return
		for user in self.users:
			if isinstance(user, dict) and str(user.get("name", "")) == username:
				user["tag"] = tag
				self.tag_target_name = username
				self.save()
				return

	def draw_background(self) -> None:
		self.screen.fill(BG)
		width, height = self.screen.get_size()
		for x in range(0, width, 40):
			pygame.draw.line(self.screen, (14, 27, 47), (x, 0), (x, height), 1)
		for y in range(0, height, 40):
			pygame.draw.line(self.screen, (14, 27, 47), (0, y), (width, y), 1)
		pygame.draw.line(self.screen, (36, 69, 88), (0, height - 82), (width, height - 82), 1)

	def panel(self, rect: pygame.Rect, fill=(17, 27, 48, 238), border=(74, 101, 129, 115), radius=12) -> None:
		shadow = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
		pygame.draw.rect(shadow, (0, 0, 0, 105), shadow.get_rect(), border_radius=radius)
		self.screen.blit(shadow, (rect.x + 5, rect.y + 7))
		card = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
		pygame.draw.rect(card, fill, card.get_rect(), border_radius=radius)
		pygame.draw.rect(card, border, card.get_rect(), 1, border_radius=radius)
		self.screen.blit(card, rect.topleft)

	def button(self, rect: pygame.Rect, label: str, detail: str, color=CYAN) -> None:
		mouse = pygame.mouse.get_pos()
		hover = rect.collidepoint(mouse)
		shadow = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
		pygame.draw.rect(shadow, (0, 0, 0, 100), shadow.get_rect(), border_radius=10)
		self.screen.blit(shadow, (rect.x + 5, rect.y + 7))
		card = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
		pygame.draw.rect(card, (17, 29, 49, 245), card.get_rect(), border_radius=10)
		pygame.draw.rect(card, (*color, 185) if hover else (34, 54, 76, 220), (1, 1, rect.w - 2, 58), border_radius=9)
		pygame.draw.line(card, (*color, 180), (18, 60), (rect.w - 18, 60), 1)
		self.screen.blit(card, rect.topleft)
		label_surface = self.font.render(label, True, BG if hover else TEXT)
		self.screen.blit(label_surface, label_surface.get_rect(midleft=(rect.x + 18, rect.y + 30)))
		if rect.h >= 80:
			self.text(detail, rect.x + 18, rect.y + 78, (173, 193, 216), self.small)
		if hover:
			pygame.draw.line(self.screen, color, (rect.x + 18, rect.bottom - 10), (rect.right - 18, rect.bottom - 10), 2)

	@property
	def available_presets(self) -> list[tuple[str, str, object]]:
		presets = list(PRESETS)
		for name, equation, function, _, _ in SHOP_PRESETS:
			if name == "CUSTOM PRESET":
				if self.custom_preset_unlocked:
					presets.append(("CUSTOM PRESET", self.custom_preset_equation, lambda x, eq=self.custom_preset_equation: self.parse_equation(eq)(x)))
				continue
			if name in self.unlocked_preset_names:
				presets.append((name, equation, function))
		return presets

	def preset_buttons(self) -> list[tuple[int, pygame.Rect]]:
		buttons: list[tuple[int, pygame.Rect]] = []
		for index in range(len(self.available_presets)):
			column = index % 2
			row = index // 2
			buttons.append((index, pygame.Rect(16 + column * 128, 160 + row * 54, 118, 42)))
		return buttons

	def preset_preview_y(self) -> int:
		buttons = self.preset_buttons()
		if not buttons:
			return 330
		last_rect = buttons[-1][1]
		return max(330, last_rect.bottom + 16)

	def level_file_path(self) -> Path:
		clean_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", self.level_name.strip()).strip("_") or "untitled_arena"
		return Path(__file__).with_name(f"{clean_name}.mfl")

	def save_level(self) -> None:
		payload = {
			"format": "math-fight-level",
			"version": 1,
			"name": self.level_name.strip() or "untitled_arena",
			"description": self.level_description.strip(),
			"author": self.username,
			"author_tag": self.user_tag,
			"targets": [{"x": round(x, 4), "y": round(y, 4)} for x, y in self.level_points],
		}
		try:
			self.level_file_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")
			self.level_status = f"Saved {self.level_file_path().name}"
		except OSError:
			self.level_status = "Could not save this level."

	def load_level(self) -> None:
		paths = sorted(Path(__file__).parent.glob("*.mfl"), key=lambda path: path.stat().st_mtime, reverse=True)
		if not paths:
			self.level_status = "No .mfl levels found yet."
			return
		try:
			data = json.loads(paths[0].read_text(encoding="utf-8"))
			self.level_name = str(data.get("name", paths[0].stem))
			self.level_description = str(data.get("description", ""))
			self.level_points = [
				(float(target["x"]), float(target["y"]))
				for target in data.get("targets", [])
				if isinstance(target, dict) and "x" in target and "y" in target
			]
			self.level_status = f"Loaded {paths[0].name}"
		except (OSError, ValueError, TypeError, json.JSONDecodeError, KeyError):
			self.level_status = "That .mfl file is invalid."

	def level_editor(self) -> None:
		self.draw_background()
		self.text("LEVEL EDITOR", 54, 48, CYAN, self.title)
		self.text("BUILD A GRAPH ARENA / SAVE IT AS .MFL", 58, 112, GOLD, self.font)
		canvas = pygame.Rect(330, 140, 880, 500)
		self.panel(canvas, fill=(10, 20, 36, 245), border=(61, 113, 135, 150), radius=10)
		for x in range(canvas.left + 40, canvas.right, 40):
			pygame.draw.line(self.screen, (24, 49, 68), (x, canvas.top), (x, canvas.bottom), 1)
		for y in range(canvas.top + 40, canvas.bottom, 40):
			pygame.draw.line(self.screen, (24, 49, 68), (canvas.left, y), (canvas.right, y), 1)
		for point_x, point_y in self.level_points:
			pixel = (canvas.left + int(point_x * canvas.width), canvas.top + int(point_y * canvas.height))
			pygame.draw.circle(self.screen, GOLD, pixel, 8)
			pygame.draw.circle(self.screen, GOLD, pixel, 15, 1)
		self.text("LEVEL NAME", 54, 170, MUTED, self.small)
		name_box = pygame.Rect(54, 194, 230, 42)
		pygame.draw.rect(self.screen, (19, 35, 56), name_box, border_radius=7)
		pygame.draw.rect(self.screen, CYAN if self.level_input_active else MUTED, name_box, 2, border_radius=7)
		self.text(self.level_name, name_box.x + 12, name_box.y + 11, TEXT, self.small)
		self.text("Click inside the arena to add targets.", 54, 270, TEXT, self.small)
		self.text("Click a target again to remove it.", 54, 296, MUTED, self.small)
		self.text(f"TARGETS {len(self.level_points):02d}", 54, 344, GOLD, self.font)
		self.text(self.level_status, 54, 382, CYAN, self.small)
		for rect, label in [(pygame.Rect(54, 450, 230, 46), "SAVE .MFL"), (pygame.Rect(54, 510, 230, 46), "LOAD LATEST")]:
			pygame.draw.rect(self.screen, GOLD if label.startswith("SAVE") else PANEL_LIGHT, rect, border_radius=8)
			self.text(label, rect.x + 62, rect.y + 14, BG if label.startswith("SAVE") else TEXT, self.small)
		self.text("ESC  BACK TO MENU", 54, 680, MUTED, self.small)

	def admin_panel(self) -> None:
		self.draw_background()
		self.text("ADMIN PANEL", 54, 48, CYAN, self.title)
		self.text("OWNER CONTROLS / LOCAL PROFILE DATA", 58, 112, GOLD, self.font)
		if not self.owner_access():
			self.panel(pygame.Rect(270, 220, 740, 180), fill=(45, 22, 36, 245), border=(251, 113, 133, 150), radius=10)
			self.text("ACCESS DENIED", 500, 270, RED, self.title)
			self.text("Only the owner account can open this panel.", 430, 330, TEXT, self.small)
			return
		users_panel = pygame.Rect(54, 150, 700, 500)
		self.panel(users_panel, fill=(10, 20, 36, 245), border=(61, 113, 135, 150), radius=10)
		self.text("USER TAGS", users_panel.x + 24, users_panel.y + 22, GOLD, self.font)
		for index, user in enumerate(self.users[:8]):
			row = pygame.Rect(users_panel.x + 24, users_panel.y + 70 + index * 48, 650, 38)
			name = str(user.get("name", "PLAYER"))
			selected = name == self.admin_selected_name
			pygame.draw.rect(self.screen, (30, 74, 91) if selected else (18, 30, 52), row, border_radius=7)
			user_tag = "OWNER" if name == self.owner_username else str(user.get("tag", "PLAYER")).upper()
			self.text(name, row.x + 12, row.y + 10, CYAN if selected else TEXT, self.small)
			self.text(user_tag, row.x + 430, row.y + 10, GOLD, self.small)
		self.text("CLICK TO SELECT", 790, 185, MUTED, self.small)
		self.text(f"SELECTED: {self.admin_selected_name or 'NONE'}", 790, 230, TEXT, self.small)
		for index, tag in enumerate(TAGS[:-1]):
			rect = pygame.Rect(790, 270 + index * 54, 270, 42)
			pygame.draw.rect(self.screen, GOLD if index == 0 else PANEL_LIGHT, rect, border_radius=8)
			self.text(f"{index + 1}  {tag}", rect.x + 26, rect.y + 13, BG if index == 0 else TEXT, self.small)
		self.text(f"MFL LEVELS: {len(list(Path(__file__).parent.glob('*.mfl')))}", 790, 535, CYAN, self.font)
		self.text("Select a user, then click a tag.", 790, 575, MUTED, self.small)
		self.text("ESC  BACK TO MENU", 54, 680, MUTED, self.small)

	def menu(self) -> None:
		self.draw_background()

		hero = pygame.Rect(56, 60, 1168, 188)
		self.panel(hero, radius=14)
		pygame.draw.line(self.screen, CYAN, (hero.x + 28, hero.y + 28), (hero.x + 28, hero.bottom - 28), 3)
		self.text("MATH FIGHT", hero.x + 42, hero.y + 48, CYAN, self.title)
		self.text("DRAW THE LINE. BREAK THE LINE.", hero.x + 48, hero.y + 122, GOLD, self.font)
		self.text(f"PLAYER: {self.username}", hero.x + 48, hero.y + 156, TEXT, self.small)
		self.text(f"{self.user_tag} // OFFLINE 1 PLAYER VS CPU", hero.x + 48, hero.y + 176, MUTED, self.small)

		currency_bar = pygame.Rect(905, 80, 285, 94)
		self.panel(currency_bar, fill=(10, 18, 34, 220), border=(61, 88, 116, 100), radius=10)
		self.text(f"COINS {self.coins:04d}", currency_bar.x + 18, currency_bar.y + 20, GOLD, self.font)
		self.text(f"DIAMONDS {self.diamonds:02d}", currency_bar.x + 18, currency_bar.y + 42, (168, 130, 255), self.small)
		rank_name, _, next_rank, wins = self.current_rank()
		self.text("RANK", currency_bar.x + 18, currency_bar.y + 62, CYAN, self.small)
		self.text(rank_name, currency_bar.x + 68, currency_bar.y + 62, CYAN, self.small)
		if next_rank:
			self.text(f"NEXT {next_rank}", currency_bar.x + 18, currency_bar.y + 80, GOLD, self.small)

		self.button(pygame.Rect(74, 300, 340, 148), "PRESET ARSENAL", "Verified equation weapons", CYAN)
		self.button(pygame.Rect(470, 300, 340, 148), "HARD MODE", "Type it yourself. No preview.", GOLD)
		self.button(pygame.Rect(866, 300, 340, 148), "ORB LAB", "Spend coins and diamonds", (168, 130, 255))
		self.button(pygame.Rect(72, 494, 220, 54), "HOW TO PLAY", "Clear step-by-step guide", GOLD)
		self.button(pygame.Rect(72, 560, 220, 54), "SEARCH USERS", "See every saved player", (168, 130, 255))
		self.button(pygame.Rect(320, 494, 220, 54), "CHALLENGES", "Daily goals and trophies", CYAN)
		self.button(pygame.Rect(320, 560, 220, 54), "RANK BOARD", "Local leaderboard", (168, 130, 255))
		self.button(pygame.Rect(560, 494, 220, 54), "SETTINGS", "Audio, motion, tips", GOLD)
		self.button(pygame.Rect(560, 560, 220, 54), "PROFILE", "Stats and unlocks", CYAN)
		self.button(pygame.Rect(866, 560, 340, 54), "LEVEL EDITOR", "Create and save .mfl arenas", GOLD)

		weapon_shop = pygame.Rect(866, 494, 340, 54)
		mouse = pygame.mouse.get_pos()
		weapon_hover = weapon_shop.collidepoint(mouse)
		shop_panel = pygame.Surface((weapon_shop.w, weapon_shop.h), pygame.SRCALPHA)
		pygame.draw.rect(shop_panel, (20, 33, 58, 220), shop_panel.get_rect(), border_radius=14)
		pygame.draw.rect(shop_panel, (168, 130, 255, 200) if weapon_hover else (168, 130, 255, 140), (10, 10, weapon_shop.w - 20, weapon_shop.h - 20), border_radius=10)
		self.screen.blit(shop_panel, weapon_shop.topleft)
		self.text("WEAPON SHOP", weapon_shop.x + 88, weapon_shop.y + 17, BG if weapon_hover else TEXT, self.small)

		# animated floating orb preview
		orb_x = 1125 + math.sin(self.preview_phase * 1.2) * 14
		orb_y = 604 + math.cos(self.preview_phase * 1.5) * 12
		orb_scale = 92 + math.sin(self.preview_phase * 1.8) * 9
		glow_orb = pygame.Surface((180, 180), pygame.SRCALPHA)
		pygame.draw.circle(glow_orb, (103, 232, 249, 35), (90, 90), 74 + int(math.sin(self.preview_phase) * 12))
		self.screen.blit(glow_orb, (orb_x - 90, orb_y - 90))
		self.draw_mustache_orb((int(orb_x), int(orb_y)), int(orb_scale))

		self.text("GRAPH ARENA / PREVIEW READY", 74, 692, GOLD, self.small)

	def name_edit(self) -> None:
		self.menu()
		overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
		overlay.fill((8, 13, 27, 170))
		self.screen.blit(overlay, (0, 0))
		window = pygame.Rect(260, 180, 760, 260)
		shadow = pygame.Surface((window.w, window.h), pygame.SRCALPHA)
		pygame.draw.rect(shadow, (0, 0, 0, 120), shadow.get_rect(), border_radius=26)
		self.screen.blit(shadow, (window.x + 12, window.y + 14))
		panel = pygame.Surface((window.w, window.h), pygame.SRCALPHA)
		pygame.draw.rect(panel, (17, 27, 48, 240), panel.get_rect(), border_radius=26)
		pygame.draw.rect(panel, (25, 40, 68, 190), (14, 14, window.w - 28, window.h - 28), border_radius=22)
		self.screen.blit(panel, window.topleft)
		self.text("CHANGE NAME", window.x + 38, window.y + 28, GOLD, self.title)
		self.text("THIS IS SAVED TO YOUR PROFILE", window.x + 38, window.y + 88, MUTED, self.small)
		name_box = pygame.Rect(window.x + 38, window.y + 118, 420, 44)
		pygame.draw.rect(self.screen, (26, 42, 68), name_box, border_radius=8)
		pygame.draw.rect(self.screen, CYAN if self.name_edit_active else MUTED, name_box, 2, border_radius=8)
		self.text(self.name_edit_text or "PLAYER", name_box.x + 14, name_box.y + 12, TEXT, self.font)
		cancel = pygame.Rect(window.x + 38, window.y + 180, 150, 48)
		confirm = pygame.Rect(window.x + 220, window.y + 180, 150, 48)
		for rect, label, active in [(cancel, "CANCEL", True), (confirm, "SAVE", True)]:
			mouse = pygame.mouse.get_pos()
			hover = rect.collidepoint(mouse)
			pygame.draw.rect(self.screen, CYAN if hover else PANEL_LIGHT, rect, border_radius=12)
			self.text(label, rect.x + 42, rect.y + 16, BG if hover else TEXT, self.small)
		self.text("PRESS ENTER TO SAVE • ESC TO GO BACK", window.x + 38, window.y + 220, MUTED, self.small)

	def leaderboard(self) -> None:
		self.menu()
		overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
		overlay.fill((8, 13, 27, 170))
		self.screen.blit(overlay, (0, 0))
		window = pygame.Rect(180, 115, 920, 560)
		panel = pygame.Surface((window.w, window.h), pygame.SRCALPHA)
		pygame.draw.rect(panel, (17, 27, 48, 240), panel.get_rect(), border_radius=26)
		self.screen.blit(panel, window.topleft)
		self.text("LOCAL RANK BOARD", window.x + 38, window.y + 30, GOLD, self.title)
		ri = [entry for entry in self.users if isinstance(entry, dict)]
		ri = sorted(ri, key=lambda e: (int(e.get("wins", 0)), int(e.get("coins", 0)), int(e.get("diamonds", 0))), reverse=True)[:8]
		for index, user in enumerate(ri):
			card = pygame.Rect(window.x + 40, window.y + 110 + index * 56, 840, 46)
			pygame.draw.rect(self.screen, (18, 30, 52), card, border_radius=10)
			self.text(f"#{index + 1} {user.get('name', 'PLAYER')}", card.x + 18, card.y + 12, CYAN if index == 0 else TEXT, self.font)
			self.text(f"{self.rank_label(int(user.get('wins', 0)))}", card.x + 420, card.y + 12, GOLD, self.small)
			self.text(f"{int(user.get('coins', 0))}c", card.x + 620, card.y + 12, GOLD, self.small)
			self.text(f"{int(user.get('diamonds', 0))}d", card.x + 720, card.y + 12, (168, 130, 255), self.small)
		close = pygame.Rect(window.x + 720, window.y + 470, 150, 54)
		pygame.draw.rect(self.screen, CYAN, close, border_radius=12)
		self.text("CLOSE", close.x + 48, close.y + 18, BG, self.small)

	def profile(self) -> None:
		self.menu()
		overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
		overlay.fill((8, 13, 27, 170))
		self.screen.blit(overlay, (0, 0))
		window = pygame.Rect(210, 130, 860, 520)
		panel = pygame.Surface((window.w, window.h), pygame.SRCALPHA)
		pygame.draw.rect(panel, (17, 27, 48, 240), panel.get_rect(), border_radius=26)
		self.screen.blit(panel, window.topleft)
		self.text("PLAYER PROFILE", window.x + 38, window.y + 32, GOLD, self.title)
		self.text(f"{self.username}  [{self.user_tag}]", window.x + 38, window.y + 100, CYAN, self.font)
		self.text(f"RANK {self.current_rank()[0]}", window.x + 38, window.y + 130, TEXT, self.small)
		self.text(f"WINS {self.total_wins}   BEST STREAK {self.best_streak}   BATTLES {self.total_battles}", window.x + 38, window.y + 170, TEXT, self.small)
		self.text(f"COINS {self.coins}   DIAMONDS {self.diamonds}   BEST COMBO {self.best_combo}", window.x + 38, window.y + 200, TEXT, self.small)
		edit_name = pygame.Rect(window.x + 500, window.y + 82, 180, 42)
		edit_hover = edit_name.collidepoint(pygame.mouse.get_pos())
		pygame.draw.rect(self.screen, CYAN if edit_hover else PANEL_LIGHT, edit_name, border_radius=8)
		self.text("CHANGE NAME", edit_name.x + 38, edit_name.y + 13, BG if edit_hover else TEXT, self.small)
		if self.owner_access():
			admin_button = pygame.Rect(window.x + 500, window.y + 140, 180, 42)
			admin_hover = admin_button.collidepoint(pygame.mouse.get_pos())
			pygame.draw.rect(self.screen, GOLD if admin_hover else PANEL_LIGHT, admin_button, border_radius=8)
			self.text("ADMIN PANEL", admin_button.x + 38, admin_button.y + 13, BG if admin_hover else TEXT, self.small)
		for i, (key, label) in enumerate([
			("first_win", "FIRST WIN"),
			("showdown", "SHOWDOWN"),
			("coin_collector", "COIN COLLECTOR"),
			("graph_guru", "GRAPH GURU"),
			("ranked_up", "RANKED UP"),
			("legend", "LEGEND"),
		]):
			rect = pygame.Rect(window.x + 38, window.y + 250 + i * 42, 320, 30)
			pygame.draw.rect(self.screen, (18, 30, 52), rect, border_radius=8)
			self.text(label, rect.x + 12, rect.y + 7, CYAN if self.achievements.get(key, False) else MUTED, self.small)
		close = pygame.Rect(window.x + 690, window.y + 440, 150, 54)
		pygame.draw.rect(self.screen, CYAN, close, border_radius=12)
		self.text("CLOSE", close.x + 48, close.y + 18, BG, self.small)

	def settings(self) -> None:
		self.menu()
		overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
		overlay.fill((8, 13, 27, 170))
		self.screen.blit(overlay, (0, 0))
		window = pygame.Rect(250, 160, 780, 420)
		panel = pygame.Surface((window.w, window.h), pygame.SRCALPHA)
		pygame.draw.rect(panel, (17, 27, 48, 240), panel.get_rect(), border_radius=26)
		self.screen.blit(panel, window.topleft)
		self.text("GAME SETTINGS", window.x + 38, window.y + 30, GOLD, self.title)
		for index, (key, label) in enumerate([("sound", "SOUND EFFECTS"), ("reduced_motion", "REDUCED MOTION"), ("show_tips", "SHOW TIPS")]):
			rect = pygame.Rect(window.x + 38, window.y + 110 + index * 80, 220, 40)
			pygame.draw.rect(self.screen, (18, 30, 52), rect, border_radius=10)
			self.text(label, rect.x + 14, rect.y + 10, TEXT, self.small)
			box = pygame.Rect(rect.x + 250, rect.y + 5, 30, 30)
			pygame.draw.rect(self.screen, CYAN if self.settings.get(key, True) else MUTED, box, border_radius=8)
			self.text("ON" if self.settings.get(key, True) else "OFF", box.x + 7, box.y + 8, BG if self.settings.get(key, True) else TEXT, self.small)
		close = pygame.Rect(window.x + 610, window.y + 330, 150, 54)
		pygame.draw.rect(self.screen, CYAN, close, border_radius=12)
		self.text("CLOSE", close.x + 48, close.y + 18, BG, self.small)

	def challenges(self) -> None:
		self.menu()
		overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
		overlay.fill((8, 13, 27, 170))
		self.screen.blit(overlay, (0, 0))
		window = pygame.Rect(200, 120, 880, 540)
		panel = pygame.Surface((window.w, window.h), pygame.SRCALPHA)
		pygame.draw.rect(panel, (17, 27, 48, 240), panel.get_rect(), border_radius=26)
		self.screen.blit(panel, window.topleft)
		self.text("DAILY CHALLENGES", window.x + 38, window.y + 32, GOLD, self.title)
		challenge = self.daily_challenge()
		self.text(challenge["title"], window.x + 38, window.y + 115, CYAN, self.font)
		self.text(challenge["description"], window.x + 38, window.y + 150, TEXT, self.small)
		progress = min(100, int((challenge["progress"] / max(1, challenge["goal"])) * 100))
		bar = pygame.Rect(window.x + 38, window.y + 180, 560, 18)
		pygame.draw.rect(self.screen, PANEL_LIGHT, bar, border_radius=8)
		pygame.draw.rect(self.screen, GOLD, (bar.x, bar.y, bar.w * progress / 100, bar.h), border_radius=8)
		self.text(f"{challenge['progress']} / {challenge['goal']}", window.x + 620, window.y + 176, TEXT, self.small)
		for i, (key, label) in enumerate([
			("first_win", "FIRST WIN"),
			("showdown", "3 WINS IN A DAY"),
			("coin_collector", "250 COINS"),
			("graph_guru", "5 BATTLES"),
			("ranked_up", "RANK 3"),
			("legend", "ALBERT EINSTEIN 5X"),
		]):
			rect = pygame.Rect(window.x + 38, window.y + 230 + i * 36, 520, 26)
			pygame.draw.rect(self.screen, (18, 30, 52), rect, border_radius=8)
			self.text(label, rect.x + 10, rect.y + 5, CYAN if self.achievements.get(key, False) else MUTED, self.small)
		close = pygame.Rect(window.x + 700, window.y + 460, 150, 54)
		pygame.draw.rect(self.screen, CYAN, close, border_radius=12)
		self.text("CLOSE", close.x + 48, close.y + 18, BG, self.small)

	def daily_challenge(self) -> dict:
		challenges = [
			{"title": "RALLY START", "id": "wins", "description": "Win 3 battles this week.", "goal": 3, "progress": min(self.total_wins, 3)},
			{"title": "MONEY MAZE", "id": "coins", "description": "Earn 250 total coins.", "goal": 250, "progress": min(self.coins, 250)},
			{"title": "BATTLE TEST", "id": "battles", "description": "Play 5 battles.", "goal": 5, "progress": min(self.total_battles, 5)},
			{"title": "GRAPH HACKER", "id": "graph", "description": "Reach 2,000 total wins across all profiles.", "goal": 2000, "progress": min(self.total_wins, 2000)},
		]
		selection = self.daily_challenge_index % len(challenges)
		challenge = challenges[selection]
		challenge["progress"] = min(challenge["progress"] + self.daily_challenge_progress, challenge["goal"])
		return challenge

	def unlock_achievement(self, key: str) -> None:
		if not self.achievements.get(key, False):
			self.achievements[key] = True
			self.save()

	def maybe_unlock_achievements(self, result: str) -> None:
		if result == "win":
			self.unlock_achievement("first_win")
			if self.total_wins >= 3:
				self.unlock_achievement("showdown")
			if self.coins >= 250:
				self.unlock_achievement("coin_collector")
			if self.total_battles >= 5:
				self.unlock_achievement("graph_guru")
			if self.current_rank()[0].upper().startswith("PRO") or "EINSTEIN" in self.current_rank()[0].upper():
				self.unlock_achievement("ranked_up")
			if "5X" in self.current_rank()[0].upper():
				self.unlock_achievement("legend")

	def toggle_setting(self, key: str) -> None:
		self.settings[key] = not self.settings.get(key, True)
		self.save()

	def user_search(self) -> None:
		self.menu()
		overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
		overlay.fill((8, 13, 27, 170))
		self.screen.blit(overlay, (0, 0))
		window = pygame.Rect(180, 110, 920, 560)
		shadow = pygame.Surface((window.w, window.h), pygame.SRCALPHA)
		pygame.draw.rect(shadow, (0, 0, 0, 120), shadow.get_rect(), border_radius=26)
		self.screen.blit(shadow, (window.x + 12, window.y + 14))
		panel = pygame.Surface((window.w, window.h), pygame.SRCALPHA)
		pygame.draw.rect(panel, (17, 27, 48, 240), panel.get_rect(), border_radius=26)
		pygame.draw.rect(panel, (25, 40, 68, 190), (14, 14, window.w - 28, window.h - 28), border_radius=22)
		self.screen.blit(panel, window.topleft)
		self.text("SEARCH USERS", window.x + 38, window.y + 30, GOLD, self.title)
		self.text("TYPE TO FILTER SHARED PLAYERS", window.x + 38, window.y + 90, MUTED, self.small)
		self.text(self.online_status, window.x + 480, window.y + 90, CYAN if self.online_status.startswith("ONLINE") else RED, self.small)
		search_box = pygame.Rect(window.x + 38, window.y + 118, 320, 42)
		pygame.draw.rect(self.screen, (26, 42, 68), search_box, border_radius=8)
		pygame.draw.rect(self.screen, CYAN if self.search_input_active else MUTED, search_box, 2, border_radius=8)
		self.text(self.search_query or "PLAYER NAME...", search_box.x + 14, search_box.y + 12, TEXT, self.font)
		close_button = pygame.Rect(window.x + 740, window.y + 440, 150, 54)
		pygame.draw.rect(self.screen, CYAN, close_button, border_radius=12)
		self.text("CLOSE", close_button.x + 52, close_button.y + 18, BG, self.small)
		visible_users = []
		profile_source = self.online_users if self.online_status.startswith("ONLINE") else self.users
		for user in profile_source:
			name = str(user.get("name", "PLAYER"))
			if self.search_query and self.search_query.lower() not in name.lower():
				continue
			visible_users.append(user)
		if not visible_users:
			self.text("NO PLAYERS FOUND", window.x + 38, window.y + 180, TEXT, self.font)
		else:
			for index, user in enumerate(visible_users[:8]):
				card = pygame.Rect(window.x + 38, window.y + 180 + index * 72, 840, 60)
				pygame.draw.rect(self.screen, (18, 30, 52), card, border_radius=12)
				pygame.draw.rect(self.screen, (255, 255, 255, 22), card, 1, border_radius=12)
				self.text(str(user.get("name", "PLAYER")), card.x + 18, card.y + 14, CYAN, self.font)
				user_tag = "OWNER" if str(user.get("name", "")) == self.owner_username else str(user.get("tag", "PLAYER")).upper()
				self.text(f"{user_tag}  //  {self.rank_label(int(user.get('wins', 0)))}", card.x + 18, card.y + 36, GOLD, self.small)
				self.text(f"COINS {int(user.get('coins', 0)):04d}", card.x + 480, card.y + 14, GOLD, self.small)
				self.text(f"DIAMONDS {int(user.get('diamonds', 0)):02d}", card.x + 480, card.y + 34, (168, 130, 255), self.small)
		self.text("CLICK THE BOX TO TYPE • PRESS ESC TO RETURN", window.x + 38, window.y + 510, MUTED, self.small)
		if self.owner_access():
			self.text("OWNER: click a user, then press 1 PLAYER  2 SUPPORTER  3 DEVELOPER  4 ADMIN", window.x + 38, window.y + 535, GOLD, self.small)

	def tutorial(self) -> None:
		self.menu()
		overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
		overlay.fill((8, 13, 27, 170))
		self.screen.blit(overlay, (0, 0))
		window = pygame.Rect(170, 110, 940, 540)
		shadow = pygame.Surface((window.w, window.h), pygame.SRCALPHA)
		pygame.draw.rect(shadow, (0, 0, 0, 120), shadow.get_rect(), border_radius=26)
		self.screen.blit(shadow, (window.x + 12, window.y + 14))
		panel = pygame.Surface((window.w, window.h), pygame.SRCALPHA)
		pygame.draw.rect(panel, (17, 27, 48, 240), panel.get_rect(), border_radius=26)
		pygame.draw.rect(panel, (25, 40, 68, 190), (14, 14, window.w - 28, window.h - 28), border_radius=22)
		self.screen.blit(panel, window.topleft)
		title = self.tutorial_pages[self.tutorial_page][0]
		self.text(title, window.x + 38, window.y + 30, GOLD, self.title)
		self.text(f"PAGE {self.tutorial_page + 1} / {len(self.tutorial_pages)}", window.x + 740, window.y + 44, MUTED, self.small)
		for index, line in enumerate(self.tutorial_pages[self.tutorial_page][1]):
			self.text(f"• {line}", window.x + 50, window.y + 120 + index * 52, TEXT, self.font)
		close_button = pygame.Rect(window.x + 720, window.y + 440, 150, 54)
		prev_button = pygame.Rect(window.x + 50, window.y + 440, 150, 54)
		next_button = pygame.Rect(window.x + 210, window.y + 440, 150, 54)
		for rect, label, active in [(prev_button, "PREV", self.tutorial_page > 0), (next_button, "NEXT", self.tutorial_page < len(self.tutorial_pages) - 1), (close_button, "CLOSE", True)]:
			mouse = pygame.mouse.get_pos()
			hover = rect.collidepoint(mouse)
			pygame.draw.rect(self.screen, CYAN if hover and active else PANEL_LIGHT, rect, border_radius=12)
			if not active:
				pygame.draw.rect(self.screen, (46, 67, 92), rect, 1, border_radius=12)
			self.text(label, rect.x + 44, rect.y + 18, BG if hover and active else TEXT, self.small)
		self.text("Use arrows, click buttons, or press ESC to leave this lesson.", window.x + 48, window.y + 510, MUTED, self.small)

	def load_save(self) -> tuple[int, int, bool, list[str], bool, str, int, str, list[dict], dict, dict, int, int, int, int, int, str]:
		try:
			data = json.loads(self.save_path.read_text(encoding="utf-8"))
			players = data.get("users")
			if isinstance(players, list):
				user_list = players
			else:
				user_list = [{
					"name": str(data.get("username", "PLAYER")),
					"coins": int(data.get("coins", 0)),
					"diamonds": int(data.get("diamonds", 3)),
					"wins": int(data.get("wins", 0)),
					"mustache": bool(data.get("mustache", False)),
					"unlocked_preset_names": list(data.get("unlocked_preset_names", [])),
					"custom_preset_unlocked": bool(data.get("custom_preset_unlocked", False)),
					"custom_preset_equation": str(data.get("custom_preset_equation", "x^2 - 2")),
				}]
			username = str(data.get("username", "PLAYER"))
			settings = data.get("settings") if isinstance(data.get("settings"), dict) else {
				"sound": True,
				"reduced_motion": False,
				"show_tips": True,
			}
			achievements = data.get("achievements") if isinstance(data.get("achievements"), dict) else {
				"first_win": False,
				"showdown": False,
				"coin_collector": False,
				"graph_guru": False,
				"ranked_up": False,
				"legend": False,
			}
			return (
				int(data.get("coins", 0)),
				int(data.get("diamonds", 3)),
				bool(data.get("mustache", False)),
				list(data.get("unlocked_preset_names", [])),
				bool(data.get("custom_preset_unlocked", False)),
				str(data.get("custom_preset_equation", "x^2 - 2")),
				int(data.get("wins", 0)),
				username,
				user_list,
				settings,
				achievements,
				int(data.get("best_combo", 0)),
				int(data.get("total_battles", 0)),
				int(data.get("best_streak", 0)),
				int(data.get("daily_challenge_index", 0)),
				int(data.get("daily_challenge_progress", 0)),
				str(data.get("daily_challenge_date", "")),
			)
		except (OSError, ValueError, TypeError, json.JSONDecodeError):
			return 0, 3, False, [], False, "x^2 - 2", 0, "PLAYER", [{
				"name": "PLAYER",
				"coins": 0,
				"diamonds": 3,
				"wins": 0,
				"mustache": False,
				"unlocked_preset_names": [],
				"custom_preset_unlocked": False,
				"custom_preset_equation": "x^2 - 2",
			}], {
				"sound": True,
				"reduced_motion": False,
				"show_tips": True,
			}, {
				"first_win": False,
				"showdown": False,
				"coin_collector": False,
				"graph_guru": False,
				"ranked_up": False,
				"legend": False,
			}, 0, 0, 0, 0, 0, ""

	def save(self) -> None:
		try:
			current_user = {
				"name": self.username,
				"tag": self.user_tag,
				"coins": self.coins,
				"diamonds": self.diamonds,
				"wins": self.total_wins,
				"mustache": self.mustache,
				"unlocked_preset_names": self.unlocked_preset_names,
				"custom_preset_unlocked": self.custom_preset_unlocked,
				"custom_preset_equation": self.custom_preset_equation,
			}
			if self.owner_access():
				self.owner_username = self.username
			old_name = getattr(self, "saved_username", self.username)
			current_index = next(
				(index for index, entry in enumerate(self.users)
				 if isinstance(entry, dict) and entry.get("name") in {old_name, self.username}),
				None,
			)
			if current_index is None:
				self.users.insert(0, current_user)
			else:
				self.users[current_index] = current_user
				self.users[:] = [
					entry for index, entry in enumerate(self.users)
					if index == current_index or not isinstance(entry, dict) or entry.get("name") != self.username
				]
			self.saved_username = self.username
			self.save_path.write_text(json.dumps({
				"owner_username": self.owner_username,
				"username": self.username,
				"coins": self.coins,
				"diamonds": self.diamonds,
				"mustache": self.mustache,
				"unlocked_preset_names": self.unlocked_preset_names,
				"custom_preset_unlocked": self.custom_preset_unlocked,
				"custom_preset_equation": self.custom_preset_equation,
				"wins": self.total_wins,
				"users": self.users,
				"settings": self.settings,
				"achievements": self.achievements,
				"best_combo": self.best_combo,
				"total_battles": self.total_battles,
				"best_streak": self.best_streak,
				"daily_challenge_index": self.daily_challenge_index,
				"daily_challenge_progress": self.daily_challenge_progress,
				"daily_challenge_date": self.daily_challenge_date,
			}), encoding="utf-8")
		except OSError:
			pass

	def load_mustache_orb(self) -> pygame.Surface | None:
		try:
			image = pygame.image.load(Path(__file__).with_name("mustache_orb.png")).convert_alpha()
			image.set_colorkey((0, 0, 0))
			return image
		except (pygame.error, OSError):
			return None

	def draw_mustache_orb(self, center: tuple[int, int], diameter: int) -> None:
		if self.mustache_orb is None:
			pygame.draw.circle(self.screen, ORB_GREEN, center, diameter // 2)
			self.draw_mustache(center)
			return
		image = pygame.transform.smoothscale(self.mustache_orb, (diameter, diameter))
		self.screen.blit(image, image.get_rect(center=center))

	def shop(self) -> None:
		self.screen.fill(BG)
		self.text("ORB LAB", 70, 70, CYAN, self.title)
		self.text("MAKE YOUR FIGHTER YOURS", 74, 140, GOLD, self.font)
		self.text(f"COINS {self.coins:04d}     DIAMONDS {self.diamonds:02d}", 74, 205, TEXT, self.font)
		item = pygame.Rect(74, 260, 430, 170)
		pygame.draw.rect(self.screen, PANEL_LIGHT, item, border_radius=4)
		self.text("THE PROFESSOR", 100, 290, TEXT, self.font)
		self.text("A magnificent mustache for your orb.", 100, 328, MUTED, self.small)
		self.text("OWNED" if self.mustache else "50 COINS  /  1 DIAMOND", 100, 372, CYAN if self.mustache else GOLD, self.font)
		self.text("MUSTACHE EQUIPPED" if self.mustache else "Click item to purchase", 100, 402, MUTED, self.small)
		if self.mustache:
			self.draw_mustache_orb((710, 345), 110)
		else:
			pygame.draw.circle(self.screen, ORB_GREEN, (710, 345), 48)
		back = pygame.Rect(74, 510, 220, 48)
		pygame.draw.rect(self.screen, PANEL_LIGHT, back, border_radius=3)
		self.text("BACK TO MENU", 112, 525, TEXT, self.small)
		self.text(self.shop_status, 74, 610, TEXT, self.small)

	def weapon_shop(self) -> None:
		self.screen.fill(BG)
		self.text("WEAPON SHOP", 70, 70, CYAN, self.title)
		self.text("BUY NEW CURVES FOR YOUR ARSENAL", 74, 140, GOLD, self.font)
		self.text(f"COINS {self.coins:04d}     DIAMONDS {self.diamonds:02d}", 74, 205, TEXT, self.font)
		self.text(self.weapon_shop_status, 74, 240, TEXT, self.small)
		for index, (name, equation, _, cost, diamond_cost) in enumerate(SHOP_PRESETS):
			rect = pygame.Rect(74, 280 + index * 110, 1132, 92)
			owned = name == "CUSTOM PRESET" and self.custom_preset_unlocked or name in self.unlocked_preset_names
			pygame.draw.rect(self.screen, (18, 30, 52) if not owned else (16, 84, 72), rect, border_radius=12)
			pygame.draw.rect(self.screen, (255, 255, 255, 30), rect, 1, border_radius=12)
			self.text(name, rect.x + 30, rect.y + 22, TEXT, self.font)
			self.text(equation, rect.x + 30, rect.y + 54, CYAN, self.small)
			price = f"{cost} COINS" if diamond_cost == 0 else f"{cost} COINS / {diamond_cost} DIAMONDS"
			self.text("OWNED" if owned else price, rect.x + 920, rect.y + 22, GOLD if not owned else CYAN, self.font)
			self.text("READY" if owned else "BUY", rect.x + 980, rect.y + 54, TEXT, self.small)
		back = pygame.Rect(74, 690, 220, 48)
		pygame.draw.rect(self.screen, PANEL_LIGHT, back, border_radius=3)
		self.text("BACK TO MENU", 112, 704, TEXT, self.small)

	def result_screen(self) -> None:
		self.screen.fill(BG)
		win = self.result == "win"
		color = CYAN if win else RED
		self.text("VICTORY" if win else "DEFEATED", 74, 84, color, self.title)
		self.text("THE GRAPH DECIDES. YOU ANSWERED.", 78, 150, GOLD, self.font)
		if self.mustache:
			self.draw_mustache_orb((190, 315), 140)
		else:
			pygame.draw.circle(self.screen, self.player.color, (190, 315), 62)
		self.text("YOU", 164, 395, color, self.font)
		self.text("+100 COINS" if win else "+20 COINS", 410, 275, GOLD, self.font)
		self.text("+1 DIAMOND" if win else "NO DIAMOND", 410, 320, (168, 130, 255) if win else MUTED, self.font)
		self.text(f"TOTAL  {self.coins:04d} COINS   {self.diamonds:02d} DIAMONDS", 410, 380, TEXT, self.small)
		buttons = [(pygame.Rect(74, 470, 190, 52), "REMATCH"), (pygame.Rect(280, 470, 190, 52), "MAIN MENU"), (pygame.Rect(486, 470, 190, 52), "ORB LAB")]
		for rect, label in buttons:
			pygame.draw.rect(self.screen, GOLD if label == "REMATCH" else PANEL_LIGHT, rect, border_radius=3)
			self.text(label, rect.x + 48, rect.y + 17, BG if label == "REMATCH" else TEXT, self.small)
		self.text("R = rematch     M = menu     C = Orb Lab", 78, 560, MUTED, self.font)

	def draw_mustache(self, center: tuple[int, int]) -> None:
		x, y = center
		pygame.draw.ellipse(self.screen, BG, (x - 22, y + 4, x, y + 17))
		pygame.draw.ellipse(self.screen, BG, (x, y + 4, x + 22, y + 17))

	def current_rank(self) -> tuple[str, int, str | None, int]:
		wins = max(0, self.total_wins)
		if wins == 0:
			current_label = "0 YEAR OLD"
			current_threshold = 0
			next_label = "0 YEAR OLD 1 STAR"
			return current_label, current_threshold, next_label, wins

		star_index = min((wins - 1) // 3, len(RANKS) - 1)
		star_number = (wins - 1) % 3 + 1
		current_label = f"{RANKS[star_index]} {star_number} STAR" if star_number == 1 else f"{RANKS[star_index]} {star_number} STARS"
		current_threshold = wins

		next_wins = wins + 1
		if next_wins > 3 * len(RANKS):
			next_label = None
		else:
			next_star_index = min((next_wins - 1) // 3, len(RANKS) - 1)
			next_star_number = (next_wins - 1) % 3 + 1
			next_label = f"{RANKS[next_star_index]} {next_star_number} STAR" if next_star_number == 1 else f"{RANKS[next_star_index]} {next_star_number} STARS"
		return current_label, current_threshold, next_label, wins

	def rank_label(self, wins: int) -> str:
		wins = max(0, wins)
		if wins == 0:
			return "0 YEAR OLD"
		star_index = min((wins - 1) // 3, len(RANKS) - 1)
		star_number = (wins - 1) % 3 + 1
		if star_number == 1:
			return f"{RANKS[star_index]} 1 STAR"
		return f"{RANKS[star_index]} {star_number} STARS"

	def finish_battle(self, result: str) -> None:
		if self.reward_paid:
			return
		self.result = result
		self.reward_paid = True
		self.coins += 100 if result == "win" else 20
		if result == "win":
			self.diamonds += 1
			self.total_wins += 1
		self.save()
		self.mode = "result"

	def start(self, mode: str) -> None:
		self.mode = mode
		self.last_mode = mode
		self.reward_paid = False
		self.selected = 0
		self.input_text = "x^2 - 3"
		self.input_active = mode == "hard"
		self.round_number = 1
		self.status = "Choose a graph weapon, then FIRE."
		self.player = Fighter("YOU", ORB_GREEN, -6.5, -3.7)
		self.cpu = Fighter("CPU", RED, 6.5, 3.7)
		self.cpu_turn_number = 0
		self.player_curve = []
		self.cpu_curve = []
		self.refresh_preview()

	def refresh_preview(self) -> None:
		try:
			if self.mode == "preset":
				presets = self.available_presets
				if self.selected >= len(presets):
					self.selected = 0
				function = presets[self.selected][2]
			else:
				function = self.parse_equation(self.input_text)
			self.player_curve = self.anchor_curve(self.sample(function), self.player, function)
		except (SyntaxError, ValueError, NameError, TypeError):
			self.player_curve = []

	def to_screen(self, x: float, y: float) -> tuple[int, int]:
		px = GRAPH.left + int((x - X_MIN) / (X_MAX - X_MIN) * GRAPH.width)
		py = GRAPH.top + int((Y_MAX - y) / (Y_MAX - Y_MIN) * GRAPH.height)
		return px, py

	def draw_graph(self) -> None:
		pygame.draw.rect(self.screen, (13, 23, 41), GRAPH)
		for x in range(-10, 11):
			px, _ = self.to_screen(x, 0)
			pygame.draw.line(self.screen, (24, 41, 67), (px, GRAPH.top), (px, GRAPH.bottom))
			self.text(str(x), px - 5, GRAPH.bottom + 8, MUTED, self.small)
		for y in range(math.ceil(Y_MIN), math.floor(Y_MAX) + 1):
			_, py = self.to_screen(0, y)
			pygame.draw.line(self.screen, (24, 41, 67), (GRAPH.left, py), (GRAPH.right, py))
			self.text(str(y), GRAPH.left - 24, py - 8, MUTED, self.small)
		zero_x, zero_y = self.to_screen(0, 0)
		pygame.draw.line(self.screen, (75, 95, 125), (GRAPH.left, zero_y), (GRAPH.right, zero_y), 2)
		pygame.draw.line(self.screen, (75, 95, 125), (zero_x, GRAPH.top), (zero_x, GRAPH.bottom), 2)
		self.draw_curve(self.player_curve, CYAN)
		self.draw_curve(self.cpu_curve, RED)
		self.draw_fighter(self.player)
		self.draw_fighter(self.cpu)

	def draw_curve(self, curve: list[tuple[float, float]], color: tuple[int, int, int]) -> None:
		if len(curve) > 1:
			pygame.draw.lines(self.screen, color, False, [self.to_screen(x, y) for x, y in curve], 4)

	def draw_fighter(self, fighter: Fighter) -> None:
		px, py = self.to_screen(fighter.x, fighter.y)
		pygame.draw.circle(self.screen, fighter.color, (px, py), 17)
		pygame.draw.circle(self.screen, TEXT, (px, py), 17, 2)
		if fighter is self.player and self.mustache:
			self.draw_mustache_orb((px, py), 42)
		label = self.font.render(fighter.name, True, fighter.color)
		self.screen.blit(label, label.get_rect(center=(px, py - 34)))

	def game(self) -> None:
		self.screen.fill(BG)
		pygame.draw.rect(self.screen, PANEL, (0, 0, self.screen.get_width(), 92))
		self.text("MATH FIGHT", 24, 28, CYAN, self.font)
		self.text(f"ROUND {self.round_number} / 3", 220, 31, GOLD, self.small)
		rank_name, _, _, _ = self.current_rank()
		self.text(f"RANK {rank_name}", self.screen.get_width() - 560, 31, CYAN, self.small)
		self.text(f"YOU {self.player.hp:03d} HP     CPU {self.cpu.hp:03d} HP", self.screen.get_width() - 280, 31, TEXT, self.small)
		self.text(f"{self.coins}c  {self.diamonds}d", self.screen.get_width() - 410, 31, GOLD, self.small)
		menu_button = pygame.Rect(self.screen.get_width() - 140, 20, 120, 38)
		pygame.draw.rect(self.screen, PANEL_LIGHT, menu_button, border_radius=3)
		self.text("MAIN MENU", menu_button.x + 20, 31, TEXT, self.small)
		pygame.draw.rect(self.screen, PANEL, (0, 92, 285, self.screen.get_height() - 92))
		heading = "PRESET ARSENAL // PREVIEW" if self.mode == "preset" else "HARD MODE // PREVIEW ON"
		self.text(heading, 22, 122, GOLD, self.small)
		if self.mode == "preset":
			presets = self.available_presets
			for index, rect in self.preset_buttons():
				name, equation, _ = presets[index]
				pygame.draw.rect(self.screen, (14, 116, 144) if index == self.selected else (18, 30, 52), rect, border_radius=8)
				pygame.draw.rect(self.screen, (255, 255, 255, 24), rect, 1, border_radius=8)
				self.text(name, rect.x + 12, rect.y + 9, TEXT, self.small)
				self.text(equation, rect.x + 12, rect.y + 26, CYAN, self.small)
			preview_y = self.preset_preview_y()
			self.text(f"PREVIEW // {presets[self.selected][1]}", 20, preview_y, CYAN, self.small)
		else:
			entry = pygame.Rect(18, 168, 249, 46)
			pygame.draw.rect(self.screen, (26, 42, 68), entry, border_radius=3)
			pygame.draw.rect(self.screen, CYAN if self.input_active else MUTED, entry, 2, border_radius=3)
			self.text(self.input_text, 28, 180, TEXT, self.font)
			self.text("Allowed: y=, x, + - * / ^, sin(x), cos(x)", 20, 230, MUTED, self.small)
			self.text("Example: y = 0.0828x^2 + 10", 20, 252, MUTED, self.small)
			self.text(f"PREVIEW // {self.input_text}", 20, 330, CYAN, self.small)
		fire = pygame.Rect(18, 495, 249, 52)
		pygame.draw.rect(self.screen, GOLD, fire, border_radius=3)
		fire_text = self.font.render("FIRE GRAPH  [ENTER]", True, BG)
		self.screen.blit(fire_text, fire_text.get_rect(center=fire.center))
		move = pygame.Rect(18, 560, 249, 42)
		pygame.draw.rect(self.screen, (45, 85, 100), move, border_radius=3)
		self.text("MOVE / SKIP GRAPH  [WASD]", 40, 572, TEXT, self.small)
		reset = pygame.Rect(18, 612, 249, 42)
		pygame.draw.rect(self.screen, PANEL_LIGHT, reset, border_radius=3)
		self.text("RESET BATTLE", 80, 624, TEXT, self.small)
		self.text(self.status, 20, 680, TEXT, self.small)
		self.text("GRAPH RULES", 20, self.screen.get_height() - 62, GOLD, self.small)
		self.text("Crossing an enemy = 25 damage", 20, self.screen.get_height() - 40, MUTED, self.small)
		self.draw_graph()

	def sample(self, function) -> list[tuple[float, float]]:
		x_values = np.linspace(X_MIN, X_MAX, 161, dtype=np.float64)
		try:
			y_values = np.asarray(function(x_values), dtype=np.float64)
		except (ArithmeticError, ValueError, OverflowError, TypeError):
			return []
		if y_values.ndim == 0:
			y_values = np.full_like(x_values, float(y_values))
		valid = np.isfinite(y_values) & (np.abs(y_values) <= 1000)
		return [(float(x), float(y)) for x, y in zip(x_values[valid], y_values[valid])]

	def anchor_curve(self, curve: list[tuple[float, float]], fighter: Fighter, function) -> list[tuple[float, float]]:
		"""Launch the actual equation from the fighter's current x-position."""
		anchored = [(x + fighter.x, y + fighter.y) for x, y in curve]
		return [(x, y) for x, y in anchored if X_MIN - 1 <= x <= X_MAX + 1 and Y_MIN - 1 <= y <= Y_MAX + 1]

	def parse_equation(self, text: str):
		expression = text.strip().lower().replace("^", "**").replace(" ", "")
		if expression.startswith("y="):
			expression = expression[2:]
		expression = re.sub(r"(?<=[0-9.)])(?=x|sin|cos|tan)", "*", expression)
		expression = re.sub(r"(?<=[0-9x)])(?=\()", "*", expression)
		if not expression or len(expression) > 60:
			raise ValueError
		allowed = {"x", "sin", "cos", "tan", "pi"}
		code = compile(expression, "equation", "eval")
		if any(name not in allowed for name in code.co_names):
			raise ValueError
		return lambda x: eval(code, {"__builtins__": {}}, {"x": x, "sin": np.sin, "cos": np.cos, "tan": np.tan, "pi": np.pi})

	def fire(self) -> None:
		try:
			if self.mode == "preset":
				presets = self.available_presets
				if self.selected >= len(presets):
					self.selected = 0
				equation, function = presets[self.selected][1:3]
			else:
				equation = self.input_text
				function = self.parse_equation(equation)
			curve = self.sample(function)
			if len(curve) < 2:
				raise ValueError
		except (SyntaxError, ValueError, NameError, TypeError):
			self.status = "INVALID GRAPH: try y = 0.0828x^2 + 10."
			return
		self.player_curve = self.anchor_curve(curve, self.player, function)
		self.move_cpu_toward_player()
		self.cpu_turn_number += 1
		self.cpu_equation, cpu_function = self.choose_cpu_attack()
		self.cpu_curve = self.anchor_curve(self.sample(cpu_function), self.cpu, cpu_function)
		player_hit = self.hits(self.player_curve, self.cpu)
		cpu_hit = self.cpu_turn_number % CPU_FIRE_INTERVAL == 0 and self.cpu_hits(self.cpu_curve, self.player)
		if player_hit:
			self.cpu.hp = max(0, self.cpu.hp - 25)
		if cpu_hit:
			self.player.hp = max(0, self.player.hp - CPU_DAMAGE)
		self.status = f"{equation}  {'HIT' if player_hit else 'MISS'}  //  CPU {self.cpu_equation} {'HIT' if cpu_hit else 'MISS'}"
		if self.player.hp == 0 or self.cpu.hp == 0:
			self.finish_battle("win" if self.cpu.hp == 0 else "loss")
			return
		self.round_number = self.round_number + 1 if self.round_number < 3 else 1

	def move(self, dx: float, dy: float) -> None:
		if self.player.hp <= 0 or self.cpu.hp <= 0:
			return
		self.player.x = max(X_MIN + 0.5, min(X_MAX - 0.5, self.player.x + dx))
		self.player.y = max(Y_MIN + 0.5, min(Y_MAX - 0.5, self.player.y + dy))
		self.move_cpu_toward_player()
		self.cpu_turn_number += 1
		self.cpu_equation, cpu_function = self.choose_cpu_attack()
		self.cpu_curve = self.anchor_curve(self.sample(cpu_function), self.cpu, cpu_function)
		cpu_hit = self.cpu_turn_number % CPU_FIRE_INTERVAL == 0 and self.cpu_hits(self.cpu_curve, self.player)
		if cpu_hit:
			self.player.hp = max(0, self.player.hp - CPU_DAMAGE)
		self.status = f"You moved. CPU chose {self.cpu_equation} ({'HIT' if cpu_hit else 'MISS'})."
		if self.player.hp == 0:
			self.finish_battle("loss")
		else:
			self.round_number = self.round_number + 1 if self.round_number < 3 else 1
		self.refresh_preview()

	def choose_cpu_attack(self):
		"""Pick the preset whose local curve best matches the player's relative position."""
		delta_x = self.player.x - self.cpu.x
		delta_y = self.player.y - self.cpu.y
		candidates = []
		for index, (name, equation, function) in enumerate(self.available_presets):
			try:
				miss_distance = abs(float(function(delta_x)) - delta_y)
			except (ArithmeticError, ValueError, OverflowError):
				miss_distance = float("inf")
			candidates.append((miss_distance, index, name, equation, function))
		_, _, name, equation, function = min(candidates, key=lambda item: (item[0], item[1]))
		return f"{name}: {equation}", function

	def move_cpu_toward_player(self) -> None:
		dx = self.player.x - self.cpu.x
		dy = self.player.y - self.cpu.y
		if abs(dx) + abs(dy) == 0:
			return
		step = CPU_MOVE_STEP / max(abs(dx), abs(dy))
		self.cpu.x = max(X_MIN + 0.5, min(X_MAX - 0.5, self.cpu.x + dx * step))
		self.cpu.y = max(Y_MIN + 0.5, min(Y_MAX - 0.5, self.cpu.y + dy * step))

	def cpu_hits(self, curve: list[tuple[float, float]], fighter: Fighter) -> bool:
		return any(abs(x - fighter.x) < 0.35 and abs(y - fighter.y) < 0.45 for x, y in curve)

	def buy_mustache(self) -> None:
		if self.mustache:
			self.shop_status = "The Professor is already equipped."
		elif self.coins >= 50:
			self.coins -= 50
			self.mustache = True
			self.shop_status = "Purchased with coins and equipped. Magnificent."
			self.save()
		elif self.diamonds >= 1:
			self.diamonds -= 1
			self.mustache = True
			self.shop_status = "Purchased with a diamond and equipped. Magnificent."
			self.save()
		else:
			self.shop_status = "You need 50 coins or 1 diamond."

	def hits(self, curve: list[tuple[float, float]], fighter: Fighter) -> bool:
		return any(abs(x - fighter.x) < 0.55 and abs(y - fighter.y) < 0.7 for x, y in curve)

	def buy_weapon(self, offer_index: int) -> None:
		name, equation, function, cost, diamond_cost = SHOP_PRESETS[offer_index]
		if name == "CUSTOM PRESET":
			if self.custom_preset_unlocked:
				self.weapon_shop_status = "Custom preset already unlocked."
				return
			if self.coins >= cost and self.diamonds >= diamond_cost:
				self.coins -= cost
				self.diamonds -= diamond_cost
				self.custom_preset_unlocked = True
				self.weapon_shop_status = "Custom preset unlocked. It is now available in the preset list."
				self.save()
			else:
				self.weapon_shop_status = "You need 1000 coins and 50 diamonds to unlock a custom preset."
			return
		if name in self.unlocked_preset_names:
			self.weapon_shop_status = f"{name} is already in your arsenal."
			return
		if self.coins >= cost and self.diamonds >= diamond_cost:
			self.coins -= cost
			self.diamonds -= diamond_cost
			self.unlocked_preset_names.append(name)
			self.weapon_shop_status = f"{name} unlocked. It is ready to use in the preset arsenal."
			self.save()
		else:
			self.weapon_shop_status = f"You need {cost} coins and {diamond_cost} diamonds for {name}."

	def click(self, position: tuple[int, int]) -> None:
		x, y = position
		if self.mode == "menu":
			if pygame.Rect(74, 300, 340, 148).collidepoint(x, y):
				self.start("preset")
			elif pygame.Rect(470, 300, 340, 148).collidepoint(x, y):
				self.start("hard")
			elif pygame.Rect(866, 300, 340, 148).collidepoint(x, y):
				self.mode = "shop"
			elif pygame.Rect(866, 494, 340, 54).collidepoint(x, y):
				self.mode = "weapon_shop"
			elif pygame.Rect(72, 494, 220, 54).collidepoint(x, y):
				self.tutorial_page = 0
				self.mode = "tutorial"
			elif pygame.Rect(320, 494, 220, 54).collidepoint(x, y):
				self.mode = "challenges"
			elif pygame.Rect(320, 560, 220, 54).collidepoint(x, y):
				self.mode = "leaderboard"
			elif pygame.Rect(560, 494, 220, 54).collidepoint(x, y):
				self.mode = "settings"
			elif pygame.Rect(560, 560, 220, 54).collidepoint(x, y):
				self.mode = "profile"
			elif pygame.Rect(866, 560, 340, 54).collidepoint(x, y):
				self.mode = "level_editor"
			elif pygame.Rect(72, 560, 220, 54).collidepoint(x, y):
				self.search_query = ""
				self.search_input_active = True
				self.sync_online_profile()
				self.refresh_online_users()
				self.mode = "user_search"
		elif self.mode == "level_editor":
			canvas = pygame.Rect(330, 140, 880, 500)
			if canvas.collidepoint(x, y):
				normalized = ((x - canvas.left) / canvas.width, (y - canvas.top) / canvas.height)
				nearby = next((point for point in self.level_points if abs(point[0] - normalized[0]) < 0.035 and abs(point[1] - normalized[1]) < 0.035), None)
				if nearby is None:
					self.level_points.append(normalized)
					self.level_status = "Target added."
				else:
					self.level_points.remove(nearby)
					self.level_status = "Target removed."
			elif pygame.Rect(54, 194, 230, 42).collidepoint(x, y):
				self.level_input_active = True
			elif pygame.Rect(54, 450, 230, 46).collidepoint(x, y):
				self.save_level()
			elif pygame.Rect(54, 510, 230, 46).collidepoint(x, y):
				self.load_level()
		elif self.mode == "admin_panel":
			if self.owner_access():
				for index, user in enumerate(self.users[:8]):
					row = pygame.Rect(54 + 24, 150 + 70 + index * 48, 650, 38)
					if row.collidepoint(x, y):
						self.admin_selected_name = str(user.get("name", ""))
						break
				for index, tag in enumerate(TAGS[:-1]):
					if pygame.Rect(790, 270 + index * 54, 270, 42).collidepoint(x, y) and self.admin_selected_name:
						self.assign_tag(self.admin_selected_name, tag)
						break
		elif self.mode == "name_edit":
			name_box = pygame.Rect(298, 298, 420, 44)
			if name_box.collidepoint(x, y):
				self.name_edit_active = True
			elif pygame.Rect(298, 360, 150, 48).collidepoint(x, y):
				self.name_edit_active = False
				self.mode = "menu"
			elif pygame.Rect(480, 360, 150, 48).collidepoint(x, y):
				self.username = self.name_edit_text.strip()[:16] or "PLAYER"
				self.name_edit_active = False
				self.save()
				self.mode = "menu"
		elif self.mode == "tutorial":
			if pygame.Rect(170 + 720, 110 + 440, 150, 54).collidepoint(x, y):
				self.mode = "menu"
			elif pygame.Rect(170 + 50, 110 + 440, 150, 54).collidepoint(x, y) and self.tutorial_page > 0:
				self.tutorial_page -= 1
			elif pygame.Rect(170 + 210, 110 + 440, 150, 54).collidepoint(x, y) and self.tutorial_page < len(self.tutorial_pages) - 1:
				self.tutorial_page += 1
			elif pygame.Rect(170 + 210, 110 + 440, 150, 54).collidepoint(x, y):
				self.mode = "menu"
		elif self.mode == "user_search":
			search_box = pygame.Rect(180 + 38, 110 + 118, 320, 42)
			if search_box.collidepoint(x, y):
				self.search_input_active = True
			elif pygame.Rect(180 + 740, 110 + 440, 150, 54).collidepoint(x, y):
				self.mode = "menu"
				self.search_input_active = False
			elif self.owner_access():
				for index, user in enumerate(self.users[:8]):
					row = pygame.Rect(180 + 38, 110 + 180 + index * 72, 840, 60)
					if row.collidepoint(x, y):
						self.tag_target_name = str(user.get("name", ""))
						break
		elif self.mode in {"leaderboard", "profile", "settings", "challenges"}:
			if self.mode == "profile" and pygame.Rect(210 + 500, 130 + 82, 180, 42).collidepoint(x, y):
				self.name_edit_text = self.username
				self.name_edit_active = True
				self.mode = "name_edit"
			elif self.mode == "profile" and self.owner_access() and pygame.Rect(210 + 500, 130 + 140, 180, 42).collidepoint(x, y):
				self.mode = "admin_panel"
			elif pygame.Rect(180 + 720, 115 + 470, 150, 54).collidepoint(x, y):
				self.mode = "menu"
			if self.mode == "settings":
				for index, (key, label) in enumerate([("sound", "SOUND EFFECTS"), ("reduced_motion", "REDUCED MOTION"), ("show_tips", "SHOW TIPS")]):
					box = pygame.Rect(250 + 38 + 250, 160 + 110 + index * 80 + 5, 30, 30)
					if box.collidepoint(x, y):
						self.toggle_setting(key)
						break
		elif self.mode == "shop":
			if pygame.Rect(74, 260, 430, 170).collidepoint(x, y):
				self.buy_mustache()
			elif pygame.Rect(74, 510, 220, 48).collidepoint(x, y):
				self.mode = "menu"
		elif self.mode == "weapon_shop":
			if pygame.Rect(74, 690, 220, 48).collidepoint(x, y):
				self.mode = "menu"
			for index, _ in enumerate(SHOP_PRESETS):
				rect = pygame.Rect(74, 280 + index * 110, 1132, 92)
				if rect.collidepoint(x, y):
					self.buy_weapon(index)
					break
		elif self.mode == "result":
			if pygame.Rect(74, 470, 190, 52).collidepoint(x, y):
				self.start(self.last_mode)
			elif pygame.Rect(280, 470, 190, 52).collidepoint(x, y):
				self.mode = "menu"
			elif pygame.Rect(486, 470, 190, 52).collidepoint(x, y):
				self.mode = "shop"
			return
		if self.mode == "preset":
			for index, rect in self.preset_buttons():
				if rect.collidepoint(x, y):
					self.selected = index
					self.refresh_preview()
					break
		elif self.mode == "hard" and pygame.Rect(18, 168, 249, 46).collidepoint(x, y):
			self.input_active = True
		elif pygame.Rect(18, 495, 249, 52).collidepoint(x, y):
			self.fire()
		elif pygame.Rect(18, 560, 249, 42).collidepoint(x, y):
			self.move(0.8, 0)
		elif pygame.Rect(18, 612, 249, 42).collidepoint(x, y):
			self.start(self.mode)
		elif pygame.Rect(self.screen.get_width() - 140, 20, 120, 38).collidepoint(x, y):
			self.mode = "menu"

	def run(self) -> None:
		running = True
		while running:
			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					running = False
				elif event.type == pygame.VIDEORESIZE:
					self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
				elif event.type == pygame.MOUSEBUTTONDOWN:
					self.click(event.pos)
				elif event.type == pygame.KEYDOWN:
					if event.key == pygame.K_ESCAPE:
						if self.mode == "menu":
							running = False
						elif self.mode == "tutorial":
							self.mode = "menu"
						else:
							self.mode = "menu"
					elif self.mode == "tutorial":
						if event.key in (pygame.K_RIGHT, pygame.K_d):
							self.tutorial_page = min(len(self.tutorial_pages) - 1, self.tutorial_page + 1)
						elif event.key in (pygame.K_LEFT, pygame.K_a):
							self.tutorial_page = max(0, self.tutorial_page - 1)
						elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
							if self.tutorial_page < len(self.tutorial_pages) - 1:
								self.tutorial_page += 1
							else:
								self.mode = "menu"
					elif self.mode == "user_search":
						if event.key == pygame.K_BACKSPACE:
							self.search_query = self.search_query[:-1]
						elif event.key == pygame.K_RETURN:
							self.search_input_active = False
						elif self.owner_access() and self.tag_target_name and pygame.K_1 <= event.key <= pygame.K_4:
							self.assign_tag(self.tag_target_name, TAGS[event.key - pygame.K_1])
						elif self.search_input_active and event.unicode and len(self.search_query) < 18:
							self.search_query += event.unicode
					elif self.mode == "level_editor":
						if event.key == pygame.K_BACKSPACE and self.level_input_active:
							self.level_name = self.level_name[:-1]
						elif self.level_input_active and event.unicode and event.unicode.isprintable() and len(self.level_name) < 32:
							self.level_name += event.unicode
					elif self.mode == "name_edit":
						if event.key == pygame.K_ESCAPE:
							self.name_edit_active = False
							self.mode = "menu"
						elif event.key == pygame.K_RETURN:
							self.username = self.name_edit_text.strip()[:16] or "PLAYER"
							self.name_edit_active = False
							self.save()
							self.mode = "menu"
						elif event.key == pygame.K_BACKSPACE:
							self.name_edit_text = self.name_edit_text[:-1]
						elif self.name_edit_active and event.unicode and event.unicode.isprintable() and len(self.name_edit_text) < 16:
							self.name_edit_text += event.unicode
					elif self.mode == "shop" and event.key == pygame.K_m:
						self.mode = "menu"
					elif self.mode == "result" and event.key == pygame.K_r:
						self.start(self.last_mode)
					elif self.mode == "result" and event.key == pygame.K_c:
						self.mode = "shop"
					elif self.mode == "result" and event.key == pygame.K_m:
						self.mode = "menu"
					elif self.mode != "menu" and event.key == pygame.K_RETURN:
						self.fire()
					elif self.mode != "menu" and event.key == pygame.K_r:
						self.start(self.mode)
					elif self.mode == "preset" and pygame.K_1 <= event.key <= pygame.K_6:
						self.selected = event.key - pygame.K_1
						self.refresh_preview()
					elif self.mode != "menu" and event.key in (pygame.K_w, pygame.K_UP):
						self.move(0, 0.8)
					elif self.mode != "menu" and event.key in (pygame.K_s, pygame.K_DOWN):
						self.move(0, -0.8)
					elif self.mode != "menu" and event.key in (pygame.K_a, pygame.K_LEFT):
						self.move(-0.8, 0)
					elif self.mode != "menu" and event.key in (pygame.K_d, pygame.K_RIGHT):
						self.move(0.8, 0)
					elif self.mode == "hard" and self.input_active:
						if event.key == pygame.K_BACKSPACE:
							self.input_text = self.input_text[:-1]
						elif event.key == pygame.K_SPACE:
							self.input_text += " "
						elif event.unicode and len(self.input_text) < 60:
							self.input_text += event.unicode
						self.refresh_preview()
			self.preview_phase += 0.06
			if self.mode == "menu":
				self.menu()
			elif self.mode == "shop":
				self.shop()
			elif self.mode == "weapon_shop":
				self.weapon_shop()
			elif self.mode == "result":
				self.result_screen()
			elif self.mode == "tutorial":
				self.tutorial()
			elif self.mode == "user_search":
				self.user_search()
			elif self.mode == "name_edit":
				self.name_edit()
			elif self.mode == "level_editor":
				self.level_editor()
			elif self.mode == "admin_panel":
				self.admin_panel()
			elif self.mode == "leaderboard":
				self.leaderboard()
			elif self.mode == "profile":
				self.profile()
			elif self.mode == "settings":
				self.settings()
			elif self.mode == "challenges":
				self.challenges()
			else:
				self.game()
			pygame.display.flip()
			self.clock.tick(60)
		pygame.quit()

if __name__ == "__main__":
	MathFight().run()

