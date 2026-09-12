import { createDocumentTexture, createPaperMesh, PAPER_FRAGMENT_SHADER, PAPER_VERTEX_SHADER } from './paperModel';

export interface SceneHandle {
  setLight(value: number): void;
  setRunning(running: boolean): void;
  destroy(): void;
}

interface SceneOptions {
  light: boolean;
  reducedMotion: boolean;
}

// Seconds a sheet takes to cross its whole trajectory at one second per second of scene
// time. The descent is even over the cycle — no sheet brakes on the way down and settles
// into a hover — so the snowfall never stops falling however long the page stays open.
// Each sheet scales this by its own speed, and the spread of speeds is what breaks up the
// fall into something disorderly rather than a marching grid.
const FALL_DURATION = 26;
// On load the sky is empty: sheets enter one after another over these seconds.
const ENTRY_WINDOW = 5;
// The fall arrives in a hurry: the scene clock starts this many times faster than real
// time, so the sheets come down quickly and the sky is full within a few seconds instead
// of filling for half a minute. Then the rush bleeds off and the snowfall calms to its
// steady pace. It happens once, when the scene starts, and never comes back.
const RUSH_RATE = 4.5;
// How fast the rush bleeds off. After roughly three of these seconds the clock is back to
// one second per second, gradually enough to read as settling rather than braking.
const RUSH_SETTLE = 3.4;

