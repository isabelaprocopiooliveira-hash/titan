
"""
BOMBERMAN - Versão Python (Pygame) - Visual Realista
------------------------------------------------------
Controles:
  Setas do teclado -> mover o jogador
  Espaço           -> colocar bomba
  R                -> reiniciar (quando o jogo terminar)
  ESC              -> sair

Instalação:
  pip install pygame
Executar:
  python bomberman.py
"""

import pygame
import random
import sys
import math

# ---------------------------------------------------------
# CONFIGURAÇÕES GERAIS
# ---------------------------------------------------------
TILE = 40
COLS = 15
ROWS = 13
HUD_HEIGHT = 60
WIDTH = COLS * TILE
HEIGHT = ROWS * TILE + HUD_HEIGHT
FPS = 60

EMPTY = 0
WALL = 1
BLOCK = 2

COLOR_HUD_BG_TOP = (42, 42, 42)
COLOR_HUD_BG_BOTTOM = (10, 10, 10)
COLOR_TEXT = (255, 255, 255)


def pseudo(n):
    """Pseudo-aleatório determinístico (mesmo padrão sempre, sem recalcular)."""
    x = math.sin(n * 12.9898) * 43758.5453
    return x - math.floor(x)


def lighten(color, amt):
    return tuple(min(255, c + amt) for c in color)


def make_grid():
    grid = [[EMPTY for _ in range(COLS)] for _ in range(ROWS)]

    for c in range(COLS):
        grid[0][c] = WALL
        grid[ROWS - 1][c] = WALL
    for r in range(ROWS):
        grid[r][0] = WALL
        grid[r][COLS - 1] = WALL

    for r in range(1, ROWS - 1):
        for c in range(1, COLS - 1):
            if r % 2 == 0 and c % 2 == 0:
                grid[r][c] = WALL

    safe_zones = set()
    for (sr, sc) in [(1, 1), (1, COLS - 2), (ROWS - 2, 1), (ROWS - 2, COLS - 2)]:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                safe_zones.add((sr + dr, sc + dc))

    for r in range(1, ROWS - 1):
        for c in range(1, COLS - 1):
            if grid[r][c] == WALL:
                continue
            if (r, c) in safe_zones:
                continue
            if random.random() < 0.65:
                grid[r][c] = BLOCK

    return grid


class Bomb:
    def __init__(self, col, row, bomb_range, owner):
        self.col = col
        self.row = row
        self.range = bomb_range
        self.owner = owner
        self.max_timer = 2.2
        self.timer = 2.2
        self.exploded = False


class Explosion:
    def __init__(self, cells, duration=0.45):
        self.cells = cells
        self.timer = duration
        self.duration = duration


class Enemy:
    def __init__(self, col, row):
        self.x = col * TILE
        self.y = row * TILE + HUD_HEIGHT
        self.speed = 70
        self.dir = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        self.change_timer = random.uniform(0.5, 1.5)
        self.alive = True
        self.facing = "down"
        self.walk_phase = random.uniform(0, 10)

    def rect(self):
        return pygame.Rect(int(self.x) + 6, int(self.y) + 6, TILE - 12, TILE - 12)


class Player:
    def __init__(self, col, row):
        self.x = col * TILE
        self.y = row * TILE + HUD_HEIGHT
        self.speed = 160
        self.lives = 3
        self.bomb_max = 1
        self.bomb_range = 2
        self.alive = True
        self.invincible_timer = 0
        self.facing = "down"
        self.moving = False
        self.walk_phase = 0

    def rect(self):
        return pygame.Rect(int(self.x) + 6, int(self.y) + 6, TILE - 12, TILE - 12)


def cell_blocked(grid, row, col):
    if row < 0 or row >= ROWS or col < 0 or col >= COLS:
        return True
    return grid[row][col] != EMPTY


def rect_collides_grid(grid, rect, bombs, ignore_bombs=None):
    ignore_set = ignore_bombs or ()
    corners = [
        (rect.left, rect.top), (rect.right - 1, rect.top),
        (rect.left, rect.bottom - 1), (rect.right - 1, rect.bottom - 1),
    ]
    for (x, y) in corners:
        col = x // TILE
        row = (y - HUD_HEIGHT) // TILE
        if cell_blocked(grid, row, col):
            return True
        for b in bombs:
            if b in ignore_set:
                continue
            if b.row == row and b.col == col:
                return True
    return False


