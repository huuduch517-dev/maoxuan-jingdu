var CN = "一二三四五六七八九十";
var NOTES = [], TRIES = {}, RENDER = function () {};

/* ──────────────────────────────────────────────────────────
   存储层：Artifact 运行时用服务端 db，其他地方（GitHub Pages、
   本地 file://）退回 localStorage。两种实现对外接口一致。
   ────────────────────────────────────────────────────────── */
var Store = (function () {
  var impl = null, subs = [];
  var LS = 'mx:notes';

  function lsAll() {
    try { return JSON.parse(localStorage.getItem(LS) || '[]'); } catch (e) { return []; }
  }
  function lsSave(arr) {
    try { localStorage.setItem(LS, JSON.stringify(arr)); } catch (e) {}
    fire();
  }
  function fire() {
    var all = impl === 'ls' ? lsAll() : NOTES;
    subs.forEach(function (f) { f(all); });
  }

  var db = null, coll = null;

  return {
    kind: function () { return impl; },

    init: async function () {
      try { db = await claude.use('db'); } catch (e) { db = null; }
      if (db) {
        impl = 'db';
        coll = db.collection('notes');
        coll.where('art', '==', AID).onSnapshot(function (snap) {
          NOTES = snap.docs.map(function (d) {
            var v = d.data() || {};
            return { id: d.id, art: v.art, kind: v.kind || 'note', anchor: v.anchor || 'general',
                     label: v.label || '通篇感想', text: v.text || '',
                     createdAt: v.createdAt, updatedAt: v.updatedAt };
          });
          fire();
        }, function () {});
        return 'db';
      }
      impl = 'ls';
      setTimeout(fire, 0);
      return 'ls';
    },

    watch: function (f) { subs.push(f); },

    add: function (rec) {
      rec.createdAt = rec.updatedAt = Date.now();
      if (impl === 'db') return coll.add(rec);
      var all = lsAll();
      rec.id = 'n' + Date.now() + Math.random().toString(36).slice(2, 6);
      all.push(rec); lsSave(all);
      return Promise.resolve();
    },

    update: function (id, text) {
      if (impl === 'db') return coll.doc(id).update({ text: text, updatedAt: Date.now() });
      var all = lsAll();
      all.forEach(function (n) { if (n.id === id) { n.text = text; n.updatedAt = Date.now(); } });
      lsSave(all);
      return Promise.resolve();
    },

    del: function (id) {
      if (impl === 'db') return coll.doc(id).delete();
      lsSave(lsAll().filter(function (n) { return n.id !== id; }));
      return Promise.resolve();
    },

    dump: function () { return JSON.stringify(impl === 'db' ? NOTES : lsAll(), null, 1); },

    restore: function (txt) {
      var arr = JSON.parse(txt);
      if (!Array.isArray(arr)) throw new Error('格式不对');
      if (impl === 'ls') {
        var have = {}; lsAll().forEach(function (n) { have[n.id] = 1; });
        var merged = lsAll().concat(arr.filter(function (n) { return n.id && !have[n.id]; }));
        lsSave(merged);
        return Promise.resolve(arr.length);
      }
      return Promise.all(arr.filter(function (n) { return n.art === AID; }).map(function (n) {
        return coll.add({ art: AID, kind: n.kind || 'note', anchor: n.anchor, label: n.label,
                          text: n.text, createdAt: n.createdAt || Date.now(), updatedAt: Date.now() });
      })).then(function (r) { return r.length; });
    }
  };
})();

/* ── 阅读进度条 ── */
(function () {
  var bar = document.getElementById('prog');
  if (!bar) return;
  function upd() {
    var h = document.documentElement.scrollHeight - innerHeight;
    bar.style.width = (h > 0 ? Math.min(100, scrollY / h * 100) : 0) + '%';
  }
  addEventListener('scroll', upd, { passive: true });
  addEventListener('resize', upd);
  upd();
})();

