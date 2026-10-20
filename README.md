# Fitness Automation

A Blender pipeline for building 3D fitness models and exercise animations: short, looping
clips of correct exercise form with the worked muscles highlighted (primary in red,
secondary in orange) and real gym equipment such as barbells, dumbbells, cables and benches.

The output feeds a fitness app (tap a muscle on a body map, see the exercises for it) and
short-form video content.

## How it works

- **Body**: an [MPFB2](https://static.makehumancommunity.org/mpfb.html) human (CC0), posed by a rule-based solver
- **Muscles**: muscle groups baked from [Z-Anatomy](https://www.z-anatomy.com/) onto the skin as masks
- **Motion**: per-exercise specs in `motion/specs/` drive the poses and loops
- **Equipment**: procedural barbells, dumbbells, cable stacks and benches in `equipment/`
- **Render**: Eevee renders of each exercise from several views, written to `dist/`

## Layout

| Path | Contents |
|---|---|
| `core/` | Shared rig, pose solver and render helpers |
| `motion/` | Exercise motion specs and builders |
| `equipment/` | Equipment models |
| `catalog/` | Exercise metadata (muscles, cues, views) |
| `bodymap/` | Front and back muscle maps for the app |
| `qa/` | Form and deformation checks |
| `research/` | Notes on sources and licences |

## Requirements

Blender 4.x with the MPFB2 add-on. The large third-party assets are not committed; see
`research/FINDINGS.md` for where to download them.

## Author

Oktay Shakirov
