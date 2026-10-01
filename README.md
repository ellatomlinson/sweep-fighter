# sweep-fighter
Make my Roomba play Street Fighter II

A ceiling webcam tracks the neon-pink Roomba, splits the arena into a 3×3 grid,
and presses a Street Fighter II input for whichever cell he's in (Fish-Plays-Pokémon style).

```
 HADOUKEN  | JUMP     | JUMP FWD
 PUNCH     | HADOUKEN | KICK
 PUNCH 2   | CROUCH   | KICK 2
```

## Setup
```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python sweep_fighter.py arena   # click arena corners TL, TR, BR, BL
.venv/bin/python sweep_fighter.py tune    # adjust HSV sliders until only the pink paper is white; press s
.venv/bin/python sweep_fighter.py play --dry-run   # watch moves print
.venv/bin/python sweep_fighter.py play    # then click into the emulator window
```
macOS: grant your terminal **Camera** and **Accessibility** permissions (Accessibility is needed to send keys).

Edit `config.json` (created on first save) to remap keys to your emulator's bindings,
change the grid, or tune `hold_frames` / `repeat_seconds`. Use `--camera 1` if the wrong webcam opens.
