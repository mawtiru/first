"""Prepare Pages assets and a double-clickable self-contained HTML snapshot."""
import json
from pathlib import Path
from validate import validate
ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'site'

def build():
    data = [json.loads((SITE / f'data/{name}.json').read_text()) for name in ('catalog', 'research', 'updates')]
    validate(data[0], data[1])
    html = (SITE / 'index.html').read_text()
    css = (SITE / 'style.css').read_text()
    lib = (SITE / 'lib.js').read_text().replace('export ', '')
    app = (SITE / 'app.js').read_text().split('\n', 1)[1]
    inline = 'window.SEMI_ATLAS_DATA=' + json.dumps(data, ensure_ascii=False).replace('<', '\\u003c') + ';\n' + lib + '\nconst e=escape;\n' + app
    html = html.replace('<link rel="stylesheet" href="style.css">', '<style>' + css + '</style>')
    html = html.replace('<script type="module" src="app.js"></script>', '<script>\n' + inline + '\n</script>')
    (SITE / 'standalone.html').write_text(html)
    (SITE / '.nojekyll').touch()
    print('Built site/standalone.html; Pages serves site/index.html')

if __name__ == '__main__':
    build()
