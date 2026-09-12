/** A flexible, double-sided A4 surface, lit in world space. */
export const PAPER_VERTEX_SHADER = `#version 300 es
precision highp float;

layout(location = 0) in vec3 aPosition;
layout(location = 1) in vec2 aUv;

uniform float uAspect;
uniform float uTime;
uniform vec3 uPosition;
uniform vec3 uRotation;
uniform float uScale;
uniform float uSeed;

out vec2 vUv;
out vec3 vNormal;
out vec3 vWorld;

vec3 rotatePaper(vec3 p) {
  vec3 c = cos(uRotation), s = sin(uRotation);
  p = vec3(p.x, c.x * p.y - s.x * p.z, s.x * p.y + c.x * p.z);
  p = vec3(c.y * p.x + s.y * p.z, p.y, -s.y * p.x + c.y * p.z);
  return vec3(c.z * p.x - s.z * p.y, s.z * p.x + c.z * p.y, p.z);
}

void main() {
  float x = aPosition.x, y = aPosition.y;
  float phase = uTime * 0.48 + uSeed * 6.283185;
  float curl = 0.065 + 0.0275 * sin(phase * 0.61);
  float twist = 0.075 * sin(phase * 0.43 + 1.7);
  float rippleY = y * 5.2 + phase;
  float rippleX = x * 3.1 + uSeed * 4.0;
  // A broad curl, a gentle twist, and a small travelling flutter. Derivatives of
  // the same surface keep lighting smooth across the subdivided mesh.
  float bend = curl * x * x * 2.6 + twist * x * y
    + 0.0225 * sin(rippleY) * sin(rippleX);
  float dx = curl * x * 5.2 + twist * y
    + 0.06975 * sin(rippleY) * cos(rippleX);
  float dy = twist * x + 0.117 * cos(rippleY) * sin(rippleX);

  vUv = aUv;
  vNormal = rotatePaper(normalize(vec3(-dx, -dy, 1.0)));
  vWorld = rotatePaper(vec3(x, y, bend) * uScale) + uPosition;
  float distance = 12.0 - vWorld.z;
  // Perspective projection, vertical tan(fov / 2) = 0.52, near/far = 0.1/60.
  gl_Position = vec4(vWorld.x / (0.52 * uAspect), vWorld.y / 0.52,
    (60.1 / 59.9) * distance - (12.0 / 59.9), distance);
}`;

export const PAPER_FRAGMENT_SHADER = `#version 300 es
precision highp float;

in vec2 vUv;
in vec3 vNormal;
in vec3 vWorld;

uniform float uLight;
uniform float uVariant;
uniform sampler2D uDocuments;

out vec4 outColor;

void main() {
  // Keep bilinear filtering within the selected high-resolution A4 panel.
  vec2 pageUv = clamp(vUv, vec2(0.5 / 768.0, 0.5 / 1086.0),
    vec2(1.0 - 0.5 / 768.0, 1.0 - 0.5 / 1086.0));
  vec3 printColor = texture(uDocuments, vec2((pageUv.x + uVariant) / 3.0, pageUv.y)).rgb;
  vec3 normal = normalize(vNormal) * (gl_FrontFacing ? 1.0 : -1.0);
  // Office stock stays solid, with only a trace of ink visible on the reverse.
  if (!gl_FrontFacing) printColor = mix(vec3(0.996, 0.992, 0.976), printColor, 0.06);
  vec3 light = normalize(vec3(-0.55, 0.8, 1.0));
  vec3 view = normalize(vec3(0.0, 0.0, 12.0) - vWorld);
  float diffuse = max(dot(normal, light), 0.0);
  float highlight = pow(max(dot(normal, normalize(light + view)), 0.0), 30.0) * 0.025;
  vec3 tint = mix(vec3(0.9, 0.935, 0.98), vec3(0.99, 0.995, 1.0), uLight);
  float edgeDistance = min(min(vUv.x, 1.0 - vUv.x), min(vUv.y, 1.0 - vUv.y));
  float edge = 1.0 - smoothstep(0.001, 0.004, edgeDistance);
  printColor = mix(printColor, vec3(0.80, 0.82, 0.84), edge * 0.38);
  vec3 color = printColor * tint * (0.76 + diffuse * 0.22) + highlight;
  // Recede by dimming the surface, never by revealing another sheet through it.
  float depthLight = mix(0.74, 1.0, clamp((vWorld.z + 7.0) / 9.0, 0.0, 1.0));
  outColor = vec4(color * depthLight, 1.0);
}`;

