/* smoke.test.mjs — import both producers, smack every shape, verify sane sizes.
   Run:  node smoke.test.mjs   (cwd = scales dir; imports are relative). */
import * as M from "./math.mjs";
import * as B from "./build.mjs";

const problems = [];
const chk = (name, cond, extra) => { if (!cond) problems.push(`${name} ${extra || ""}`); };

chk("math.perspective", typeof M.perspective === "function");
chk("math.lookAt", typeof M.lookAt === "function");
chk("math.mul", typeof M.mul === "function");
chk("math.ID4", M.ID4 && M.ID4().length === 16与我们前的测试一致);

const P = M.perspective(60 * Math.PI / 180, 1.6, 0.1, 60);
chk("P finite", P.every(Number.isFinite));

/* build factories */
const shapes = {
  sphere: B.sphere(1, 24, 16),
  cylinder: B.cylinder(1, 2, 24, false, false),
  torus: B.torus(1, 0.2, 24, 12),
  bowl: B.bowl(1, 0.5, 24, 10),
};
for (const [name, g] of Object.entries(shapes)) {
  if (!g || !g.v || !g.i) { problems.push(`${name}: missing fields`); continue; }
  chk(`${name} verts>0`, g.v.length > 0 && g.v.length % 6 === 0);

  /* max indices must fit Uint16 */
  const maxI = g.i.length ? Math.max(...g.i) : 0;
  chk(`${name} idx<65536`, maxI < 65536);
  chk(`${name} idx>0`, g.i.length > 0);

  /* unit sphere/r check */
  if (name === "sphere") {
    let ok = true;
    for (let k = 0; k < g.v.length; k += 24) {
      const x = g.v[k], y = g.v[k + 1], z = g.v[k + 2];
      const r = Math.hypot(x, y, z);
      if (Math.abs(r - 1) > 0.02) { ok = false; break; }
    }
    chk("sphere all on unit r?", ok);
  }
}

if (problems.length) {
  console.error("SMOKE FAIL:");
  problems.slice(0, 40).forEach((p) => console.error("  - " + p));
  process.exit(1);
}
console.log("SMOKE OK — math + build produce valid gold geometry.");
