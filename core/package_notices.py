"""Copy the checked source notices into the distributable media bundle."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def package_notices():
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    anatomy = (ROOT / 'bodymap/LICENSE.md').read_text()
    data = (ROOT / 'catalog/sources/LICENSE.free-exercise-db').read_text()
    (dist / 'ATTRIBUTION.md').write_text(anatomy + '\n## Exercise data\n\n'
        + 'free-exercise-db by yuhonas and contributors: https://github.com/yuhonas/free-exercise-db\n'
        + 'Source muscle/equipment classification: Unlicense. Original coaching text is provided as a draft for review.\n\n'
        + '### Unlicense\n\n' + data)

if __name__ == '__main__':
    package_notices()