/* ── 目录高亮 ── */
(function () {
  var links = [].slice.call(document.querySelectorAll('nav.toc a'));
  if (!links.length) return;
  var secs = links.map(function (a) { return document.getElementById(a.getAttribute('href').slice(1)); });
  function upd() {
    var act = null;
    for (var i = 0; i < secs.length; i++) {
      if (secs[i] && secs[i].getBoundingClientRect().top <= 140) act = links[i];
    }
    links.forEach(function (a) { a.classList.toggle('on', a === act); });
  }
  addEventListener('scroll', upd, { passive: true });
  upd();
})();

/* ── 段号回看 ── */
(function () {
  if (typeof SRC === 'undefined') return;
  var panel = null;
  function close() { if (panel) { panel.remove(); panel = null; } }
  document.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('.pr') : null;
    if (!b) { if (panel && !e.target.closest('#peek')) close(); return; }
    var lab = b.getAttribute('data-p');
    var n = String(CN.indexOf(lab) + 1);
    if (!SRC[n]) return;
    close();
    panel = document.createElement('div');
    panel.id = 'peek';
    var h = document.createElement('div'); h.className = 'ph';
    var t = document.createElement('span'); t.textContent = '原文 第' + lab + '节';
    var x = document.createElement('button'); x.className = 'px'; x.type = 'button'; x.textContent = '关闭';
    x.addEventListener('click', close);
    h.appendChild(t); h.appendChild(x);
    var p = document.createElement('p'); p.className = 'pg'; p.textContent = SRC[n];
    var f = document.createElement('div'); f.className = 'pf';
    var a = document.createElement('a'); a.href = '#p' + n; a.textContent = '跳到原文这一节 ›';
    a.addEventListener('click', function () {
      close();
      var el = document.getElementById('p' + n);
      if (el) { el.classList.add('hl'); setTimeout(function () { el.classList.remove('hl'); }, 2600); }
    });
    f.appendChild(a);
    panel.appendChild(h); panel.appendChild(p); panel.appendChild(f);
    document.body.appendChild(panel);
  });
  addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
})();

/* ── 存疑跳转 ── */
(function () {
  var ds = [].slice.call(document.querySelectorAll('.lv.mine:not(.obs)'));
  var b = document.getElementById('dj');
  if (!b) return;
  if (!ds.length) { b.hidden = true; return; }
  var i = -1;
  b.textContent = '存疑 ' + ds.length;
  b.addEventListener('click', function () {
    ds.forEach(function (d) { d.classList.remove('on'); });
    i = (i + 1) % ds.length;
    ds[i].classList.add('on');
    ds[i].scrollIntoView({ behavior: 'smooth', block: 'center' });
    b.textContent = (i + 1) + ' / ' + ds.length;
  });
})();

function fmt(ts) {
  try {
    var d = new Date(ts);
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  } catch (e) { return ''; }
}

/* ── 编辑器（批注与「先写」共用） ── */
function editor(mount, opts) {
  var old = mount.querySelector('.ted');
  if (old) { old.remove(); return; }
  var ed = document.createElement('div'); ed.className = 'ted';
  var ta = document.createElement('textarea');
  ta.id = 'ta-' + (opts.id || Math.random().toString(36).slice(2));
  ta.placeholder = opts.ph || '写下来就行，不用组织语言。';
  if (opts.value) ta.value = opts.value;
  var r = document.createElement('div'); r.className = 'er';
  var sp = document.createElement('span'); sp.className = 'sp';
  var ok = document.createElement('button'); ok.className = 'bt1'; ok.type = 'button'; ok.textContent = '保存';
  var no = document.createElement('button'); no.className = 'bt2'; no.type = 'button'; no.textContent = '取消';
  no.addEventListener('click', function () { ed.remove(); });
  ok.addEventListener('click', function () {
    var v = ta.value.trim();
    if (!v) { ed.remove(); return; }
    ok.disabled = true; sp.textContent = '保存中…';
    opts.save(v).then(function () { ed.remove(); })
      .catch(function (err) { ok.disabled = false; sp.textContent = '没存上（' + (err && err.code ? err.code : 'error') + '）'; });
  });
  r.appendChild(sp); r.appendChild(no); r.appendChild(ok);
  ed.appendChild(ta); ed.appendChild(r);
  mount.appendChild(ed);
  ta.focus();
}

