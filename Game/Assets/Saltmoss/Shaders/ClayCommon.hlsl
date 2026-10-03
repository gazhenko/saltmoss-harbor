#ifndef SALTMOSS_CLAY_COMMON
#define SALTMOSS_CLAY_COMMON

// Globals driven by ClayClock / DayCycle / SeaState (see Scripts/Runtime/Clay).
float _ClayTime;      // stepped animation time (s): changes only on stop-motion steps
float _ClayFrame;     // stepped frame counter
float _ClayBoil;      // 0..1 surface "boil" amount (0 when stop-motion is off for motion sensitivity)
float _NightGlow;     // 0 day .. 1 night: lamp glass and windows glow

float ClayHash13(float3 p)
{
    p = frac(p * 0.1031);
    p += dot(p, p.zyx + 31.32);
    return frac((p.x + p.y) * p.z);
}

float ClayHash11(float x)
{
    x = frac(x * 0.1031);
    x *= x + 33.33;
    x *= x + x;
    return frac(x);
}

float ClayNoise3(float3 p)
{
    float3 i = floor(p);
    float3 f = frac(p);
    f = f * f * (3.0 - 2.0 * f);
    float n000 = ClayHash13(i), n100 = ClayHash13(i + float3(1, 0, 0));
    float n010 = ClayHash13(i + float3(0, 1, 0)), n110 = ClayHash13(i + float3(1, 1, 0));
    float n001 = ClayHash13(i + float3(0, 0, 1)), n101 = ClayHash13(i + float3(1, 0, 1));
    float n011 = ClayHash13(i + float3(0, 1, 1)), n111 = ClayHash13(i + float3(1, 1, 1));
    return lerp(lerp(lerp(n000, n100, f.x), lerp(n010, n110, f.x), f.y),
                lerp(lerp(n001, n101, f.x), lerp(n011, n111, f.x), f.y), f.z);
}

// Each stop-motion step the animator re-handles the puppet: a tiny, different displacement of the surface.
float3 ClayBoilOffset(float3 restPos, float3 normalOS, float amp, float freq)
{
    float fr = _ClayFrame;
    float3 o = float3(ClayHash11(fr) * 61.3, ClayHash11(fr + 7.0) * 37.1, ClayHash11(fr + 13.0) * 17.9);
    float n = ClayNoise3(restPos * freq + o) - 0.5;
    n += (ClayNoise3(restPos * freq * 2.7 + o.zxy) - 0.5) * 0.5;
    return normalOS * (n * 2.0 * amp * _ClayBoil);
}

// Object-space triplanar sampling of a tangent-space normal map with whiteout blending.
half3 ClayTriplanarNormal(TEXTURE2D_PARAM(tex, samp), float3 p, half3 n, half strength)
{
    half3 w = pow(abs(n), 4.0h);
    w /= (w.x + w.y + w.z + 1e-4h);
    half3 tx = UnpackNormalScale(SAMPLE_TEXTURE2D(tex, samp, p.zy), strength);
    half3 ty = UnpackNormalScale(SAMPLE_TEXTURE2D(tex, samp, p.xz), strength);
    half3 tz = UnpackNormalScale(SAMPLE_TEXTURE2D(tex, samp, p.xy), strength);
    tx = half3(tx.xy + n.zy, abs(tx.z) * n.x);
    ty = half3(ty.xy + n.xz, abs(ty.z) * n.y);
    tz = half3(tz.xy + n.xy, abs(tz.z) * n.z);
    return normalize(tx.zyx * w.x + ty.xzy * w.y + tz.xyz * w.z);
}

half3 ClaySrgbToLinear(half3 c)
{
    return c * (c * (c * 0.305306011h + 0.682171111h) + 0.012522878h);
}

#endif
