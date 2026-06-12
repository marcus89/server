from pathlib import Path
from functools import wraps
import shutil
import zipfile

from flask import (
    Flask, request, jsonify,
    render_template_string,
    send_from_directory, abort,
    Response
)

from werkzeug.utils import secure_filename

app = Flask(__name__)

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "uploads"

EFFECTS = UPLOADS / "effects"
MIDI = UPLOADS / "midi"
CONF = UPLOADS / "conf"

for p in [EFFECTS, MIDI, CONF]:
    p.mkdir(parents=True, exist_ok=True)

# ---------------- AUTH ----------------

USER, PASS = "admin", "secret"

def requires_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.authorization

        if not auth or auth.username != USER or auth.password != PASS:
            return Response(
                "Auth required",
                401,
                {"WWW-Authenticate": 'Basic realm="Login Required"'}
            )

        return f(*args, **kwargs)

    return wrapper

# ---------------- UI ----------------

HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Server</title>

<style>
body {
  font-family: sans-serif;
  max-width: 1000px;
  margin: auto;
  padding: 20px;
}

.tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.tab {
  padding: 10px 15px;
  border: 1px solid #ccc;
  cursor: pointer;
  user-select: none;
}

.panel {
  display: none;
}

.panel.active {
  display: block;
}

.dropzone {
  border: 2px dashed #999;
  padding: 40px;
  text-align: center;
  margin-bottom: 20px;
  transition: 0.2s;
}

.dropzone.drag {
  background: #eee;
  border-color: #333;
}

ul {
  list-style: none;
  padding-left: 0;
}

li {
  padding: 6px 0;
  display: flex;
  justify-content: space-between;
}
</style>
</head>

<body>

<h1>Audio Server</h1>

<div class="tabs">
  <div class="tab" onclick="show('effects')">effects</div>
  <div class="tab" onclick="show('midi')">midi</div>
  <div class="tab" onclick="show('conf')">conf</div>
</div>

<!-- EFFECTS -->
<div id="effects" class="panel active">

  <h2>effects (.lv2)</h2>

  <div class="dropzone" id="dz-effects">
    Drag & drop LV2 zip here
    <br><br>
    <input type="file" id="file-effects">
  </div>

  <ul>
    {% for f in effects %}
      <li>
        <span>{{f}}</span>
        <a href="/download/effects/{{f}}">download</a>
      </li>
    {% endfor %}
  </ul>
</div>

<!-- MIDI -->
<div id="midi" class="panel">

  <h2>midi</h2>

  <div class="dropzone" id="dz-midi">
    Drag & drop MIDI here
    <br><br>
    <input type="file" id="file-midi">
  </div>

  <ul>
    {% for f in midi %}
      <li>
        <span>{{f}}</span>
        <a href="/download/midi/{{f}}">download</a>
      </li>
    {% endfor %}
  </ul>
</div>

<!-- CONF -->
<div id="conf" class="panel">

  <h2>conf</h2>

  <div class="dropzone" id="dz-conf">
    Drag & drop config here
    <br><br>
    <input type="file" id="file-conf">
  </div>

  <ul>
    {% for f in conf %}
      <li>
        <span>{{f}}</span>
        <a href="/download/conf/{{f}}">download</a>
      </li>
    {% endfor %}
  </ul>
</div>

<script>

function show(id) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById(id).classList.add('active');
}

// ---------------- DRAG & DROP ----------------

function setupDrop(zoneId, inputId, uploadUrl) {

  const zone = document.getElementById(zoneId);
  const input = document.getElementById(inputId);

  zone.addEventListener('dragover', e => {
    e.preventDefault();
    zone.classList.add('drag');
  });

  zone.addEventListener('dragleave', () => {
    zone.classList.remove('drag');
  });

  zone.addEventListener('drop', async e => {
    e.preventDefault();
    zone.classList.remove('drag');
    await uploadFiles(e.dataTransfer.files, uploadUrl);
    location.reload();
  });

  input.addEventListener('change', async e => {
    await uploadFiles(e.target.files, uploadUrl);
    location.reload();
  });
}

async function uploadFiles(files, url) {

  for (const f of files) {
    const form = new FormData();
    form.append("file", f);

    await fetch(url, {
      method: "POST",
      body: form
    });
  }
}

// init
setupDrop("dz-effects", "file-effects", "/api/upload/effects");
setupDrop("dz-midi", "file-midi", "/api/upload/midi");
setupDrop("dz-conf", "file-conf", "/api/upload/conf");

</script>

</body>
</html>
"""

# ---------------- ROUTES ----------------

@app.route("/")
@requires_auth
def index():
    effects = [
        p.name for p in EFFECTS.iterdir()
        if p.is_dir() and p.name.endswith(".lv2")
    ]
    effects.sort()
    midi = [f.name for f in MIDI.iterdir() if f.is_file()]
    conf = [f.name for f in CONF.iterdir() if f.is_file()]

    return render_template_string(
        HTML,
        effects=effects,
        midi=midi,
        conf=conf
    )

# ---------- LV2 upload ----------

@app.route("/api/upload/effects", methods=["POST"])
@requires_auth
def upload_lv2():
    f = request.files["file"]
    name = secure_filename(f.filename)

    if not name.endswith(".zip"):
        return {"error": "zip only"}, 400

    tmp = EFFECTS / name
    f.save(tmp)

    target = EFFECTS / name.replace(".zip", ".lv2")

    with zipfile.ZipFile(tmp) as z:
        z.extractall(target)

    tmp.unlink()
    return {"ok": True}

# ---------- MIDI / CONF ----------

@app.route("/api/upload/<folder>", methods=["POST"])
@requires_auth
def upload(folder):
    target = MIDI if folder == "midi" else CONF if folder == "conf" else None
    if not target:
        abort(404)

    f = request.files["file"]
    name = secure_filename(f.filename)
    f.save(target / name)

    return {"ok": True}

# ---------- DOWNLOAD ----------

@app.route("/download/<folder>/<name>")
@requires_auth
def download(folder, name):
    if folder == "midi":
        return send_from_directory(MIDI, name, as_attachment=True)
    if folder == "conf":
        return send_from_directory(CONF, name, as_attachment=True)
    abort(404)

@app.route("/download/effects/<name>")
@requires_auth
def download_lv2(name):
    path = EFFECTS / name
    if not path.exists():
        abort(404)

    zip_path = EFFECTS / f"{name}.zip"
    shutil.make_archive(str(zip_path).replace(".zip",""), "zip", path)

    return send_from_directory(EFFECTS, zip_path.name, as_attachment=True)

# ---------- DELETE LV2 ----------

@app.route("/api/delete/effects/<name>")
@requires_auth
def delete_lv2(name):
    path = EFFECTS / name
    if path.exists():
        shutil.rmtree(path)
    return {"deleted": True}

# ---------- HTTPS ----------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8002,
    )