def try_move(entity, dx, dy, dt, grid, bombs, ignore_bombs=None):
    if dx != 0:
        new_x = entity.x + dx * entity.speed * dt
        rect = pygame.Rect(int(new_x) + 6, int(entity.y) + 6, TILE - 12, TILE - 12)
        if not rect_collides_grid(grid, rect, bombs, ignore_bombs):
            entity.x = new_x
    if dy != 0:
        new_y = entity.y + dy * entity.speed * dt
        rect = pygame.Rect(int(entity.x) + 6, int(new_y) + 6, TILE - 12, TILE - 12)
        if not rect_collides_grid(grid, rect, bombs, ignore_bombs):
            entity.y = new_y


def get_ignored_bombs(rect, bombs):
    """Bombas cujo quadrado ainda encosta no retângulo atual da entidade.
    Assim, o personagem só volta a colidir com uma bomba depois de sair
    COMPLETAMENTE da casa dela (evita o bug de ficar travado ao soltar a bomba)."""
    ignored = []
    for b in bombs:
        bomb_rect = pygame.Rect(b.col * TILE, b.row * TILE + HUD_HEIGHT, TILE, TILE)
        if rect.colliderect(bomb_rect):
            ignored.append(b)
    return ignored


def explode_bomb(bomb, grid, bombs, explosions):
    cells = [(bomb.row, bomb.col)]
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    for dr, dc in directions:
        for i in range(1, bomb.range + 1):
            r = bomb.row + dr * i
            c = bomb.col + dc * i
            if r < 0 or r >= ROWS or c < 0 or c >= COLS:
                break
            if grid[r][c] == WALL:
                break
            cells.append((r, c))
            if grid[r][c] == BLOCK:
                grid[r][c] = EMPTY
                break
            for other in bombs:
                if other is not bomb and not other.exploded and other.row == r and other.col == c:
                    other.timer = 0
    explosions.append(Explosion(cells))


def entity_hit_by_explosion(entity, explosions):
    rect = entity.rect()
    for exp in explosions:
        for (r, c) in exp.cells:
            fire_rect = pygame.Rect(c * TILE, r * TILE + HUD_HEIGHT, TILE, TILE)
            if rect.colliderect(fire_rect):
                return True
    return False


# ---------------------------------------------------------
# DESENHO - TEXTURAS E SOMBRAS REALISTAS
# ---------------------------------------------------------
def draw_shadow(screen, cx, cy, w, h):
    surf = pygame.Surface((w * 2, h * 2), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 110), (0, 0, w * 2, h * 2))
    screen.blit(surf, (cx - w, cy - h))


def draw_grass_tile(screen, x, y, r, c):
    for i in range(TILE):
        t = i / TILE
        color = (
            int(93 + (74 - 93) * t),
            int(168 + (138 - 168) * t),
            int(80 + (62 - 80) * t),
        )
        pygame.draw.line(screen, color, (x, y + i), (x + TILE, y + i))

    for i in range(4):
        seed = r * 971 + c * 733 + i * 37
        px = x + pseudo(seed) * TILE
        py = y + pseudo(seed + 1) * TILE
        shade = (70, 120, 55) if pseudo(seed + 2) > 0.5 else (110, 180, 90)
        pygame.draw.ellipse(screen, shade, (px, py, 6, 3))


