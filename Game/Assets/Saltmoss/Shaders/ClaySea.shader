// The sea as a sculpted, varnished clay surface: Gerstner swell evaluated at stop-motion time (it moves on twos),
// rougher with distance from the harbour and with the weather, white clay foam on crests, along shores/pilings
// (baked shore-foam map) and in wakes (dynamic foam points). Mirrored on the CPU by SeaState.HeightAt for buoyancy.
Shader "Saltmoss/ClaySea"
{
    Properties
    {
        _DeepColor ("Deep", Color) = (0.12, 0.27, 0.32, 1)
        _CrestColor ("Crest", Color) = (0.26, 0.48, 0.5, 1)
        _HarborColor ("Harbour (shallow) tint", Color) = (0.2, 0.42, 0.42, 1)
        _FoamColor ("Foam", Color) = (0.93, 0.92, 0.87, 1)
        [Normal][NoScaleOffset] _RippleNormal ("Sculpted ripples", 2D) = "bump" {}
        _RippleScale ("Ripple tiles per metre", Float) = 0.22
        _RippleStrength ("Ripple strength", Range(0, 2)) = 0.7
        [Normal][NoScaleOffset] _FingerNormal ("Fingerprints", 2D) = "bump" {}
        _FingerScale ("Fingerprint tiles per metre", Float) = 1.1
        _FingerStrength ("Fingerprint strength", Range(0, 2)) = 0.35
        _Smooth ("Varnish smoothness", Range(0, 1)) = 0.84
        _FoamSmooth ("Foam smoothness", Range(0, 1)) = 0.3
        _CrestFoam ("Crest foam threshold", Range(0, 1.5)) = 0.72
        _SSSColor ("Backlit crest colour", Color) = (0.25, 0.6, 0.45, 1)
        _SSS ("Backlit crest", Range(0, 2)) = 0.6
        [NoScaleOffset] _ShoreFoam ("Shore foam map (R)", 2D) = "black" {}
        _ShoreRect ("Shore map rect (minX, minZ, sizeX, sizeZ)", Vector) = (-128, -128, 256, 256)
    }

    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry+10" }

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
        #include "ClayCommon.hlsl"

        #define SEA_WAVES 6
        float4 _SeaWaveA[SEA_WAVES];   // dir.x, dir.z, k (2pi/lambda), omega
        float4 _SeaWaveB[SEA_WAVES];   // amplitude (m), steepness Q, phase, -
        float4 _SeaRough;              // centre.x, centre.z, r0, r1
        float4 _SeaRoughAmp;           // calm multiplier (inside r0), rough multiplier (beyond r1), chop, -
        float4 _FoamPoints[32];        // x, z, radius, strength

        TEXTURE2D(_RippleNormal); SAMPLER(sampler_RippleNormal);
        TEXTURE2D(_FingerNormal); SAMPLER(sampler_FingerNormal);
        TEXTURE2D(_ShoreFoam); SAMPLER(sampler_ShoreFoam);

        CBUFFER_START(UnityPerMaterial)
            half4 _DeepColor, _CrestColor, _HarborColor, _FoamColor, _SSSColor;
            float _RippleScale; half _RippleStrength;
            float _FingerScale; half _FingerStrength;
            half _Smooth, _FoamSmooth, _CrestFoam, _SSS;
            float4 _ShoreRect;
        CBUFFER_END

        float RoughAt(float2 xz)
        {
            float d = distance(xz, _SeaRough.xy);
            float t = saturate((d - _SeaRough.z) / max(_SeaRough.w - _SeaRough.z, 1.0));
            return lerp(_SeaRoughAmp.x, _SeaRoughAmp.y, t * t * (3.0 - 2.0 * t));
        }

        // Gerstner displacement + normal at rest position xz
        void Gerstner(float2 xz, out float3 disp, out float3 normal, out float crest, out float ampSum)
        {
            float m = RoughAt(xz);
            float t = _ClayTime;
            disp = float3(0, 0, 0);
            float3 n = float3(0, 1, 0);
            crest = 0; ampSum = 0;
            [unroll]
            for (int i = 0; i < SEA_WAVES; i++)
            {
                float2 d = _SeaWaveA[i].xy;
                float k = _SeaWaveA[i].z, w = _SeaWaveA[i].w;
                float A = _SeaWaveB[i].x * m, Q = _SeaWaveB[i].y;
                float th = k * dot(d, xz) - w * t + _SeaWaveB[i].z;
                float s, c;
                sincos(th, s, c);
                disp += float3(Q * A * d.x * c, A * s, Q * A * d.y * c);
                n -= float3(d.x * k * A * c, Q * k * A * s, d.y * k * A * c);
                crest += A * s;
                ampSum += A;
            }
            normal = normalize(n);
        }
        ENDHLSL

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            Cull Back
            ZWrite On

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _SCREEN_SPACE_OCCLUSION
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile _ _CLUSTER_LIGHT_LOOP
            #pragma multi_compile_fog
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            struct A { float4 positionOS : POSITION; };
            struct V
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                float2 restXZ : TEXCOORD1;
                half3 normalWS : TEXCOORD2;
                half2 crest : TEXCOORD3;   // normalised height, amplitude sum
                half fog : TEXCOORD4;
            };

            V vert(A v)
            {
                V o;
                float3 ws = TransformObjectToWorld(v.positionOS.xyz);
                float3 disp, n; float crest, ampSum;
                Gerstner(ws.xz, disp, n, crest, ampSum);
                float3 p = float3(ws.x, 0, ws.z) + disp;
                o.positionWS = p;
                o.positionCS = TransformWorldToHClip(p);
                o.restXZ = ws.xz;
                o.normalWS = n;
                o.crest = half2(crest / max(ampSum, 1e-3), ampSum);
                o.fog = ComputeFogFactor(o.positionCS.z);
                return o;
            }

            half4 frag(V i) : SV_Target
            {
                float2 xz = i.restXZ;
                half3 nGeo = normalize(i.normalWS);
                // sculpted ripples: two layers of tool-pushed ripples, stepping with the stop-motion clock
                float t = _ClayTime;
                float2 uv1 = xz * _RippleScale + float2(t * 0.013, t * 0.008);
                float2 uv2 = xz * _RippleScale * 2.3 + float2(-t * 0.011, t * 0.017) + 0.37;
                half rs = _RippleStrength * (0.5h + i.crest.y * 0.6h);
                half3 r1 = UnpackNormalScale(SAMPLE_TEXTURE2D(_RippleNormal, sampler_RippleNormal, uv1), rs);
                half3 r2 = UnpackNormalScale(SAMPLE_TEXTURE2D(_RippleNormal, sampler_RippleNormal, uv2), rs * 0.6h);
                half3 f1 = UnpackNormalScale(SAMPLE_TEXTURE2D(_FingerNormal, sampler_FingerNormal, xz * _FingerScale), _FingerStrength);
                half2 slope = r1.xy + r2.xy + f1.xy;
                half3 n = normalize(nGeo + half3(slope.x, 0, slope.y));

                // colour: deep troughs, lighter crests, greener harbour water
                half h = i.crest.x * 0.5h + 0.5h;
                float rough = RoughAt(xz);
                half3 col = lerp(_DeepColor.rgb, _CrestColor.rgb, saturate(h * 1.1h));
                col = lerp(_HarborColor.rgb, col, saturate(rough * 1.4h));
                half mott = ClayNoise3(float3(xz * 0.9, 1.7)) - 0.5h + (ClayNoise3(float3(xz * 4.1, 3.3)) - 0.5h) * 0.5h;
                col *= 1.0h + mott * 0.12h;

                // foam: crests, shores/pilings, wakes — lumpy white clay with a broken edge
                half fn = ClayNoise3(float3(xz * 1.7, _ClayFrame * 0.0 + 2.0)) * 0.6h + ClayNoise3(float3(xz * 5.3, 9.0)) * 0.4h;
                half crestFoam = saturate((i.crest.x - _CrestFoam + (fn - 0.5h) * 0.5h) * 4.0h) * saturate(i.crest.y * 1.5h);
                float2 suv = (xz - _ShoreRect.xy) / _ShoreRect.zw;
                half shore = all(suv > 0) && all(suv < 1) ? SAMPLE_TEXTURE2D(_ShoreFoam, sampler_ShoreFoam, suv).r : 0;
                // shore foam breathes with the swell
                half shoreFoam = saturate((shore - 0.5h + (fn - 0.5h) * 0.5h + i.crest.x * 0.1h) * 3.0h);
                half wake = 0;
                [loop]
                for (int k = 0; k < 32; k++)
                {
                    float4 fp = _FoamPoints[k];
                    if (fp.w <= 0) continue;
                    float d = distance(xz, fp.xy) / fp.z;
                    wake = max(wake, saturate((1.0 - d) * 2.0 + (fn - 0.5) * 0.9) * fp.w);
                }
                half foam = saturate(max(max(crestFoam, shoreFoam), wake));
                foam = smoothstep(0.35h, 0.6h, foam);
                // foam is a raised lump of clay: tilt the normal at its edge
                n = normalize(n + half3(ddx(foam), 0, ddy(foam)) * 1.5h);
                col = lerp(col, _FoamColor.rgb * (0.92h + fn * 0.1h), foam);
                half smooth = lerp(_Smooth, _FoamSmooth, foam);

                InputData input = (InputData)0;
                input.positionWS = i.positionWS;
                input.positionCS = i.positionCS;
                input.normalWS = n;
                input.viewDirectionWS = GetWorldSpaceNormalizeViewDir(i.positionWS);
                input.shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                input.fogCoord = i.fog;
                input.bakedGI = SampleSH(n);
                input.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(i.positionCS);
                input.shadowMask = half4(1, 1, 1, 1);

                SurfaceData s = (SurfaceData)0;
                s.albedo = col;
                s.smoothness = smooth;
                s.occlusion = 1;
                s.alpha = 1;
                s.normalTS = half3(0, 0, 1);
                half4 c = UniversalFragmentPBR(input, s);

                // light through thin crests (resin-like) when looking toward the sun
                Light L = GetMainLight(input.shadowCoord, input.positionWS, input.shadowMask);
                half back = pow(saturate(dot(input.viewDirectionWS, -L.direction)), 3.0h);
                c.rgb += _SSSColor.rgb * L.color * (_SSS * back * saturate(i.crest.x * 0.5h + 0.5h) * (1.0h - foam));
                c.rgb = MixFog(c.rgb, i.fog);
                return half4(c.rgb, 1);
            }
            ENDHLSL
        }

        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode" = "DepthOnly" }
            ZWrite On
            ColorMask R
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            struct A { float4 positionOS : POSITION; };
            float4 vert(A v) : SV_POSITION
            {
                float3 ws = TransformObjectToWorld(v.positionOS.xyz);
                float3 d, n; float c, s;
                Gerstner(ws.xz, d, n, c, s);
                return TransformWorldToHClip(float3(ws.x, 0, ws.z) + d);
            }
            half frag(float4 p : SV_POSITION) : SV_Target { return p.z; }
            ENDHLSL
        }

        Pass
        {
            Name "DepthNormals"
            Tags { "LightMode" = "DepthNormals" }
            ZWrite On
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_fragment _ _GBUFFER_NORMALS_OCT
            struct A { float4 positionOS : POSITION; };
            struct V { float4 positionCS : SV_POSITION; half3 n : TEXCOORD0; };
            V vert(A v)
            {
                V o;
                float3 ws = TransformObjectToWorld(v.positionOS.xyz);
                float3 d, n; float c, s;
                Gerstner(ws.xz, d, n, c, s);
                o.positionCS = TransformWorldToHClip(float3(ws.x, 0, ws.z) + d);
                o.n = n;
                return o;
            }
            half4 frag(V i) : SV_Target
            {
                float3 n = normalize(i.n);
            #if defined(_GBUFFER_NORMALS_OCT)
                return half4(PackFloat2To888(saturate(PackNormalOctQuadEncode(n) * 0.5 + 0.5)), 0.0);
            #else
                return half4(n, 0.0);
            #endif
            }
            ENDHLSL
        }
    }
    FallBack Off
}
