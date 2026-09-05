"""Math Fight: a graph-powered arithmetic duel.

Run with: python main.py
The game uses only the Python standard library so it is easy to share.
"""

from __future__ import annotations

import math
import json
import random
import re
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
		self.coins, self.diamonds, self.mustache, self.unlocked_preset_names, self.custom_preset_unlocked, self.custom_preset_equation = self.load_save()
		self.shop_status = "Customize your orb."
		self.mustache_orb = self.load_mustache_orb()
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

	def button(self, rect: pygame.Rect, label: str, detail: str, color=CYAN) -> None:
		mouse = pygame.mouse.get_pos()
		hover = rect.collidepoint(mouse)
		shadow = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
		pygame.draw.rect(shadow, (0, 0, 0, 110), shadow.get_rect(), border_radius=18)
		self.screen.blit(shadow, (rect.x + 10, rect.y + 12))
		card = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
		pygame.draw.rect(card, (19, 31, 52, 235), card.get_rect(), border_radius=18)
		pygame.draw.rect(card, (*color, 160) if hover else (*color, 120), (16, 16, rect.w - 32, 52), border_radius=12)
		pygame.draw.rect(card, (255, 255, 255, 24), (14, 14, rect.w - 28, rect.h - 28), 1, border_radius=18)
		self.screen.blit(card, rect.topleft)
		label_surface = self.font.render(label, True, BG if hover else (9, 16, 30))
		self.screen.blit(label_surface, label_surface.get_rect(center=(rect.centerx, rect.y + 42)))
		self.text(detail, rect.x + 24, rect.y + 82, (201, 216, 255), self.small)
		if hover:
			pygame.draw.line(self.screen, color, (rect.x + 24, rect.bottom - 12), (rect.right - 24, rect.bottom - 12), 2)

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

	def menu(self) -> None:
		self.screen.fill(BG)
		# ambient glows
		for center, radius, color in [((260, 120), 180, (94, 232, 249)), ((980, 180), 220, (168, 130, 255)), ((770, 660), 260, (251, 191, 36))]:
			glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
			pygame.draw.circle(glow, (*color, 30), (radius, radius), radius)
			self.screen.blit(glow, (center[0] - radius, center[1] - radius))

		hero = pygame.Rect(56, 60, 1168, 188)
		hero_shadow = pygame.Surface((hero.w, hero.h), pygame.SRCALPHA)
		pygame.draw.rect(hero_shadow, (0, 0, 0, 110), hero_shadow.get_rect(), border_radius=28)
		self.screen.blit(hero_shadow, (hero.x + 10, hero.y + 12))
		hero_panel = pygame.Surface((hero.w, hero.h), pygame.SRCALPHA)
		pygame.draw.rect(hero_panel, (17, 27, 48, 235), hero_panel.get_rect(), border_radius=28)
		pygame.draw.rect(hero_panel, (27, 42, 69, 210), (18, 18, hero.w - 36, hero.h - 36), border_radius=24)
		self.screen.blit(hero_panel, hero.topleft)
		self.text("MATH FIGHT", hero.x + 42, hero.y + 48, CYAN, self.title)
		self.text("DRAW THE LINE. BREAK THE LINE.", hero.x + 48, hero.y + 122, GOLD, self.font)
		self.text("OFFLINE // 1 PLAYER VS CPU", hero.x + 48, hero.y + 156, MUTED, self.small)

		currency_bar = pygame.Rect(905, 80, 285, 64)
		currency_panel = pygame.Surface((currency_bar.w, currency_bar.h), pygame.SRCALPHA)
		pygame.draw.rect(currency_panel, (10, 18, 34, 180), currency_panel.get_rect(), border_radius=16)
		self.screen.blit(currency_panel, currency_bar.topleft)
		self.text(f"COINS {self.coins:04d}", currency_bar.x + 18, currency_bar.y + 20, GOLD, self.font)
		self.text(f"DIAMONDS {self.diamonds:02d}", currency_bar.x + 18, currency_bar.y + 42, (168, 130, 255), self.small)

		self.button(pygame.Rect(74, 300, 340, 148), "PRESET ARSENAL", "Verified equation weapons", CYAN)
		self.button(pygame.Rect(470, 300, 340, 148), "HARD MODE", "Type it yourself. No preview.", GOLD)
		self.button(pygame.Rect(866, 300, 340, 148), "ORB LAB", "Spend coins and diamonds", (168, 130, 255))

		weapon_shop = pygame.Rect(866, 494, 340, 54)
		mouse = pygame.mouse.get_pos()
		weapon_hover = weapon_shop.collidepoint(mouse)
		shop_panel = pygame.Surface((weapon_shop.w, weapon_shop.h), pygame.SRCALPHA)
		pygame.draw.rect(shop_panel, (20, 33, 58, 220), shop_panel.get_rect(), border_radius=14)
		pygame.draw.rect(shop_panel, (168, 130, 255, 200) if weapon_hover else (168, 130, 255, 140), (10, 10, weapon_shop.w - 20, weapon_shop.h - 20), border_radius=10)
		self.screen.blit(shop_panel, weapon_shop.topleft)
		self.text("WEAPON SHOP", weapon_shop.x + 88, weapon_shop.y + 17, BG if weapon_hover else TEXT, self.small)

		how_to_play = pygame.Rect(72, 494, 220, 54)
		mouse = pygame.mouse.get_pos()
		hover = how_to_play.collidepoint(mouse)
		button_panel = pygame.Surface((how_to_play.w, how_to_play.h), pygame.SRCALPHA)
		pygame.draw.rect(button_panel, (20, 33, 58, 220), button_panel.get_rect(), border_radius=14)
		pygame.draw.rect(button_panel, (251, 191, 36, 200) if hover else (251, 191, 36, 140), (10, 10, how_to_play.w - 20, how_to_play.h - 20), border_radius=10)
		self.screen.blit(button_panel, how_to_play.topleft)
		self.text("HOW TO PLAY", how_to_play.x + 26, how_to_play.y + 17, BG if hover else TEXT, self.small)

		# animated floating orb preview
		orb_x = 1125 + math.sin(self.preview_phase * 1.2) * 14
		orb_y = 604 + math.cos(self.preview_phase * 1.5) * 12
		orb_scale = 92 + math.sin(self.preview_phase * 1.8) * 9
		glow_orb = pygame.Surface((180, 180), pygame.SRCALPHA)
		pygame.draw.circle(glow_orb, (103, 232, 249, 35), (90, 90), 74 + int(math.sin(self.preview_phase) * 12))
		self.screen.blit(glow_orb, (orb_x - 90, orb_y - 90))
		self.draw_mustache_orb((int(orb_x), int(orb_y)), int(orb_scale))

		self.text("GRAPH ARENA / PREVIEW READY", 74, 692, GOLD, self.small)

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

	def load_save(self) -> tuple[int, int, bool, list[str], bool, str]:
		try:
			data = json.loads(self.save_path.read_text(encoding="utf-8"))
			return (
				int(data.get("coins", 0)),
				int(data.get("diamonds", 3)),
				bool(data.get("mustache", False)),
				list(data.get("unlocked_preset_names", [])),
				bool(data.get("custom_preset_unlocked", False)),
				str(data.get("custom_preset_equation", "x^2 - 2")),
			)
		except (OSError, ValueError, TypeError, json.JSONDecodeError):
			return 0, 3, False, [], False, "x^2 - 2"

	def save(self) -> None:
		try:
			self.save_path.write_text(json.dumps({
				"coins": self.coins,
				"diamonds": self.diamonds,
				"mustache": self.mustache,
				"unlocked_preset_names": self.unlocked_preset_names,
				"custom_preset_unlocked": self.custom_preset_unlocked,
				"custom_preset_equation": self.custom_preset_equation,
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

	def finish_battle(self, result: str) -> None:
		if self.reward_paid:
			return
		self.result = result
		self.reward_paid = True
		self.coins += 100 if result == "win" else 20
		if result == "win":
			self.diamonds += 1
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
			for index, (name, equation, _) in enumerate(presets):
				rect = pygame.Rect(16, 160 + index * 52, 253, 42)
				pygame.draw.rect(self.screen, (14, 116, 144) if index == self.selected else PANEL_LIGHT, rect, border_radius=3)
				self.text(f"{index + 1}  {name}", 27, rect.y + 6, TEXT, self.small)
				self.text(equation, 27, rect.y + 23, CYAN, self.small)
		else:
			entry = pygame.Rect(18, 168, 249, 46)
			pygame.draw.rect(self.screen, (26, 42, 68), entry, border_radius=3)
			pygame.draw.rect(self.screen, CYAN if self.input_active else MUTED, entry, 2, border_radius=3)
			self.text(self.input_text, 28, 180, TEXT, self.font)
			self.text("Allowed: y=, x, + - * / ^, sin(x), cos(x)", 20, 230, MUTED, self.small)
			self.text("Example: y = 0.0828x^2 + 10", 20, 252, MUTED, self.small)
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
		elif self.mode == "tutorial":
			if pygame.Rect(170 + 720, 110 + 440, 150, 54).collidepoint(x, y):
				self.mode = "menu"
			elif pygame.Rect(170 + 50, 110 + 440, 150, 54).collidepoint(x, y) and self.tutorial_page > 0:
				self.tutorial_page -= 1
			elif pygame.Rect(170 + 210, 110 + 440, 150, 54).collidepoint(x, y) and self.tutorial_page < len(self.tutorial_pages) - 1:
				self.tutorial_page += 1
			elif pygame.Rect(170 + 210, 110 + 440, 150, 54).collidepoint(x, y):
				self.mode = "menu"
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
		if self.mode == "preset" and 16 <= x <= 269 and 160 <= y < 160 + 52 * len(self.available_presets):
			self.selected = max(0, min(len(self.available_presets) - 1, (y - 160) // 52))
			self.refresh_preview()
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
			else:
				self.game()
			pygame.display.flip()
			self.clock.tick(60)
		pygame.quit()

if __name__ == "__main__":
	MathFight().run()

