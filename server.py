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
  font-family: system-ui, sans-serif;
  background: radial-gradient(circle at top, #1a1f2b, #0b0d12);
  color: #e8e8e8;
  max-width: 1000px;
  margin: auto;
  padding: 24px;
}

/* TITLE like pedal label */
h1 {
  text-align: center;

  font-weight: 700;
  letter-spacing: 4px;
  font-size: 20px;

  margin-bottom: 28px;

  text-transform: uppercase;

  color: #cfd6e6;

  /* hardware panel feel */
  padding: 10px 16px;
  border-radius: 10px;

  background: linear-gradient(180deg, #151a25, #0f121a);
  border: 1px solid #2a3344;

  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.04),
    0 6px 18px rgba(0,0,0,0.4);
}

/* TABS → now look like stomp buttons */
.tab {
  display: inline-block;
  padding: 12px 18px;
  margin-right: 8px;
  border-radius: 10px;
  cursor: pointer;

  background: linear-gradient(#2a3140, #1b2130);
  border: 1px solid #3a455a;

  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.08),
    0 3px 10px rgba(0,0,0,0.4);

  font-size: 13px;
  letter-spacing: 1px;
  text-transform: uppercase;

  transition: 0.15s;
}

.tab:hover {
  transform: translateY(-1px);
  border-color: #6aa6ff;
}

.panel {
  display: none;
  margin-top: 22px;
}

.active {
  display: block;
}

/* DROPZONE → looks like pedal slot / input jack */
.dropzone {
  border-radius: 14px;
  border: 1px dashed #3c465c;
  background: linear-gradient(180deg, #151a25, #10131b);
  padding: 34px;

  text-align: center;
  margin-bottom: 18px;

  color: #9aa6bd;

  box-shadow:
    inset 0 0 0 1px rgba(255,255,255,0.03);
  transition: 0.2s;
}

.dropzone:hover {
  border-color: #6aa6ff;
  color: #d7e6ff;
}

.dropzone.drag {
  border-color: #00ffd5;
  background: linear-gradient(180deg, #162a2a, #0f1717);
  box-shadow: 0 0 20px rgba(0,255,213,0.15);
}

/* EFFECT LIST → pedal slots */
ul {
  list-style: none;
  padding: 0;
}

li {
  display: flex;
  justify-content: space-between;
  align-items: center;

  padding: 12px 14px;
  margin-bottom: 10px;

  background: linear-gradient(180deg, #151a25, #0f121a);
  border: 1px solid #2a3344;
  border-radius: 12px;

  box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
}

/* “active signal” accent */
li:hover {
  border-color: #6aa6ff;
}

/* links = subtle LED */
li a {
  color: #6aa6ff;
  text-decoration: none;
  font-size: 13px;
}

li a:hover {
  text-shadow: 0 0 6px rgba(106,166,255,0.6);
}

/* optional pedal glow effect */
.panel.active {
  animation: fadeIn 0.15s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0.6; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.tag {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 10px;
  display: inline-block;
  box-shadow: 0 0 8px rgba(255,255,255,0.2);
}

/* reverb → blue */
.tag.reverb { background: #4da3ff; box-shadow: 0 0 10px #4da3ff; }

/* delay → purple */
.tag.delay { background: #b26cff; box-shadow: 0 0 10px #b26cff; }

/* distortion → red */
.tag.distortion { background: #ff4d4d; box-shadow: 0 0 10px #ff4d4d; }

/* chorus/mod → green */
.tag.chorus,
.tag.mod { background: #35e6a3; box-shadow: 0 0 10px #35e6a3; }

/* default */
.tag.default { background: #666; }

.filter-btn {
  display: inline-block;
  padding: 6px 10px;
  margin-right: 6px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;

  background: #141823;
  border: 1px solid #2a3344;
  color: #aab6cc;
  transition: 0.15s;
}

.filter-btn:hover {
  border-color: #6aa6ff;
  color: #fff;
}

.filter-btn.active {
  background: #1f2a3d;
  border-color: #6aa6ff;
  color: #fff;
}

.tabs {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-bottom: 20px;
}

.tab.active {
  background: #1f2a3d;
  box-shadow: inset 0 0 0 1px #6aa6ff, 0 0 12px rgba(106,166,255,0.3);
}

</style>
</head>

<body>

<h1>Audio Server</h1>

<div class="tabs">
  <div class="tab active" onclick="showTab('effects', this)">effects</div>
  <div class="tab" onclick="showTab('midi', this)">midi</div>
  <div class="tab" onclick="showTab('conf', this)">conf</div>
</div>

<!-- EFFECTS -->
<div id="effects" class="panel active">
  <div class="dropzone" id="dz-effects">
    Drag & drop LV2 zip here
    <br><br>
  </div>
<div style="margin-bottom:12px">

<span class="filter-btn active" onclick="filterLV2('all', this)">
  <span class="tag default"></span> ALL
</span>

<span class="filter-btn" onclick="filterLV2('reverb', this)">
  <span class="tag reverb"></span> REVERB
</span>

<span class="filter-btn" onclick="filterLV2('delay', this)">
  <span class="tag delay"></span> DELAY
</span>

<span class="filter-btn" onclick="filterLV2('distortion', this)">
  <span class="tag distortion"></span> DIST
</span>

<span class="filter-btn" onclick="filterLV2('chorus', this)">
  <span class="tag chorus"></span> MOD
</span>

<span class="filter-btn" onclick="filterLV2('other', this)">
  <span class="tag default"></span> OTHER
</span>

</div>

    <ul>
    {% for f in effects %}

        <li class="lv2-item"
            data-type="{% if 'reverb' in f %}reverb
            {%- elif 'delay' in f %}delay
            {%- elif 'dist' in f %}distortion
            {%- elif 'chorus' in f or 'mod' in f %}chorus
            {%- else %}other{% endif %}">

        <span class="tag {{ 'reverb' if 'reverb' in f
            else 'delay' if 'delay' in f
            else 'distortion' if 'dist' in f
            else 'chorus' if 'chorus' in f or 'mod' in f
            else 'default' }}"></span>

        <span>{{f}}</span>

        <span style="margin-left:auto">
            <a href="/download/effects/{{f}}">download</a>
        </span>

        </li>

    {% endfor %}
    </ul>
</div>

<!-- MIDI -->
<div id="midi" class="panel">
  <div class="dropzone" id="dz-midi">
    Drag & drop MIDI here
    <br><br>
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
  <div class="dropzone" id="dz-conf">
    Drag & drop config here
    <br><br>
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

function showTab(id, el) {

  // hide panels
  document.querySelectorAll('.panel')
    .forEach(p => p.classList.remove('active'));

  document.getElementById(id).classList.add('active');

  // update tab highlight
  document.querySelectorAll('.tab')
    .forEach(t => t.classList.remove('active'));

  el.classList.add('active');
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

function filterLV2(type, btn) {

  // reset button states
  document.querySelectorAll('.filter-btn')
    .forEach(b => b.classList.remove('active'));

  btn.classList.add('active');

  // filter items
  document.querySelectorAll('.lv2-item')
    .forEach(item => {

      const t = item.dataset.type;

      if (type === 'all' || t === type) {
        item.style.display = 'flex';
      } else {
        item.style.display = 'none';
      }

    });
}
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