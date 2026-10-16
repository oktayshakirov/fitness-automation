"""Rep tempo: one loop = start hold, out (s 0 -> 1), peak hold, back (s 1 -> 0), end hold.
s = 0 is the start position (standing for a squat, arms down for a curl), s = 1 the
far end of the movement. Frame 1 == last frame, so the clip loops."""

# the plan's squat-style names map onto the generic ones
ALIASES = {"hold_top": "start", "down": "out", "hold_bottom": "peak", "up": "back", "hold_end": "end",
           "hold_start": "start", "work": "out", "hold_peak": "peak", "return": "back"}
ORDER = ("start", "out", "peak", "back", "end")


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def normalize(tempo):
    t = {ALIASES.get(k, k): int(v) for k, v in tempo.items()}
    return {k: t.get(k, 0) for k in ORDER}


class Tempo:
    def __init__(self, tempo):
        self.t = normalize(tempo)
        self.n = sum(self.t.values())
        # last frame of each segment
        acc, self.ends = 0, {}
        for k in ORDER:
            acc += self.t[k]
            self.ends[k] = acc

    def s(self, f):
        """Phase 0..1 at frame f (1-based)."""
        e = self.ends
        if f <= e["start"]:
            return 0.0
        if f <= e["out"]:
            return smooth((f - e["start"]) / self.t["out"])
        if f <= e["peak"]:
            return 1.0
        if f <= e["back"]:
            return 1.0 - smooth((f - e["peak"]) / self.t["back"])
        return 0.0

    def key_frames(self):
        """Default contact-sheet frames: start, mid-out, peak, mid-back, near the end."""
        e = self.ends
        return [1, e["start"] + self.t["out"] // 2, e["out"] + max(1, self.t["peak"] // 2),
                e["peak"] + self.t["back"] // 2, e["back"]]