/* ── 主逻辑 ── */
(function () {
  if (typeof AID === 'undefined') return;
  var stat = document.getElementById('nstat');
  var all = document.getElementById('nall');
  var gen = document.getElementById('ngen');
  var jump = document.getElementById('nj');

  if (jump) jump.addEventListener('click', function () {
    var el = document.getElementById('s7');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  [].slice.call(document.querySelectorAll('.anb')).forEach(function (btn) {
    var box = document.createElement('div');
    box.className = 'nwrap';
    box.setAttribute('data-for', btn.getAttribute('data-a'));
    btn.parentNode.insertBefore(box, btn.nextSibling);
    btn.addEventListener('click', function () {
      editor(box, {
        id: AID + '-' + btn.getAttribute('data-a'),
        save: function (v) {
          return Store.add({ art: AID, kind: 'note', anchor: btn.getAttribute('data-a'),
                             label: btn.getAttribute('data-l'), text: v });
        }
      });
    });
  });

  [].slice.call(document.querySelectorAll('.try .tbtn')).forEach(function (btn) {
    btn.addEventListener('click', function () {
      var box = btn.closest('.try');
      editor(box.querySelector('.tslot'), {
        id: box.getAttribute('data-k'),
        ph: '写一句就行。答不出来也写一句「答不出，卡在哪」。',
        save: function (v) {
          return Store.add({ art: AID, kind: 'try', anchor: box.getAttribute('data-k'),
                             label: box.getAttribute('data-l'), text: v });
        }
      });
    });
  });

  function card(n, showLabel) {
    var c = document.createElement('div'); c.className = 'nc';
    var m = document.createElement('div'); m.className = 'nm';
    var lab = document.createElement('span');
    lab.textContent = (showLabel ? n.label + ' ／ ' : '') + fmt(n.updatedAt || n.createdAt);
    var sp = document.createElement('span'); sp.className = 'sp';
    var e = document.createElement('button'); e.type = 'button'; e.textContent = '改';
    var d = document.createElement('button'); d.type = 'button'; d.textContent = '删';
    m.appendChild(lab); m.appendChild(sp); m.appendChild(e); m.appendChild(d);
    var t = document.createElement('div'); t.className = 'tx'; t.textContent = n.text;
    c.appendChild(m); c.appendChild(t);
    e.addEventListener('click', function () {
      editor(c, { id: n.id, value: n.text, save: function (v) { return Store.update(n.id, v); } });
    });
    d.addEventListener('click', function () {
      if (!confirm('删掉这条？')) return;
      Store.del(n.id);
    });
    return c;
  }

  function paintTries() {
    [].slice.call(document.querySelectorAll('.try')).forEach(function (box) {
      var key = box.getAttribute('data-k');
      var slot = box.querySelector('.tslot');
      var btn = box.querySelector('.tbtn');
      var rec = TRIES[key];
      slot.textContent = '';
      if (rec) {
        var c = document.createElement('div'); c.className = 'mine-ans';
        var m = document.createElement('div'); m.className = 'ml';
        var lab = document.createElement('span'); lab.textContent = '你写的 ／ ' + fmt(rec.updatedAt || rec.createdAt);
        var sp = document.createElement('span'); sp.className = 'sp';
        var e = document.createElement('button'); e.type = 'button'; e.textContent = '改';
        m.appendChild(lab); m.appendChild(sp); m.appendChild(e);
        var tx = document.createElement('div'); tx.textContent = rec.text;
        c.appendChild(m); c.appendChild(tx);
        slot.appendChild(c);
        btn.hidden = true;
        e.addEventListener('click', function () {
          editor(slot, { id: key, value: rec.text, save: function (v) { return Store.update(rec.id, v); } });
        });
      } else {
        btn.hidden = false;
      }
    });
  }

  RENDER = function (list) {
    NOTES = list.filter(function (n) { return !n.art || n.art === AID; })
                .sort(function (x, y) { return (x.createdAt || 0) - (y.createdAt || 0); });
    [].slice.call(document.querySelectorAll('.nwrap[data-for]')).forEach(function (b) { b.textContent = ''; });
    if (all) all.textContent = '';
    var notes = NOTES.filter(function (n) { return n.kind !== 'try'; });
    notes.forEach(function (n) {
      var inl = document.querySelector('.nwrap[data-for="' + n.anchor + '"]');
      if (inl) inl.appendChild(card(n, false));
      if (all) all.appendChild(card(n, true));
    });
    if (all && !notes.length) {
      var e = document.createElement('p');
      e.className = 'dim';
      e.textContent = '还没有批注。原文每一节下面、每一节解读的标题右边，都有「写点什么」。';
      all.appendChild(e);
    }
    if (jump) jump.textContent = notes.length ? '批注 ' + notes.length : '批注';
    TRIES = {};
    NOTES.filter(function (n) { return n.kind === 'try'; }).forEach(function (n) { TRIES[n.anchor] = n; });
    paintTries();
  };

  Store.watch(RENDER);

  Store.init().then(function (kind) {
    if (stat) {
      stat.textContent = kind === 'db'
        ? '写下的东西存在服务端，换设备也在。'
        : '写下的东西存在这台设备的浏览器里。换设备看不到——用下面的「导出」把它们带走。';
    }
    if (!gen) return;

    var b = document.createElement('button');
    b.className = 'anb'; b.type = 'button'; b.textContent = '写一条通篇的';
    var g2 = document.createElement('div'); g2.className = 'nwrap'; g2.setAttribute('data-for', 'general');
    b.addEventListener('click', function () {
      editor(g2, { id: AID + '-general',
        save: function (v) {
          return Store.add({ art: AID, kind: 'note', anchor: 'general', label: '通篇感想', text: v });
        } });
    });
    gen.appendChild(b); gen.appendChild(g2);

    // 导出 / 导入
    var io = document.createElement('div'); io.className = 'ioz';
    var eb = document.createElement('button'); eb.className = 'anb'; eb.type = 'button'; eb.textContent = '导出';
    var ib = document.createElement('button'); ib.className = 'anb'; ib.type = 'button'; ib.textContent = '导入';
    var pane = document.createElement('div');
    io.appendChild(eb); io.appendChild(ib); io.appendChild(pane);
    gen.appendChild(io);
    eb.addEventListener('click', function () {
      pane.textContent = '';
      var ta = document.createElement('textarea'); ta.className = 'iot'; ta.readOnly = true;
      ta.value = Store.dump();
      var tip = document.createElement('p'); tip.className = 'dim';
      tip.textContent = '全选复制，存到你习惯的地方。换设备时用「导入」贴回来。';
      pane.appendChild(tip); pane.appendChild(ta); ta.select();
    });
    ib.addEventListener('click', function () {
      pane.textContent = '';
      var ta = document.createElement('textarea'); ta.className = 'iot';
      ta.placeholder = '把导出的内容贴在这里，然后点下面的「合并进来」。';
      var go = document.createElement('button'); go.className = 'bt1'; go.type = 'button'; go.textContent = '合并进来';
      var msg = document.createElement('span'); msg.className = 'dim';
      go.addEventListener('click', function () {
        try {
          Store.restore(ta.value).then(function (n) { msg.textContent = '合并了 ' + n + ' 条。'; });
        } catch (e) { msg.textContent = '贴进来的内容不是导出的格式。'; }
      });
      pane.appendChild(ta); pane.appendChild(go); pane.appendChild(msg);
    });
  });
})();
