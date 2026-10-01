"""Sweep Fighter: a ceiling webcam tracks a neon-pink Roomba and turns its
position in the arena into Street Fighter II button presses."""

import argparse
import json
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np
from pynput.keyboard import Controller, Key

CONFIG_PATH = Path(__file__).with_name("config.json")

# 3x3 grid, read as the camera sees it (row 0 = top of the image).
# Each cell is a list of "moves"; a move is a list of keys held together.
# Browser game mapping: arrows = directions, a = X, z = A.
# Change the grid sequences below if the game's button roles differ.
DEFAULT_CONFIG = {
    "camera": 0,
    "hsv_lower": [140, 80, 80],
    "hsv_upper": [175, 255, 255],
    "min_area": 400,
    # Arena corners in image pixels (TL, TR, BR, BL). None = whole frame.
    "arena": None,
    "hold_frames": 5,       # frames Roomba must stay in a cell before it fires
    "repeat_seconds": 0.3,  # re-fire the cell's action while he stays there
    "press_seconds": 0.08,
"grid": [
        [{"name": "HADOUKEN", "seq": [["down"], ["down", "right"], ["right", "a"]]},
         {"name": "JUMP BACK", "seq": [["up", "left"]]},
         {"name": "JUMP FWD", "seq": [["up", "right"]]}],
        [{"name": "PUNCH", "seq": [["a"]]},
         {"name": "HADOUKEN", "seq": [["down"], ["down", "right"], ["right", "a"]]},
         {"name": "KICK", "seq": [["z"]]}],
        [{"name": "PUNCH 2 (B)", "seq": [["x"]]},
         {"name": "CROUCH", "seq": [["down"]]},
         {"name": "KICK 2 (Y)", "seq": [["s"]]}],
    ],
}

SPECIAL_KEYS = {"up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
                "enter": Key.enter, "space": Key.space, "shift": Key.shift}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        cfg.update(json.loads(CONFIG_PATH.read_text()))
        # Add the corner Hadouken to configs saved before that grid change,
        # keeping the existing center Hadouken.
        top_left = cfg["grid"][0][0]
        if top_left["name"] == "JUMP BACK":
            cfg["grid"][0][0] = DEFAULT_CONFIG["grid"][0][0]
        # Replace these original defaults in existing saved configs, without
        # overwriting any custom grid actions or camera/arena calibration.
        for row, col in ((2, 0), (2, 2)):
            old_action = cfg["grid"][row][col]
            if old_action["name"] in {"WALK BACK", "WALK FWD"}:
                cfg["grid"][row][col] = DEFAULT_CONFIG["grid"][row][col]
    return cfg


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    print(f"Saved {CONFIG_PATH}")


def find_roomba(frame, cfg):
    hsv = cv2.cvtColor(cv2.GaussianBlur(frame, (7, 7), 0), cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(cfg["hsv_lower"]), np.array(cfg["hsv_upper"]))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, mask
    c = max(contours, key=cv2.contourArea)
    if cv2.contourArea(c) < cfg["min_area"]:
        return None, mask
    m = cv2.moments(c)
    return (m["m10"] / m["m00"], m["m01"] / m["m00"]), mask


