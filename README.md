# Robot Navigation — A* + DQN

A hybrid robot navigation simulator built with **Pygame**, combining classical **A\* pathfinding** with a **Deep Q-Network (DQN)** for dynamic obstacle avoidance.

---

## Demo

The robot navigates a 50×50 grid from start to goal, switching between A\* and RL modes in real time.

---

## Features

- **A\* Pathfinding** — optimal path planning on a static grid
- **DQN Fallback** — RL model takes over when obstacles block the path
- **Dynamic Obstacles** — 16 obstacles move every frame
- **LIDAR Visualization** — 360° ray-cast sensor with danger highlighting
- **Emergency Recovery** — auto-detects stuck state and breaks out
- **Fullscreen UI** — animated sidebar, FPS counter, mode badge

---

## Project Structure

```
robot-navigation-ai/
├── main.py                  # Entry point & game loop
├── requirements.txt
├── .gitignore
│
├── core/
│   ├── environment.py       # Grid creation, dynamic obstacle movement
│   ├── pathfinding.py       # A* algorithm
│   └── navigation.py       # RL step, emergency step, obstacle detection
│
├── models/
│   ├── dqn.py               # DQN neural network definition
│   └── dqn_model.pth        # Trained model weights (not tracked by git)
│
└── ui/
    ├── config.py            # All constants, colors, fonts, layout
    ├── renderer.py          # Grid, robot, goal, lidar, path drawing
    └── sidebar.py           # Sidebar, status bar, badges, overlays
```

---

## Installation

```bash
git clone https://github.com/Unknown183-a/robot-navigation-ai.git
cd robot-navigation-ai
pip install -r requirements.txt
```

Place your trained `dqn_model.pth` inside the `models/` folder.

---

## Usage

```bash
python main.py
```

### Controls

| Key | Action              |
|-----|---------------------|
| `P` | Toggle A\* path     |
| `R` | Toggle RL path      |
| `L` | Toggle LIDAR        |
| `E` | Trigger emergency   |
| `ESC` | Quit              |

---

## How It Works

1. **A\* mode** — robot follows the optimal path each tick
2. **RL mode** — if an obstacle is detected within `LIDAR_RANGE` steps ahead, the DQN model picks the next action (up/down/left/right)
3. **Recovery mode** — if the robot gets stuck (same position 15 frames), it takes random valid steps to escape, then recalculates A\*

---

## Requirements

- Python 3.8+
- pygame
- numpy
- torch