function compile(gl: WebGL2RenderingContext, type: number, source: string): WebGLShader | null {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    if (import.meta.env.DEV) console.warn('[documents] shader:', gl.getShaderInfoLog(shader));
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

/** Shared paper geometry, rendered at different depths without a 3D dependency. */
export function startScene(canvas: HTMLCanvasElement, options: SceneOptions): SceneHandle | null {
  const gl = canvas.getContext('webgl2', {
    alpha: true, antialias: true, depth: true, powerPreference: 'low-power',
  });
  if (!gl) return null;

  const vertex = compile(gl, gl.VERTEX_SHADER, PAPER_VERTEX_SHADER);
  const fragment = compile(gl, gl.FRAGMENT_SHADER, PAPER_FRAGMENT_SHADER);
  const program = gl.createProgram();
  if (!vertex || !fragment || !program) {
    if (vertex) gl.deleteShader(vertex);
    if (fragment) gl.deleteShader(fragment);
    if (program) gl.deleteProgram(program);
    return null;
  }
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    if (import.meta.env.DEV) console.warn('[documents] program:', gl.getProgramInfoLog(program));
    gl.deleteProgram(program);
    return null;
  }

  let documentTexture: HTMLCanvasElement;
  try {
    documentTexture = createDocumentTexture();
  } catch {
    gl.deleteProgram(program);
    return null;
  }

  const vao = gl.createVertexArray();
  const vertices = gl.createBuffer();
  const indices = gl.createBuffer();
  const texture = gl.createTexture();
  if (!vao || !vertices || !indices || !texture) {
    gl.deleteVertexArray(vao);
    gl.deleteBuffer(vertices);
    gl.deleteBuffer(indices);
    gl.deleteTexture(texture);
    gl.deleteProgram(program);
    return null;
  }

  const mesh = createPaperMesh();
  gl.bindVertexArray(vao);
  gl.bindBuffer(gl.ARRAY_BUFFER, vertices);
  gl.bufferData(gl.ARRAY_BUFFER, mesh.vertices, gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 20, 0);
  gl.enableVertexAttribArray(1);
  gl.vertexAttribPointer(1, 2, gl.FLOAT, false, 20, 12);
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indices);
  gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, mesh.indices, gl.STATIC_DRAW);
  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, documentTexture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.generateMipmap(gl.TEXTURE_2D);
  // Keep printed text clean when a sheet turns at an oblique angle.
  const anisotropy = gl.getExtension('EXT_texture_filter_anisotropic');
  if (anisotropy) {
    gl.texParameterf(gl.TEXTURE_2D, anisotropy.TEXTURE_MAX_ANISOTROPY_EXT,
      Math.min(4, gl.getParameter(anisotropy.MAX_TEXTURE_MAX_ANISOTROPY_EXT) as number));
  }
  gl.useProgram(program);
  gl.uniform1i(gl.getUniformLocation(program, 'uDocuments'), 0);

  const uniforms = Object.fromEntries([
    'uAspect', 'uTime', 'uLight', 'uPosition', 'uRotation', 'uScale', 'uVariant', 'uSeed',
  ].map(name => [name, gl.getUniformLocation(program, name)]));

  // Stable distribution prevents theme changes and React remounts from shuffling the scene.
  let seed = 1709;
  const random = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  const papers = Array.from({ length: 48 }, (_, index) => ({
    x: (random() * 2 - 1) * 0.98,
    z: -7 + random() * 9,
    // The second the sheet is released. Until then it waits above the top edge.
    entry: index / 48 * ENTRY_WINDOW + random() * 1.6,
    scale: 0.7 + random() * 0.95,
    // A near threefold spread: quick sheets overtake slow ones within the first cycle and
    // the ranks they entered in are gone for good.
    speed: 0.6 + random() * 1.05,
    turn: random() * Math.PI * 2,
    tilt: (random() - 0.5) * 1.1,
    roll: (random() - 0.5) * 1.4,
    // Two swings at unrelated frequencies: a wide drift with a faster wobble riding on it,
    // which never repeats the same path twice.
    sway: 0.22 + random() * 0.5,
    swayRate: 0.16 + random() * 0.3,
    swayFast: 0.05 + random() * 0.14,
    swayFastRate: 0.55 + random() * 0.7,
    // Air caught under the sheet: it hangs, then drops a little quicker.
    bob: 0.05 + random() * 0.13,
    bobRate: 0.3 + random() * 0.5,
    // Signed, so roughly half the sheets turn against the other half.
    spin: (random() < 0.5 ? -1 : 1) * (0.1 + random() * 0.34),
    pitch: 0.3 + random() * 0.42,
    pitchRate: 0.2 + random() * 0.34,
    rollAmp: 0.3 + random() * 0.45,
    rollRate: 0.14 + random() * 0.3,
    variant: index % 3,
    seed: random() * 100,
    mobile: index % 2 === 0,
  })).sort((a, b) => a.z - b.z);

  // Each paper is opaque; the complete canvas is softened by the page background.
  gl.disable(gl.BLEND);
  gl.enable(gl.DEPTH_TEST);
  gl.depthMask(true);
  gl.disable(gl.CULL_FACE);
  gl.clearColor(0, 0, 0, 0);

  let light = Number(options.light);
  let targetLight = light;
  let running = false;
  let destroyed = false;
  let frame = 0;
  let time = 0;
  // Real seconds the scene has been running, which is what the opening rush decays over.
  // Pausing the scene pauses this too, so a tab returning from the background picks the
  // fall up where it left it rather than restarting the rush.
  let elapsed = 0;
  let lastTime = 0;
  let width = 1;
  let height = 1;
  const reduced = options.reducedMotion;

  function draw() {
    if (destroyed || gl!.isContextLost()) return;
    gl!.clear(gl!.COLOR_BUFFER_BIT | gl!.DEPTH_BUFFER_BIT);
    gl!.useProgram(program);
    gl!.bindVertexArray(vao);
    gl!.activeTexture(gl!.TEXTURE0);
    gl!.bindTexture(gl!.TEXTURE_2D, texture);
    const aspect = width / height;
    const mobile = width < 720;
    gl!.uniform1f(uniforms.uAspect, aspect);
    gl!.uniform1f(uniforms.uTime, time);
    gl!.uniform1f(uniforms.uLight, light);

    for (const paper of papers) {
      if (mobile && !paper.mobile) continue;
      // Released at its own moment, then falling for as long as the scene runs.
      const progress = (time - paper.entry) * paper.speed;
      // Before its entry moment the sheet has not started falling yet.
      if (progress < 0) continue;
      const age = progress % FALL_DURATION;
      const distance = 12 - paper.z;
      const scale = paper.scale * (mobile ? 0.68 : 1);
      // Recycle outside the viewport, with room for the entire rotated sheet and for the
      // bob below — carrying the bob here keeps the bottom of the trajectory off screen.
      const extentY = distance * 0.52 + scale * 1.1 + paper.bob;
      // Even ground covered per second, so the descent reads the same in the first second
      // and the fifth minute, with a slow bob riding on top of it.
      const y = extentY * (1 - 2 * (age / FALL_DURATION))
        + Math.sin(time * paper.bobRate + paper.seed) * paper.bob;
      const x = paper.x * distance * 0.52 * aspect
        + (Math.sin(time * paper.swayRate + paper.turn) * paper.sway
          + Math.sin(time * paper.swayFastRate + paper.seed) * paper.swayFast)
        * (mobile ? 0.5 : 1);
      // One shared depth buffer makes the nearer sheet fully cover a farther one.
      // The whole sheet is outside the viewport when its trajectory recycles.
      gl!.uniform3f(uniforms.uPosition, x, y, paper.z);
      // Three independent rates per sheet: the tumble never lines up with the swing, and
      // the sheet turning next to it never lines up with either.
      gl!.uniform3f(uniforms.uRotation,
        paper.tilt + Math.sin(time * paper.pitchRate + paper.turn) * paper.pitch,
        paper.turn + time * paper.spin,
        paper.roll + Math.sin(time * paper.rollRate + paper.seed) * paper.rollAmp);
      gl!.uniform1f(uniforms.uScale, scale);
      gl!.uniform1f(uniforms.uVariant, paper.variant);
      gl!.uniform1f(uniforms.uSeed, paper.seed);
      gl!.drawElements(gl!.TRIANGLES, mesh.indices.length, gl!.UNSIGNED_SHORT, 0);
    }
  }

  function resize() {
    if (destroyed) return;
    width = Math.max(1, canvas.clientWidth);
    height = Math.max(1, canvas.clientHeight);
    const ratio = Math.min(window.devicePixelRatio || 1, width < 720 ? 1.5 : 1.75,
      Math.sqrt(2_800_000 / (width * height)));
    canvas.width = Math.max(1, Math.round(width * ratio));
    canvas.height = Math.max(1, Math.round(height * ratio));
    gl!.viewport(0, 0, canvas.width, canvas.height);
    draw();
  }

  function render(now: number) {
    frame = 0;
    if (!running || destroyed) return;
    const delta = Math.min(Math.max((now - lastTime) / 1000, 0), 0.05);
    lastTime = now;
    // Fast at first, easing back to one second per second. The whole scene runs on this
    // clock — descent, sway and tumble alike — so it all slows together and nothing reads
    // as decoupled while the fall settles. Past the opening seconds the rate is 1 and the
    // snowfall keeps falling at an even pace instead of easing into a hover.
    elapsed += delta;
    time += delta * (1 + (RUSH_RATE - 1) * Math.exp(-elapsed / RUSH_SETTLE));
    light += (targetLight - light) * (1 - Math.exp(-delta * 6));
    draw();
    frame = requestAnimationFrame(render);
  }

  const observer = new ResizeObserver(resize);
  observer.observe(canvas);
  resize();

  return {
    setLight(value) {
      targetLight = value;
      if (!running) { light = value; draw(); }
    },
    setRunning(next) {
      if (destroyed) return;
      const shouldRun = next && !reduced;
      if (shouldRun === running) return;
      running = shouldRun;
      if (running) {
        lastTime = performance.now();
        frame = requestAnimationFrame(render);
      } else {
        cancelAnimationFrame(frame);
        frame = 0;
        light = targetLight;
        draw();
      }
    },
    destroy() {
      destroyed = true;
      running = false;
      cancelAnimationFrame(frame);
      observer.disconnect();
      gl.deleteVertexArray(vao);
      gl.deleteBuffer(vertices);
      gl.deleteBuffer(indices);
      gl.deleteTexture(texture);
      gl.deleteProgram(program);
    },
  };
}
