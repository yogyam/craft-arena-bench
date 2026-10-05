// Top-down replay player. Reads replays/<board>/<pair>.replays.json.gz, gunzips it in the browser, draws both bots per tick.
(function () {
  var params = new URLSearchParams(location.search)
  var board = params.get('board') || '', pair = params.get('pair') || ''
  var status = document.getElementById('status'), canvas = document.getElementById('c'), ctx = canvas.getContext('2d')
  var scrub = document.getElementById('scrub'), playBtn = document.getElementById('play'), timeEl = document.getElementById('time')
  var speedEl = document.getElementById('speed'), matchEl = document.getElementById('match')
  if (!/^[a-z_]+-\d+hz$/.test(board) || !/^[a-z0-9-]+__[a-z0-9-]+$/.test(pair)) { status.textContent = 'No replay named.'; return }
  document.getElementById('title').textContent = pair.replace('__', ' v ') + ' on ' + board

  var doc = null, replay = null, frame = 0, playing = false, last = 0, acc = 0

  fetch('replays/' + board + '/' + pair + '.replays.json.gz').then(function (r) {
    if (!r.ok) throw new Error('HTTP ' + r.status)
    var ds = new DecompressionStream('gzip')
    return new Response(r.body.pipeThrough(ds)).json()
  }).then(function (d) {
    doc = d
    document.getElementById('la').textContent = d.a; document.getElementById('lb').textContent = d.b
    matchEl.innerHTML = ''
    d.replays.forEach(function (rep, i) {
      var o = document.createElement('option'); o.value = i
      var w = rep.outcome.winner === null ? 'draw' : (rep.outcome.winner === 'a' ? rep.meta.a : rep.meta.b) + ' won'
      o.textContent = 'Match ' + (i + 1) + ' (seed ' + rep.meta.seed + '): ' + w + ' by ' + rep.outcome.reason
      matchEl.appendChild(o)
    })
    select(0)
    status.textContent = d.replays.length + ' recorded match' + (d.replays.length === 1 ? '' : 'es') + ' of this pair. ' + d.mode + ', ' + d.tier_hz + ' decisions per second.'
  }).catch(function (e) { status.textContent = 'Could not load the replay: ' + e.message })

  function select (i) {
    replay = doc.replays[i]; frame = 0; playing = false; playBtn.textContent = 'Play'
    scrub.max = replay.frames.length - 1; scrub.value = 0
    document.getElementById('sub').textContent = replay.meta.a + ' (blue) v ' + replay.meta.b + ' (orange), seed ' + replay.meta.seed
    draw()
  }
  matchEl.addEventListener('change', function () { select(Number(matchEl.value)) })
  playBtn.addEventListener('click', function () { playing = !playing; playBtn.textContent = playing ? 'Pause' : 'Play'; last = performance.now(); if (playing) requestAnimationFrame(tick) })
  scrub.addEventListener('input', function () { frame = Number(scrub.value); draw() })

  function tick (now) {
    if (!playing) return
    acc += (now - last) * Number(speedEl.value) / 50; last = now
    while (acc >= 1) { acc -= 1; frame++ }
    if (frame >= replay.frames.length - 1) { frame = replay.frames.length - 1; playing = false; playBtn.textContent = 'Play' }
    scrub.value = frame; draw()
    if (playing) requestAnimationFrame(tick)
  }

  function draw () {
    if (!replay) return
    var a = doc.arena, minX = a.min[0], minZ = a.min[2], maxX = a.max[0] + 1, maxZ = a.max[2] + 1
    var pad = 3, W = canvas.width, H = canvas.height
    var sx = W / (maxX - minX + 2 * pad), sz = H / (maxZ - minZ + 2 * pad), s = Math.min(sx, sz)
    var ox = (W - s * (maxX - minX)) / 2, oz = (H - s * (maxZ - minZ)) / 2
    function X (x) { return ox + (x - minX) * s } function Z (z) { return oz + (z - minZ) * s }
    var dark = matchMedia('(prefers-color-scheme: dark)').matches
    ctx.clearRect(0, 0, W, H)
    ctx.fillStyle = dark ? '#262624' : '#e8e7df'
    ctx.fillRect(X(minX), Z(minZ), (maxX - minX) * s, (maxZ - minZ) * s)
    ctx.strokeStyle = dark ? '#5a5a55' : '#9a998f'; ctx.lineWidth = a.kind === 'walls' ? 4 : 2
    ctx.strokeRect(X(minX), Z(minZ), (maxX - minX) * s, (maxZ - minZ) * s)
    ctx.strokeStyle = dark ? '#333331' : '#d8d7cf'; ctx.lineWidth = 1
    for (var gx = minX; gx <= maxX; gx += 4) { ctx.beginPath(); ctx.moveTo(X(gx), Z(minZ)); ctx.lineTo(X(gx), Z(maxZ)); ctx.stroke() }
    for (var gz = minZ; gz <= maxZ; gz += 4) { ctx.beginPath(); ctx.moveTo(X(minX), Z(gz)); ctx.lineTo(X(maxX), Z(gz)); ctx.stroke() }
    var f = replay.frames[frame]
    var colors = [getComputedStyle(document.documentElement).getPropertyValue('--a').trim(), getComputedStyle(document.documentElement).getPropertyValue('--b').trim()]
    var names = [replay.meta.a, replay.meta.b]
    for (var i = 0; i < 2; i++) {
      var b = f[1 + i], x = X(b[0]), z = Z(b[2]), yaw = b[3] * Math.PI / 180, health = b[5]
      var fallen = b[1] < (doc.arena.min[1] - 1)
      ctx.globalAlpha = fallen ? 0.35 : 1
      ctx.fillStyle = colors[i]; ctx.beginPath(); ctx.arc(x, z, 0.4 * s, 0, 2 * Math.PI); ctx.fill()
      // Facing: Minecraft yaw 0 looks +z, 90 looks -x
      ctx.strokeStyle = colors[i]; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x, z); ctx.lineTo(x - Math.sin(yaw) * 0.9 * s, z + Math.cos(yaw) * 0.9 * s); ctx.stroke()
      // Health bar
      var bw = 1.6 * s, bh = 0.22 * s
      ctx.fillStyle = dark ? '#444' : '#ccc'; ctx.fillRect(x - bw / 2, z - 0.75 * s - bh, bw, bh)
      ctx.fillStyle = health > 10 ? '#2e9e44' : health > 5 ? '#d9a21b' : '#c23b2a'; ctx.fillRect(x - bw / 2, z - 0.75 * s - bh, bw * Math.max(0, Math.min(1, health / 20)), bh)
      ctx.fillStyle = dark ? '#eee' : '#111'; ctx.font = Math.max(11, 0.5 * s) + 'px system-ui'; ctx.textAlign = 'center'
      ctx.fillText(names[i] + ' · ' + f[3][i], x, z + 1.2 * s)
      ctx.globalAlpha = 1
    }
    timeEl.textContent = (f[0] / 20).toFixed(1) + ' s' + (f[0] >= replay.outcome.tick ? ' · ' + (replay.outcome.winner === null ? 'draw' : (replay.outcome.winner === 'a' ? names[0] : names[1]) + ' wins') + ' by ' + replay.outcome.reason : '')
  }
})()
