// Soft shade for plush toys: a lit pass (white in light, darker in shade) turned into a tint that fades in gently,
// to multiply over the flat colour. srlocations' cel shader cuts hard between two tones; a soft toy needs the shade
// to roll in, so the edge is a smoothstep `soft` wide around `cut`.
//
// naga note: do not assign to function parameters; use locals.
uniform float cut;    // = 0.5
uniform float soft;   // = 0.18
uniform float shadeR; // = 0.85
uniform float shadeG; // = 0.78
uniform float shadeB; // = 0.80

vec4 effect(vec2 uv) {
    vec4 lit = getColor(uv);
    float tone = dot(lit.rgb, vec3(0.3, 0.59, 0.11));
    if (lit.a < 0.01 || tone < 0.02) {  // nothing drawn here (or the empty backdrop): leave the paper alone
        return vec4(1.0, 1.0, 1.0, 1.0);
    }
    float k = smoothstep(cut - soft, cut + soft, tone);
    return vec4(mix(vec3(shadeR, shadeG, shadeB), vec3(1.0), k), lit.a);
}
