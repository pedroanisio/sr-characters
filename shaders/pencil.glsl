// Coloured pencil (or marker) laid on paper, for one filled shape.
// The colour goes down in strokes at one angle: it is streaky along the strokes, some areas are worked heavier,
// and pigment does not reach the valleys of the paper's tooth, so small specks of paper show through.
// `tooth` = 0 gives an even marker fill with faint streaks; 1 gives coloured pencil.
//
// naga note: do not assign to function parameters (the translated hash returned 0 everywhere); use locals.
uniform float angle;    // = 1.05
uniform float spacing;  // = 3.0
uniform float density;  // = 0.75
uniform float tooth;    // = 1.0
uniform float seed;     // = 1.0
uniform float bydark;   // = 0.0  (1: dark colours go down as marker, light ones as pencil, in one pass)

float hash21(vec2 q) {
    vec3 p3 = fract(vec3(q.x, q.y, q.x) * 0.1031);
    p3 = p3 + dot(p3, vec3(p3.y, p3.z, p3.x) + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float vnoise(vec2 q) {
    vec2 i = floor(q);
    vec2 f = fract(q);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

vec4 effect(vec2 uv) {
    vec4 col = getColor(uv);
    if (col.a <= 0.0) {
        return col;
    }
    float dens = density;
    float toothy = tooth;
    if (bydark > 0.5) {
        float lum = dot(col.rgb, vec3(0.299, 0.587, 0.114));
        float dark = 1.0 - smoothstep(0.18, 0.34, lum);
        dens = mix(density, 0.95, dark);
        toothy = mix(tooth, 0.25, dark);
    }
    vec2 p = sr_PixelCoord + vec2(seed * 97.0, seed * 41.0);
    float ca = cos(angle);
    float sa = sin(angle);
    vec2 r = vec2(ca * p.x + sa * p.y, -sa * p.x + ca * p.y);

    // streaks: noise stretched along the stroke direction
    float s1 = vnoise(vec2(r.x / 30.0, r.y / spacing));
    float s2 = vnoise(vec2(r.x / 18.0, r.y / (spacing * 0.55)) + 13.0);
    float area = vnoise(p / 190.0 + seed * 3.0);
    float pigment = dens + 0.5 * (s1 - 0.5) + 0.25 * (s2 - 0.5) + 0.4 * (area - 0.5);

    // paper tooth: pigment only catches on the peaks where it is laid lightly
    float grain = 0.55 * vnoise(p * 0.75) + 0.45 * vnoise(p * 2.1 + 7.0);
    float caught = smoothstep(0.0, 0.35, pigment + grain * 0.6 - 0.55);

    float cov = mix(clamp(pigment + 0.25, 0.0, 1.0), caught * clamp(pigment + 0.2, 0.0, 1.0), toothy);
    return vec4(col.rgb, col.a * clamp(cov, 0.0, 1.0));
}
