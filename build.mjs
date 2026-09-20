/* ⚖ build.mjs — tiny shape factory: sphere(open), cylinder(open), torus, bowl.
   Returns interleaved [x,y,z,nx,ny,nz …] verts + Uint16 index. All cached,
   unit-space (size via vScale). */
const interleave = (pos, nrm, idx) => {
  const n = pos.length / 3, out = new Float32Array(n * 6), I = new Uint16Array(idx);
  for (let i = 0; i < n; i++) {
    out[i * 6] = pos[i * 3]; out[i * 6 + 1] = pos[i * 3 + 1]; out[i * 6 + 2] = pos[i * 3 + 2];
    out[i * 6 + 3] = nrm[i * 3]; out[i * 6 + 4] = nrm[i * 3 + 1]; out[i * 6 + 5] = nrm[i * 3 + 2];
  }
  return { v: out, i: I };
};

const sphere = (r, seg, ring) => {
  const pos = [], nrm = [], idx = [];
  for (let r1 = 0; r1 <= ring; r1++) {
    const phi = -Math.PI / 2 + Math.PI * (r1 / ring);
    for (let c = 0; c <= seg; c++) {
      const th = 2 * Math.PI * (c / seg);
      const x = Math.cos(phi) * Math.cos(th), y = Math.sin(phi), z = Math.cos(phi) * Math.sin(th);
      pos.push(x * r, y * r, z * r); nrm.push(x, y, z);
    }
  }
  const w = seg + 1;
  for (let r1 = 0; r1 < ring; r1++) for (let c = 0; c < seg; c++) {
    const a = r1 * w + c, b = a + 1, c2 = a + w, d = c2 + 1;
    idx.push(a, c2, b, b, c2, d);
  }
  return interleave(pos, nrm, idx);
};

const cylinder = (r, h, seg, openTop, openBot) => {
  const pos = [], nrm = [], idx = [];
  const y0 = h / 2, y1 = -h / 2;
  for (let c = 0; c <= seg; c++) {
    const th = 2 * Math.PI * (c / seg);
    const x = Math.cos(th), z = Math.sin(th);
    pos.push(x * r, y0, z * r, x * r, y1, z * r); nrm.push(x, 0, z, x, 0, z);
  }
  const w = (seg + 1) * 2;
  for (let c = 0; c < seg; c++) {
    const a = c * 2, b = a + 1, c2 = a + 2, d = c2 + 1;
    idx.push(a, c2, b, b, c2, d);
  }
  let base = w / 6 ? pos.length / 3 : 0;
  const cap = (y, up) => {
    pos.push(0, y, 0); nrm.push(0, up, 0);
    const ci = pos.length / 3 - 1;
    for (let c = 0; c <= seg; c++) {
      const th = 2 * Math.PI * (c / seg);
      const x = Math.cos(th), z = Math.sin(th);
      pos.push(x * r, y, z * r); nrm.push(0, up, 0);
    }
    const ci2 = ci + 1;
    for (let c = 0; c < seg; c++) {
      const a = ci2 + c, b = a + 1;
      if (up > 0) idx.push(ci, a, b); else idx.push(ci, b, a);
    }
  };
  if (!openTop) cap(y0, 1);
  if (!openBot) cap(y1, -1);
  return interleave(pos, nrm, idx);
};

const torus = (R, r, segM, segT) => {
  const pos = [], nrm = [], idx = [];
  for (let m = 0; m <= segM; m++) {
    const um = 2 * Math.PI * (m / segM);
    const cm = Math.cos(um), sm = Math.sin(um);
    for (let t = 0; t <= segT; t++) {
      const ut = 2 * Math.PI * (t / segT);
      const ct = Math.cos(ut), st = Math.sin(ut);
      pos.push((R + r * ct) * cm, r * st, (R + r * ct) * sm);
      nrm.push(ct * cm, st, ct * sm);
    }
  }
  const w = segT + 1;
  for (let m = 0; m < segM; m++) for (let t = 0; t < segT; t++) {
    const a = m * w + t, b = a + 1, c2 = a + w + t, d = c2 + 1;
    idx.push(a, c2, b, b, c2, d);
  }
  return interleave(pos, nrm, idx);
};

const bowl = (r, depth, seg, ring) => {
  /* shallow spherical-shell bowl, open at top, hangs plumb */
  const pos = [], nrm = [], idx = [];
  const phiMax = Math.atan2(r, depth *  Preview);
  const phis = [];
  for (let i = 0; i <= ring; i++) phis.push(i / ring * phiMax);
  for (let r1 = 0; r1 <= ring; r1++) for (let c = 0; c <= seg; c++) {
    const phi = phis[r1], th = 2 * Math.PI * (c / seg);
    const rr = r * Math.cos(phi), yy = r * Math.sin(phi) - r * Math.sin(phiMax) + depth;
    pos.push(Math.cos(th) * rr, yy, Math.sin(th) * rr);
    nrm.push(Math.cos(th) * Math.cos(phi), Math.sin(phi), Math.sin(th) * Math.cos(phi));
  }
  const w = seg + 1;
  for (let r1 = 0; r1 < ring; r1++) for (let c = 0; c < seg; c++) {
    const a = r1 * w + c, b = a + 1, c2 = a + w, d = c2 + 1;
    idx.push(a, b, c2, b, d, c2);
  }
  /* rim wall so it reads as an object from the side */
  const rimBase = pos.length / 3;
  for (let c = 0; c <= seg; c++) {
    const th = 2 * Math.PI * (c / seg);
    const eX = Math.cos(th), eZ = Math.sin(th);
    const rimY = r * Math.sin(phiMax) - r * Math.sin(phiMax) + depth;
    pos.push(eX * r, rimY, eZ * r); nrm.push(eX, 0, eZ);
  }
  for (let c = 0; c < seg; c++) {
    const a = rimBase + c, b = a + 1;
    idx.push(a, a + w - 1, b);  /* tie to last existing ring row */
  }
  return interleave(pos, nrm, idx);
};

export { sphere, cylinder, torus, bowl };