def draw_wall_tile(screen, x, y, r, c):
    for i in range(TILE):
        t = i / TILE
        color = (
            int(138 + (90 - 138) * t),
            int(138 + (90 - 138) * t),
            int(148 + (100 - 148) * t),
        )
        pygame.draw.line(screen, color, (x, y + i), (x + TILE, y + i))

    mortar = (30, 30, 35)
    row_offset = 0 if r % 2 == 0 else TILE // 2
    pygame.draw.line(screen, mortar, (x, y + TILE // 2), (x + TILE, y + TILE // 2), 1)
    pygame.draw.line(screen, mortar, (x + row_offset, y), (x + row_offset, y + TILE // 2), 1)
    off2 = (row_offset + TILE // 2) % TILE
    pygame.draw.line(screen, mortar, (x + off2, y + TILE // 2), (x + off2, y + TILE), 1)

    pygame.draw.line(screen, (255, 255, 255, 60), (x + 1, y + 1), (x + TILE - 1, y + 1), 1)
    pygame.draw.line(screen, (255, 255, 255, 60), (x + 1, y + 1), (x + 1, y + TILE - 1), 1)
    pygame.draw.line(screen, (0, 0, 0), (x + TILE - 1, y + 1), (x + TILE - 1, y + TILE - 1), 1)
    pygame.draw.line(screen, (0, 0, 0), (x + 1, y + TILE - 1), (x + TILE - 1, y + TILE - 1), 1)


def draw_block_tile(screen, x, y, r, c):
    draw_grass_tile(screen, x, y, r, c)
    bx, by, bw, bh = x + 3, y + 3, TILE - 6, TILE - 6
    for i in range(bh):
        t = i / bh
        color = (
            int(201 + (138 - 201) * t),
            int(146 + (90 - 146) * t),
            int(79 + (44 - 79) * t),
        )
        pygame.draw.line(screen, color, (bx, by + i), (bx + bw, by + i))

    plank_color = (70, 40, 15)
    for i in range(1, 3):
        ly = by + (bh // 3) * i
        pygame.draw.line(screen, plank_color, (bx, ly), (bx + bw, ly), 1)

    diag_color = (70, 40, 15)
    pygame.draw.line(screen, diag_color, (bx, by), (bx + bw, by + bh), 1)
    pygame.draw.line(screen, diag_color, (bx + bw, by), (bx, by + bh), 1)

    bolt_color = (58, 42, 21)
    for (px, py) in [(bx + 4, by + 4), (bx + bw - 4, by + 4), (bx + 4, by + bh - 4), (bx + bw - 4, by + bh - 4)]:
        pygame.draw.circle(screen, bolt_color, (px, py), 2)

    pygame.draw.rect(screen, (255, 255, 255), (bx, by, bw, bh), 1)


def draw_grid(screen, grid):
    for r in range(ROWS):
        for c in range(COLS):
            x = c * TILE
            y = r * TILE + HUD_HEIGHT
            tile = grid[r][c]
            if tile == WALL:
                draw_wall_tile(screen, x, y, r, c)
            elif tile == BLOCK:
                draw_block_tile(screen, x, y, r, c)
            else:
                draw_grass_tile(screen, x, y, r, c)


def draw_hud(screen, font, player, score, message=""):
    for i in range(HUD_HEIGHT):
        t = i / HUD_HEIGHT
        color = (
            int(42 + (10 - 42) * t),
            int(42 + (10 - 42) * t),
            int(42 + (10 - 42) * t),
        )
        pygame.draw.line(screen, color, (0, i), (WIDTH, i))

    lives_txt = font.render(f"❤ Vidas: {player.lives}", True, COLOR_TEXT)
    bombs_txt = font.render(f"Bombas: {player.bomb_max}  Alcance: {player.bomb_range}", True, COLOR_TEXT)
    score_txt = font.render(f"Pontos: {score}", True, COLOR_TEXT)
    screen.blit(lives_txt, (10, 18))
    screen.blit(bombs_txt, (170, 18))
    screen.blit(score_txt, (440, 18))
    if message:
        msg_txt = font.render(message, True, (255, 228, 94))
        screen.blit(msg_txt, (WIDTH // 2 - msg_txt.get_width() // 2, HEIGHT - 28))


def draw_character(screen, entity, body_top, body_bottom, head_color, is_enemy):
    rect = entity.rect()
    cx = rect.centerx
    cy = rect.centery
    foot_y = rect.bottom

    draw_shadow(screen, cx, foot_y - 2, rect.width // 2, rect.height // 6)

    leg_swing = math.sin(entity.walk_phase * 8) * 5 if getattr(entity, "moving", True) else 0
    leg_color = (26, 42, 74) if not is_enemy else (58, 16, 16)
    pygame.draw.line(screen, leg_color, (cx - 5, cy + rect.height * 0.25), (cx - 5 + leg_swing * 0.4, foot_y - 1), 5)
    pygame.draw.line(screen, leg_color, (cx + 5, cy + rect.height * 0.25), (cx + 5 - leg_swing * 0.4, foot_y - 1), 5)

    body_h = int(rect.height * 0.6)
    body_rect = pygame.Rect(rect.left, cy - int(rect.height * 0.15), rect.width, body_h)
    body_surf = pygame.Surface((body_rect.width, body_rect.height), pygame.SRCALPHA)
    for i in range(body_rect.height):
        t = i / max(1, body_rect.height)
        color = tuple(int(body_top[k] + (body_bottom[k] - body_top[k]) * t) for k in range(3))
        pygame.draw.line(body_surf, color, (0, i), (body_rect.width, i))
    pygame.draw.rect(body_surf, (255, 255, 255, 0), body_surf.get_rect(), border_radius=8)
    screen.blit(body_surf, body_rect.topleft)
    pygame.draw.rect(screen, body_bottom, body_rect, 1, border_radius=8)

    head_r = int(rect.width * 0.42)
    head_cx = cx
    head_cy = rect.top + int(head_r * 0.9)
    highlight = lighten(head_color, 40)
    for rr in range(head_r, 0, -1):
        t = rr / head_r
        color = tuple(int(highlight[k] + (head_color[k] - highlight[k]) * (1 - t)) for k in range(3))
        pygame.draw.circle(screen, color, (head_cx, head_cy), rr)

    eo_x, eo_y = 0, 1
    if entity.facing == "left":
        eo_x, eo_y = -2, 0
    elif entity.facing == "right":
        eo_x, eo_y = 2, 0
    elif entity.facing == "up":
        eo_x, eo_y = 0, -2

    eye_offset = int(head_r * 0.42)
    pygame.draw.circle(screen, (255, 255, 255), (head_cx - eye_offset, head_cy - 1), 3)
    pygame.draw.circle(screen, (255, 255, 255), (head_cx + eye_offset, head_cy - 1), 3)
    pupil_color = (160, 0, 0) if is_enemy else (17, 17, 17)
    pygame.draw.circle(screen, pupil_color, (head_cx - eye_offset + eo_x, head_cy - 1 + eo_y), 1)
    pygame.draw.circle(screen, pupil_color, (head_cx + eye_offset + eo_x, head_cy - 1 + eo_y), 1)

    if is_enemy:
        pygame.draw.polygon(screen, head_color, [
            (head_cx - head_r * 0.6, head_cy - head_r * 0.7),
            (head_cx - head_r * 0.3, head_cy - head_r * 1.3),
            (head_cx - head_r * 0.1, head_cy - head_r * 0.7),
        ])
        pygame.draw.polygon(screen, head_color, [
            (head_cx + head_r * 0.6, head_cy - head_r * 0.7),
            (head_cx + head_r * 0.3, head_cy - head_r * 1.3),
            (head_cx + head_r * 0.1, head_cy - head_r * 0.7),
        ])


def draw_bomb(screen, bomb, elapsed):
    x = bomb.col * TILE + TILE // 2
    y = bomb.row * TILE + HUD_HEIGHT + TILE // 2
    progress = 1 - (bomb.timer / bomb.max_timer)
    pulse = (math.sin(elapsed * 25) * 0.15 + 1) if progress > 0.7 else 1
    radius = int((TILE // 3) * pulse)

    draw_shadow(screen, x, y + int(radius * 0.6), int(radius * 1.1), int(radius * 0.35))

    base = (85, 34, 34) if progress > 0.7 else (58, 58, 58)
    for rr in range(radius, 0, -1):
        t = rr / radius
        color = tuple(int(base[k] * t) for k in range(3))
        pygame.draw.circle(screen, color, (x, y), rr)

    highlight_surf = pygame.Surface((radius, radius), pygame.SRCALPHA)
    pygame.draw.circle(highlight_surf, (255, 255, 255, 70), (int(radius * 0.4), int(radius * 0.4)), int(radius * 0.3))
    screen.blit(highlight_surf, (x - int(radius * 0.7), y - int(radius * 0.7)))

    pygame.draw.line(screen, (138, 90, 44), (x, y - radius), (x + 3, y - radius - 14), 2)
    spark_color = (255, 228, 94) if math.sin(elapsed * 30) > 0 else (255, 138, 42)
    pygame.draw.circle(screen, spark_color, (x + 3, y - radius - 14), 3)


def draw_explosion(screen, exp):
    progress = 1 - exp.timer / exp.duration
    if progress < 0.3:
        size_factor = progress / 0.3
    else:
        size_factor = 1 - (progress - 0.3) / 0.7 * 0.3

    for (r, c) in exp.cells:
        cx = c * TILE + TILE // 2
        cy = r * TILE + HUD_HEIGHT + TILE // 2
        outer_r = max(1, int((TILE // 2) * size_factor))

        surf = pygame.Surface((outer_r * 2, outer_r * 2), pygame.SRCALPHA)
        for rr in range(outer_r, 0, -1):
            t = rr / outer_r
            if t < 0.35:
                color = (255, 255, 220, 240)
            elif t < 0.7:
                color = (255, 200, 60, 220)
            else:
                color = (255, 120, 30, 160)
            pygame.draw.circle(surf, color, (outer_r, outer_r), rr)
        screen.blit(surf, (cx - outer_r, cy - outer_r))


def reset_game():
    grid = make_grid()
    player = Player(1, 1)
    enemies = [
        Enemy(COLS - 2, 1),
        Enemy(1, ROWS - 2),
        Enemy(COLS - 2, ROWS - 2),
    ]
    bombs = []
    explosions = []
    return grid, player, enemies, bombs, explosions


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Bomberman - Python (Visual Realista)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("arial", 18, bold=True)

    grid, player, enemies, bombs, explosions = reset_game()
    score = 0
    game_over = False
    victory = False
    elapsed = 0.0

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_r and (game_over or victory):
                    grid, player, enemies, bombs, explosions = reset_game()
                    score = 0
                    game_over = False
                    victory = False
                    elapsed = 0.0
                if event.key == pygame.K_SPACE and player.alive and not game_over and not victory:
                    col = (player.x + TILE // 2) // TILE
                    row = (player.y - HUD_HEIGHT + TILE // 2) // TILE
                    active_player_bombs = [b for b in bombs if b.owner is player and not b.exploded]
                    already_here = any(b.row == row and b.col == col for b in bombs)
                    if len(active_player_bombs) < player.bomb_max and not already_here:
                        bombs.append(Bomb(col, row, player.bomb_range, player))

        if not game_over and not victory:
            elapsed += dt
            keys = pygame.key.get_pressed()
            dx = dy = 0
            if keys[pygame.K_LEFT]:
                dx = -1
                player.facing = "left"
            elif keys[pygame.K_RIGHT]:
                dx = 1
                player.facing = "right"
            if keys[pygame.K_UP]:
                dy = -1
                player.facing = "up"
            elif keys[pygame.K_DOWN]:
                dy = 1
                player.facing = "down"

            player.moving = dx != 0 or dy != 0
            if player.moving:
                player.walk_phase += dt
            else:
                player.walk_phase = 0

            if player.alive:
                ignored_bombs = get_ignored_bombs(player.rect(), bombs)
                try_move(player, dx, 0, dt, grid, bombs, ignored_bombs)
                try_move(player, 0, dy, dt, grid, bombs, ignored_bombs)

            for enemy in enemies:
                if not enemy.alive:
                    continue
                enemy.walk_phase += dt
                enemy.change_timer -= dt
                moved_rect_check = pygame.Rect(
                    int(enemy.x + enemy.dir[0] * 4) + 6,
                    int(enemy.y + enemy.dir[1] * 4) + 6,
                    TILE - 12, TILE - 12,
                )
                blocked = rect_collides_grid(grid, moved_rect_check, bombs)
                if enemy.change_timer <= 0 or blocked:
                    enemy.dir = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
                    enemy.change_timer = random.uniform(0.6, 1.6)
                    if enemy.dir[0] < 0:
                        enemy.facing = "left"
                    elif enemy.dir[0] > 0:
                        enemy.facing = "right"
                    elif enemy.dir[1] < 0:
                        enemy.facing = "up"
                    else:
                        enemy.facing = "down"
                enemy.moving = True
                try_move(enemy, enemy.dir[0], enemy.dir[1], dt, grid, bombs)

            for b in bombs:
                if not b.exploded:
                    b.timer -= dt
                    if b.timer <= 0:
                        b.exploded = True
                        explode_bomb(b, grid, bombs, explosions)
            bombs = [b for b in bombs if not b.exploded]

            for exp in explosions:
                exp.timer -= dt
            for exp in explosions:
                if player.alive and player.invincible_timer <= 0 and entity_hit_by_explosion(player, [exp]):
                    player.lives -= 1
                    player.invincible_timer = 1.5
                    if player.lives <= 0:
                        player.alive = False
                        game_over = True
                for enemy in enemies:
                    if enemy.alive and entity_hit_by_explosion(enemy, [exp]):
                        enemy.alive = False
                        score += 100
            explosions = [e for e in explosions if e.timer > 0]

            if player.invincible_timer > 0:
                player.invincible_timer -= dt

            if all(not e.alive for e in enemies):
                victory = True

        screen.fill((30, 30, 30))
        draw_grid(screen, grid)

        for b in bombs:
            draw_bomb(screen, b, elapsed)
        for exp in explosions:
            draw_explosion(screen, exp)

        for enemy in enemies:
            if enemy.alive:
                draw_character(screen, enemy, (224, 80, 80), (160, 32, 32), (199, 48, 48), True)

        if player.alive:
            if player.invincible_timer <= 0 or int(player.invincible_timer * 10) % 2 == 0:
                draw_character(screen, player, (74, 156, 255), (26, 92, 191), (47, 111, 214), False)

        message = ""
        if game_over:
            message = "GAME OVER - pressione R para reiniciar"
        elif victory:
            message = "VOCÊ VENCEU! - pressione R para reiniciar"

        draw_hud(screen, font, player, score, message)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()