def arena_transform(cfg, w, h):
    """Homography from image pixels to a unit square, so a tilted camera works."""
    src = np.float32(cfg["arena"] or [[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])
    return cv2.getPerspectiveTransform(src, dst), src


def to_cell(pt, M, rows, cols):
    u, v = cv2.perspectiveTransform(np.float32([[pt]]), M)[0][0]
    if not (0 <= u < 1 and 0 <= v < 1):
        return None
    return int(v * rows), int(u * cols)


class Presser:
    def __init__(self, cfg, dry_run):
        self.kb = Controller()
        self.cfg = cfg
        self.dry_run = dry_run

    def _key(self, k):
        return SPECIAL_KEYS.get(k, k)

    def fire(self, action):
        print(f"-> {action['name']}")
        if self.dry_run:
            return
        for combo in action["seq"]:
            keys = [self._key(k) for k in combo]
            for k in keys:
                self.kb.press(k)
            time.sleep(self.cfg["press_seconds"])
            for k in reversed(keys):
                self.kb.release(k)
            time.sleep(0.02)


def draw_overlay(frame, src, rows, cols, grid, active, pt):
    M_inv = cv2.getPerspectiveTransform(
        np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]), src)

    def img_pt(u, v):
        return tuple(int(x) for x in cv2.perspectiveTransform(np.float32([[[u, v]]]), M_inv)[0][0])

    for r in range(rows):
        for c in range(cols):
            corners = np.array([img_pt(c / cols, r / rows), img_pt((c + 1) / cols, r / rows),
                                img_pt((c + 1) / cols, (r + 1) / rows), img_pt(c / cols, (r + 1) / rows)])
            hot = active == (r, c)
            if hot:
                overlay = frame.copy()
                cv2.fillPoly(overlay, [corners], (0, 200, 255))
                cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)
            cv2.polylines(frame, [corners], True, (255, 255, 255), 1)
            cx, cy = img_pt((c + 0.5) / cols, (r + 0.5) / rows)
            label = grid[r][c]["name"]
            (tw, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.putText(frame, label, (cx - tw // 2, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 255, 255) if hot else (255, 255, 255), 1, cv2.LINE_AA)
    if pt:
        cv2.circle(frame, (int(pt[0]), int(pt[1])), 12, (0, 255, 0), 3)


def calibrate_arena(cap, cfg):
    """Click the 4 arena corners: top-left, top-right, bottom-right, bottom-left."""
    pts = []
    win = "Click arena corners TL, TR, BR, BL  (r = reset, q = cancel)"
    cv2.namedWindow(win)
    cv2.setMouseCallback(win, lambda e, x, y, *_: pts.append([x, y])
                         if e == cv2.EVENT_LBUTTONDOWN and len(pts) < 4 else None)
    while len(pts) < 4:
        ok, frame = cap.read()
        if not ok:
            continue
        for p in pts:
            cv2.circle(frame, tuple(p), 6, (0, 255, 0), -1)
        if len(pts) > 1:
            cv2.polylines(frame, [np.array(pts)], False, (0, 255, 0), 2)
        cv2.imshow(win, frame)
        k = cv2.waitKey(1) & 0xFF
        if k == ord("r"):
            pts.clear()
        elif k == ord("q"):
            cv2.destroyWindow(win)
            return
    cfg["arena"] = pts
    save_config(cfg)
    cv2.destroyWindow(win)


def tune_colour(cap, cfg):
    """Sliders for the HSV range; press s to save, q to quit."""
    win = "Tune pink (s = save, q = quit)"
    cv2.namedWindow(win)
    names = ["H lo", "S lo", "V lo", "H hi", "S hi", "V hi"]
    vals = cfg["hsv_lower"] + cfg["hsv_upper"]
    for n, v in zip(names, vals):
        cv2.createTrackbar(n, win, v, 179 if n.startswith("H") else 255, lambda _: None)
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        v = [cv2.getTrackbarPos(n, win) for n in names]
        cfg["hsv_lower"], cfg["hsv_upper"] = v[:3], v[3:]
        pt, mask = find_roomba(frame, cfg)
        if pt:
            cv2.circle(frame, (int(pt[0]), int(pt[1])), 12, (0, 255, 0), 3)
        cv2.imshow(win, np.hstack([frame, cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)]))
        k = cv2.waitKey(1) & 0xFF
        if k == ord("s"):
            save_config(cfg)
        elif k == ord("q"):
            break
    cv2.destroyWindow(win)


def play(cap, cfg, dry_run):
    grid = cfg["grid"]
    rows, cols = len(grid), len(grid[0])
    presser = Presser(cfg, dry_run)
    history = deque(maxlen=cfg["hold_frames"])
    active, last_fire, paused = None, 0.0, False
    print("Playing! Keep the emulator window focused. "
          "Preview window keys: p = pause, q = quit.")

    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        h, w = frame.shape[:2]
        M, src = arena_transform(cfg, w, h)
        pt, _ = find_roomba(frame, cfg)
        history.append(to_cell(pt, M, rows, cols) if pt else None)

        # Debounce: only switch cells once he's been in the new one for a few frames.
        if len(history) == history.maxlen and len(set(history)) == 1:
            stable = history[0]
            now = time.time()
            if stable is not None and not paused and (
                    stable != active or now - last_fire > cfg["repeat_seconds"]):
                presser.fire(grid[stable[0]][stable[1]])
                last_fire = now
            active = stable

        draw_overlay(frame, src, rows, cols, grid, active, pt)
        if paused:
            cv2.putText(frame, "PAUSED", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        cv2.imshow("Sweep Fighter", frame)
        k = cv2.waitKey(1) & 0xFF
        if k == ord("q"):
            break
        if k == ord("p"):
            paused = not paused


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", nargs="?", default="play", choices=["play", "tune", "arena"])
    ap.add_argument("--camera", type=int, help="webcam index (overrides config)")
    ap.add_argument("--dry-run", action="store_true", help="print moves, don't press keys")
    args = ap.parse_args()

    cfg = load_config()
    if args.camera is not None:
        cfg["camera"] = args.camera
    cap = cv2.VideoCapture(cfg["camera"])
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera {cfg['camera']}")
    try:
        {"tune": lambda: tune_colour(cap, cfg),
         "arena": lambda: calibrate_arena(cap, cfg),
         "play": lambda: play(cap, cfg, args.dry_run)}[args.mode]()
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