/** UV origin is the page's top left. Upload the canvas without flipping Y. */
export function createPaperMesh(): { vertices: Float32Array; indices: Uint16Array } {
  const columns = 18;
  const rows = 26;
  const vertices = new Float32Array((columns + 1) * (rows + 1) * 5);
  const indices = new Uint16Array(columns * rows * 6);
  let vertex = 0;
  let index = 0;
  for (let row = 0; row <= rows; row += 1) {
    for (let column = 0; column <= columns; column += 1) {
      const u = column / columns;
      const v = row / rows;
      vertices.set([u - 0.5, (0.5 - v) * 1.414, 0, u, v], vertex);
      vertex += 5;
      if (column === columns || row === rows) continue;
      const a = row * (columns + 1) + column;
      const b = a + 1;
      const c = a + columns + 1;
      indices.set([a, c, b, b, c, c + 1], index);
      index += 6;
    }
  }
  return { vertices, indices };
}

/** Three original, readable document designs share one local A4 texture atlas. */
export function createDocumentTexture(): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = 2304;
  canvas.height = 1086;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Unable to create the document texture');

  for (let variant = 0; variant < 3; variant += 1) {
    context.save();
    context.translate(variant * 768, 0);
    context.scale(1.5, 1.5);
    context.fillStyle = '#fffefa';
    context.fillRect(0, 0, 512, 724);

    let seed = 179 + variant * 293;
    const random = () => {
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      return seed / 4294967296;
    };
    // Low-contrast fibres remain attached to the surface as it turns.
    context.fillStyle = 'rgba(61, 67, 76, 0.018)';
    for (let fibre = 0; fibre < 1600; fibre += 1) {
      context.fillRect(random() * 512, random() * 724, random() * 2 + 0.5, 0.5);
    }

    const line = (x: number, y: number, width: number, height = 3) => {
      context.fillRect(x, y, width, height);
    };
    const paragraph = (y: number, rows: string[]) => {
      context.fillStyle = '#3b414a';
      context.font = '15px Arial, sans-serif';
      rows.forEach((row, index) => context.fillText(row, 56, y + index * 25, 400));
    };
    const section = (text: string, y: number) => {
      context.fillStyle = '#222a35';
      context.font = '600 16px Arial, sans-serif';
      context.fillText(text, 56, y);
    };

    context.fillStyle = '#526174';
    context.font = '600 11px Arial, sans-serif';
    context.fillText('ДЕЛОВЫЕ ДОКУМЕНТЫ', 56, 48);
    context.textAlign = 'right';
    context.font = '11px Arial, sans-serif';
    context.fillText(`№ 0${variant + 1} / 2026`, 456, 48);
    context.fillStyle = '#c9ced5';
    line(56, 62, 400, 1);

    context.fillStyle = '#242d3a';
    context.font = `600 ${variant === 1 ? 25 : 30}px Arial, sans-serif`;
    context.textAlign = 'center';
    context.fillText(['ЗАЯВЛЕНИЕ', 'ОПИСЬ ДОКУМЕНТОВ', 'ДОГОВОР'][variant], 256, 164);
    context.fillStyle = '#637083';
    context.font = '13px Arial, sans-serif';
    context.fillText(['о предоставлении документов', 'приложение к заявлению', 'об оказании услуг'][variant], 256, 189);
    context.textAlign = 'left';

    if (variant === 1) {
      paragraph(245, ['Перечень передаваемых документов.', 'Дата составления: 12 сентября 2026 г.']);
      context.strokeStyle = '#7f8a98';
      context.lineWidth = 1;
      context.strokeRect(56, 302, 400, 200);
      context.fillStyle = '#e6eaf0';
      context.fillRect(56.5, 302.5, 399, 39);
      context.beginPath();
      for (let row = 1; row < 5; row += 1) {
        const y = 302 + row * 40;
        context.moveTo(56, y);
        context.lineTo(456, y);
      }
      for (const x of [100, 380]) {
        context.moveTo(x, 302);
        context.lineTo(x, 502);
      }
      context.stroke();
      const rows = [
        ['№', 'Наименование', 'Листов'],
        ['1', 'Заявление', '1'],
        ['2', 'Копия договора', '2'],
        ['3', 'Справка', '1'],
        ['4', 'Приложение', '1'],
      ];
      context.fillStyle = '#303946';
      rows.forEach((row, index) => {
        context.font = `${index === 0 ? '600 ' : ''}14px Arial, sans-serif`;
        const y = 327 + index * 40;
        context.fillText(row[0], 68, y);
        context.fillText(row[1], 112, y);
        context.textAlign = 'center';
        context.fillText(row[2], 418, y);
        context.textAlign = 'left';
      });
      paragraph(537, ['Всего: 4 документа на 5 листах.', 'Документы переданы в полном объёме.']);
    } else if (variant === 0) {
      context.fillStyle = '#586372';
      context.font = '13px Arial, sans-serif';
      context.textAlign = 'right';
      context.fillText('Руководителю организации', 456, 92);
      context.fillText('от Иванова Ивана Ивановича', 456, 113);
      context.textAlign = 'left';
      paragraph(246, [
        'Прошу предоставить копии документов',
        'и направить ответ по указанному адресу.',
        'Необходимые сведения и приложения',
        'указаны в настоящем заявлении.',
      ]);
      section('Сведения заявителя', 385);
      paragraph(416, [
        'Ф. И. О.: Иванов Иван Иванович',
        'Адрес: г. Брянск, ул. Лесная, д. 12',
        'Способ получения: электронная почта',
      ]);
      section('Приложения', 526);
      paragraph(555, ['1. Копия документа — 1 лист.', '2. Дополнительные сведения — 1 лист.']);
    } else {
      section('1. Предмет договора', 245);
      paragraph(275, [
        'Заказчик поручает, а Исполнитель',
        'принимает на себя оказание услуг.',
        'Перечень и сроки указаны в приложении.',
      ]);
      section('2. Порядок выполнения', 380);
      paragraph(410, [
        'Работы выполняются в согласованный срок.',
        'Результат передаётся Заказчику по акту.',
        'Изменения оформляются письменно.',
      ]);
      section('3. Реквизиты и подписи сторон', 517);
      paragraph(547, ['Заказчик: Иванов И. И.', 'Исполнитель: Петров А. С.']);
    }

    context.fillStyle = '#5d6671';
    context.font = '13px Arial, sans-serif';
    context.fillText('12.09.2026', 56, 637);
    line(56, 644, 106, 0.8);
    line(291, 644, 165, 0.8);
    context.font = '10px Arial, sans-serif';
    context.fillText('Дата', 56, 662);
    context.fillText('Подпись', 291, 662);
    context.strokeStyle = '#385477';
    context.lineWidth = 1.7;
    context.lineCap = 'round';
    context.beginPath();
    context.moveTo(304, 639);
    context.bezierCurveTo(354, 599, 314, 670, 340, 630);
    context.bezierCurveTo(363, 594, 341, 664, 370, 632);
    context.bezierCurveTo(378, 647, 391, 622, 407, 633);
    context.stroke();

    if (variant !== 0) {
      context.strokeStyle = 'rgba(61, 96, 142, 0.58)';
      context.lineWidth = 1.3;
      for (const radius of [31, 25]) {
        context.beginPath();
        context.arc(249, 638, radius, 0, Math.PI * 2);
        context.stroke();
      }
      context.fillStyle = 'rgba(61, 96, 142, 0.7)';
      context.font = '600 8px Arial, sans-serif';
      context.textAlign = 'center';
      context.fillText('ДОКУМЕНТ', 249, 635);
      context.font = '7px Arial, sans-serif';
      context.fillText('ПРИНЯТО', 249, 646);
    }
    context.fillStyle = '#7c8590';
    context.font = '10px Arial, sans-serif';
    context.textAlign = 'center';
    context.fillText('1', 256, 697);
    context.restore();
  }
  return canvas;
}
