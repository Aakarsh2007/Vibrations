"""Check: two recordings at different fps disambiguate an aliased frequency.
Also check: detection of interpolated ('fake') slow-mo frames."""
import numpy as np

def alias(f, fs):
    r = f % fs
    return min(r, fs - r)

def resolve(obs, fmax=500, step=0.05, tol=0.3):
    """obs: list of (observed_freq, fs). Return candidate true freqs consistent with all."""
    cands = np.arange(1, fmax, step)
    ok = [f for f in cands if all(abs(alias(f, fs) - fo) < tol for fo, fs in obs)]
    # cluster
    out = []
    for f in ok:
        if not out or f - out[-1][-1] > 1: out.append([f])
        else: out[-1].append(f)
    return [round(float(np.mean(c)), 2) for c in out]

for true in [24.3, 49.5, 99.0, 148.0, 197.5]:
    o240, o120 = alias(true, 240), alias(true, 120)
    o240_960 = alias(true, 960)
    print(f"true {true:6.1f} Hz | seen@240={o240:6.1f} seen@120={o120:6.1f} | candidates(240 only)={resolve([(o240,240)], 300)[:6]} | (240+120)={resolve([(o240,240),(o120,120)], 300)}")

# interpolated-frame detection: in real 240fps every frame has new information; in interpolated video,
# frame k (synthesised) ~= mean(frame k-1, frame k+1) much more tightly than for real frames.
rng = np.random.default_rng(1)
def make(n, interp):
    base = np.cumsum(rng.normal(0, 1, (n, 64, 64)), 0)  # evolving texture
    if interp:  # only every 4th frame real (60 fps), others linear blends
        real = base[::4]
        out = []
        for a, b in zip(real[:-1], real[1:]):
            for k in range(4): out.append(a + (b - a) * k / 4)
        base = np.array(out)
    return base + rng.normal(0, 0.5, base.shape)
for interp in [False, True]:
    v = make(400, interp)
    r = np.abs(v[1:-1] - 0.5 * (v[:-2] + v[2:])).mean((1, 2))
    d = np.abs(v[1:] - v[:-1]).mean((1, 2))[:-1]
    ratio = r / d
    # periodicity of residual reveals the interpolation cadence
    spec = np.abs(np.fft.rfft(ratio - ratio.mean()))
    print(f"interp={interp}: median residual/diff ratio={np.median(ratio):.3f}  cadence peak bin={np.argmax(spec[1:])+1} of {len(spec)}")
