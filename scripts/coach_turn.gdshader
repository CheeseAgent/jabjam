shader_type canvas_item;

// Turn the original UVs around a convex cross-section. The chest emblem and
// shirt share this projection, as do the separate head and expression textures.
uniform float yaw = 0.0;
uniform float depth = 0.0;
varying vec4 tint;

void vertex() {
    tint = COLOR;
}

void fragment() {
    float q = UV.x * 2.0 - 1.0;
    float c = cos(yaw);
    float a = depth * sin(yaw);
    // Stable inverse of q = c*u + a*(1-u*u), including the zero-yaw pose.
    float u = 2.0*(q-a) / (c + sqrt(max(0.0, c*c-4.0*a*(q-a))));
    vec4 mapped = texture(TEXTURE, vec2(0.5*(u+1.0), UV.y));
    COLOR = abs(q) <= c ? tint * mapped : vec4(0.0);
}
