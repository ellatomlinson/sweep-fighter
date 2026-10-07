# sweep-fighter
Make my Roomba (Barry) play Street Fighter II

A ceiling webcam tracks the Roomba (with neon pink paper on it), splits the arena into a 3×3 grid,
and presses a Street Fighter II input for whichever cell he's in.

The current grid correlates with the following in-game actions:
```
 HADOUKEN | JUMP     | JUMP FWD
 PUNCH    | HADOUKEN | KICK
 PUNCH 2  | CROUCH   | KICK 2
```

The top-left and center squares trigger Hadouken. The other squares map to jumps,
punches, kicks, or crouch.

## Setup
```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python sweep_fighter.py arena   # click arena corners TL, TR, BR, BL
.venv/bin/python sweep_fighter.py tune    # adjust HSV sliders until only the pink paper is white; press s
.venv/bin/python sweep_fighter.py play --dry-run   # watch moves print
.venv/bin/python sweep_fighter.py play    # then click into the emulator window
```
