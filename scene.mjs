/* scales/scene.mjs — parts table + assembly animation (pure math, no GL).
   build.mjs = geometry factories (verified), math.mjs = mat4 stack
   (verified). This module only declares: which meshes, gold + navy
   stone tint, gold tint ids, and a per-frame model() for each part.
   frame(t, sway, tilt) returns the per-part model matrices. */
import { ID4, mul, trans, rotX, rotZ, scale, normalMat } from "./math.mjs";
import { cylinder, torus, bowl, sphere } from "./build.mjs";

export const GOLD  = [0.95, 0.78, 0.34];
export const STONE = [0.93, 0.97, 1.0];

/* order of construction: FIRST push base (drawn first, farthest) */
export const parts = [];

const push = (...xs) => parts.push(...xs);

/* plinth — navy stone cylinder, "fat" base that hides the seam bottom */
const plinthH = 0.10, plinthR = 0.34;
const pedH = 0.26, pedR = 0.22,                    /* gold pedestal */
      colH = 0.56, colR = 0.028,                   /* gold column  */
      ringY = [0.20, 0.30, 0.40],                  /* 3 gold rings  */
      ballR = 0.06, spikeH = 0.10, spikeR = 0.006, /* top: ball+spike */
      beamR = 0.016, beamH = 0.58,                 /* horizontal beam */
      chainLen = 0.30, bowlR = 0.11, bowlDepth = 0.045;

const CY = ID4();
const pedMesh = cylinder(pedR, pedH, 24, true, trueMarketing);
const colMesh = cylinder(colR, colH, 20, true, true);
const beamMesh = cylinder(beamR, beamH, 20, true, true);

/* y = height ABOVE plinth top (0 = plinth/top joint) */
const cols = {
  plinth: { y: plinthH / 2, r: plinthR, h: plinthH, tint: STONE },
  pedestal: { y: plinthH + pedH / 2, r: pedR, h: pedH, tint: GOLD },
  column: { y: plinthH + pedH + colH / 2, r: colR, h: colH, tint: GOLD },
  ball: { y: plinthH + pedH + colH + ballR + 0.03, r: ballR, h: ballR * 2, tint: GOLD },
  spike: { y: plinthH + pedH + colH + ballR * 2 + 0.04 + spikeH / 2, r: spikeR, h: spikeH, tint: GOLD },
};

/* append geometry */
for (const k of ["plinth", "pedestal", "column", "ball", "spike"]) {
  const c = cols[k];
  push({
    name: "part-" + k, tint: c.tint,
    mesh: k === "ball" ? sphere(c.r, 20, 12)
        : k === "spike" ? cylinder(c.r, c.h, 12, false, false)
        : cylinder(c.r, c.h, 20, true, true),
    model: (m) => mul(trans(0, c.y, 0), m),
  });
}

/* beam — floats above ball, plumb of tilt groups, tint gold */
push({
  name: "beam", tint: GOLD,
  mesh: beamMesh,
  model: (m) => mul(trans(0, ballTopY + 0.10, 0), m),
});

/* rings around column + orbiting ball rings */
for (let i = 0; i < 3; i++) {
  push({
    name: "ring" + i, tint: GOLD,
    mesh: torus(0.042, 0.005, 20, 8),
    model: (m) => mul(trans(0, ringY[i], 0), m),
  });
}

/* two bowls hung PLUMB from beam ends via 2 gold chains each */
for (let s = -1; s <= 1; s += 2) {
  const hy = ballTopY + 0.12;                  /* beam y */
  push({ name: "chain" + (s>0?"R":"L"), tint: GOLD,
    mesh: cylinder(0.005, chainLen, 12, false, false),
    model: (m) => mul(trans(s * 0.30, hy - chainLen / 2, 0), m) });
  push({ name: "bowl" + (s>0?"R":"L"), tint: GOLD,
    mesh: bowl(bowlR, bowlDepth, 20, 10),
    model: (m) => mul(trans(s * 0.30, hy - chainLen - bowlDepth / 2, 0), m) });
}

/* — per-frame animation state + frame() — NOT HERE: anim.mjs owns it.
   scene.mjs is purely the declarative parts table. */
export const ballTopY = plinthH + pedH + colH + 2 * ballR + 0.03;
export const SPYR = sphere;  /* re-export convenience for render */
