// Plasticine: URP PBR lighting (cascaded soft shadows, Forward+ lights, probes, SSAO) over sculpted vertex colour.
// Rest-pose triplanar fingerprints and tool marks (stick to skinned surfaces), wrap-lit subsurface warmth at the
// terminator, per-vertex gloss (vertex alpha: matte clay .. varnished/wet/eyes), and a per-step surface "boil".
Shader "Saltmoss/Clay"
{
    Properties
    {
        [MainColor] _BaseColor ("Tint", Color) = (1, 1, 1, 1)
        _VertexColor ("Use vertex colour + gloss", Range(0, 1)) = 1
        _Gloss ("Gloss (when no vertex colour)", Range(0, 1)) = 0.2
        _RestFromUV1 ("Rest position in UV1 (claymesh)", Float) = 1
        [Normal][NoScaleOffset] _FingerNormal ("Fingerprints / thumb smears", 2D) = "bump" {}
        _FingerScale ("Fingerprint tiles per metre", Float) = 7
        _FingerStrength ("Fingerprint strength", Range(0, 2)) = 0.55
        [Normal][NoScaleOffset] _ToolNormal ("Tool scrapes / pits", 2D) = "bump" {}
        _ToolScale ("Tool tiles per metre", Float) = 2.2
        _ToolStrength ("Tool strength", Range(0, 2)) = 0.35
        _Mottle ("Mottle", Range(0, 0.5)) = 0.06
        _MatteSmooth ("Matte smoothness", Range(0, 1)) = 0.34
        _GlossSmooth ("Gloss smoothness", Range(0, 1)) = 0.9
        _SSSColor ("Subsurface colour", Color) = (1.0, 0.42, 0.3, 1)
        _SSS ("Subsurface", Range(0, 2)) = 0.45
        _Wrap ("Wrap", Range(0, 1)) = 0.45
        _BoilAmp ("Boil amplitude (m)", Float) = 0.0016
        _BoilFreq ("Boil frequency", Float) = 9
        _Emissive ("Night glow (lamp glass)", Range(0, 1)) = 0
        [HDR] _EmissionColor ("Glow colour", Color) = (3.2, 2.1, 1.0, 1)
        _DayGlow ("Glow by day", Range(0, 1)) = 0.06
        _Wiggle ("Swim wiggle (fish)", Float) = 0
        _WiggleFreq ("Swim wiggle frequency", Float) = 7
        _NetCutout ("Procedural net cutout", Float) = 0
        _NetScale ("Net cells per metre", Float) = 14
        [Enum(UnityEngine.Rendering.CullMode)] _Cull ("Cull", Float) = 2
    }

    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry" }

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
        #include "ClayCommon.hlsl"

        TEXTURE2D(_FingerNormal); SAMPLER(sampler_FingerNormal);
        TEXTURE2D(_ToolNormal);   SAMPLER(sampler_ToolNormal);

        CBUFFER_START(UnityPerMaterial)
            half4 _BaseColor;
            half _VertexColor;
            half _Gloss;
            float _RestFromUV1;
            float _FingerScale;
            half _FingerStrength;
            float _ToolScale;
            half _ToolStrength;
            half _Mottle;
            half _MatteSmooth;
            half _GlossSmooth;
            half4 _SSSColor;
            half _SSS;
            half _Wrap;
            float _BoilAmp;
            float _BoilFreq;
            half _Emissive;
            half4 _EmissionColor;
            half _DayGlow;
            float _Wiggle;
            float _WiggleFreq;
            float _NetCutout;
            float _NetScale;
        CBUFFER_END

        struct ClayAttributes
        {
            float4 positionOS : POSITION;
            float3 normalOS : NORMAL;
            half4 color : COLOR;
            float3 rest : TEXCOORD1;
            UNITY_VERTEX_INPUT_INSTANCE_ID
        };

        float3 RestPos(ClayAttributes v)
        {
            return _RestFromUV1 > 0.5 ? v.rest : v.positionOS.xyz;
        }

        // boil + optional fish swim wiggle (head at +Z stays steadier than the tail)
        float3 ClayDeform(float3 posOS, float3 nOS, float3 rest)
        {
            posOS += ClayBoilOffset(rest, nOS, _BoilAmp, _BoilFreq);
            if (_Wiggle > 0.0)
            {
                float tailW = saturate(0.5 - rest.z * 1.2);
                posOS.x += sin(rest.z * 6.0 - _ClayTime * _WiggleFreq) * _Wiggle * (0.25 + tailW);
            }
            return posOS;
        }

        void NetClip(float3 rest, float3 nOS)
        {
            if (_NetCutout > 0.5)
            {
                float3 a = abs(nOS);
                float2 uv = a.x > a.y && a.x > a.z ? rest.zy : (a.y > a.z ? rest.xz : rest.xy);
                // diamond mesh: two diagonal families of strands
                float2 g = uv * _NetScale;
                float s1 = abs(frac(g.x + g.y) - 0.5);
                float s2 = abs(frac(g.x - g.y) - 0.5);
                clip(max(s1, s2) - 0.38);
            }
        }
        ENDHLSL

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            Cull [_Cull]
            ZWrite On

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _ADDITIONAL_LIGHT_SHADOWS
            #pragma multi_compile_fragment _ _REFLECTION_PROBE_BLENDING
            #pragma multi_compile_fragment _ _SCREEN_SPACE_OCCLUSION
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile _ _CLUSTER_LIGHT_LOOP
            #pragma multi_compile_fragment _ _LIGHT_LAYERS
            #pragma multi_compile_fog
            #pragma multi_compile_instancing

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float3 positionWS : TEXCOORD0;
                half3 normalWS : TEXCOORD1;
                half3 normalOS : TEXCOORD2;
                float3 rest : TEXCOORD3;
                half4 color : TEXCOORD4;
                half fogFactor : TEXCOORD5;
                UNITY_VERTEX_INPUT_INSTANCE_ID
                UNITY_VERTEX_OUTPUT_STEREO
            };

            Varyings vert(ClayAttributes v)
            {
                Varyings o = (Varyings)0;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_TRANSFER_INSTANCE_ID(v, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                float3 rest = RestPos(v);
                float3 pos = ClayDeform(v.positionOS.xyz, v.normalOS, rest);
                VertexPositionInputs p = GetVertexPositionInputs(pos);
                o.positionCS = p.positionCS;
                o.positionWS = p.positionWS;
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.normalOS = v.normalOS;
                o.rest = rest;
                o.color = v.color;
                o.fogFactor = ComputeFogFactor(p.positionCS.z);
                return o;
            }

            half4 frag(Varyings i) : SV_Target
            {
                UNITY_SETUP_INSTANCE_ID(i);
                half3 nOS = normalize(i.normalOS);
                NetClip(i.rest, nOS);
                half4 vc = i.color;
                half3 base = lerp(half3(1, 1, 1), ClaySrgbToLinear(vc.rgb), _VertexColor) * _BaseColor.rgb;
                half gloss = lerp(_Gloss, vc.a, _VertexColor);
                // hand-mixed clay is never one flat colour
                half m = ClayNoise3(i.rest * 31.0) - 0.5h + (ClayNoise3(i.rest * 7.0 + 5.1) - 0.5h) * 0.6h;
                base *= 1.0h + m * _Mottle;

                // fingerprints fade on varnished/glossy bits (eyes, wet skin, glass)
                half fs = _FingerStrength * (1.0h - gloss * 0.75h);
                half3 n1 = ClayTriplanarNormal(TEXTURE2D_ARGS(_FingerNormal, sampler_FingerNormal), i.rest * _FingerScale, nOS, fs);
                half3 n2 = ClayTriplanarNormal(TEXTURE2D_ARGS(_ToolNormal, sampler_ToolNormal), i.rest * _ToolScale + 0.37, nOS, _ToolStrength * (1.0h - gloss * 0.5h));
                half3 nDetail = normalize(nOS + (n1 - nOS) + (n2 - nOS));
                half3 normalWS = normalize(TransformObjectToWorldNormal(nDetail));
                if (dot(normalWS, normalWS) < 1e-6) normalWS = normalize(i.normalWS);

                half smooth = lerp(_MatteSmooth, _GlossSmooth, gloss);
                // geometric specular AA
                float3 dndx = ddx(normalWS), dndy = ddy(normalWS);
                float variance = 0.25 * (dot(dndx, dndx) + dot(dndy, dndy));
                float rough = 1.0 - smooth;
                smooth = (half)(1.0 - sqrt(saturate(rough * rough + min(2.0 * variance, 0.18))));

                InputData input = (InputData)0;
                input.positionWS = i.positionWS;
                input.positionCS = i.positionCS;
                input.normalWS = normalWS;
                input.viewDirectionWS = GetWorldSpaceNormalizeViewDir(i.positionWS);
                input.shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                input.fogCoord = i.fogFactor;
                input.bakedGI = SampleSH(normalWS);
                input.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(i.positionCS);
                input.shadowMask = half4(1, 1, 1, 1);

                SurfaceData s = (SurfaceData)0;
                s.albedo = base;
                s.metallic = 0.0h;
                s.specular = half3(0, 0, 0);
                s.smoothness = smooth;
                s.normalTS = half3(0, 0, 1);
                s.occlusion = 1.0h;
                s.alpha = 1.0h;
                half glow = _Emissive * lerp(_DayGlow, 1.0h, _NightGlow);
                s.emission = base * _EmissionColor.rgb * glow;

                half4 color = UniversalFragmentPBR(input, s);

                // subsurface: light bleeding past the terminator, warm in the shadowed side of thin lumps
                Light mainLight = GetMainLight(input.shadowCoord, input.positionWS, input.shadowMask);
                half ndl = dot(normalWS, mainLight.direction);
                half wrap = saturate((ndl + _Wrap) / (1.0h + _Wrap)) - saturate(ndl);
                half sh = lerp(1.0h, mainLight.shadowAttenuation, 0.65h);
                color.rgb += base * _SSSColor.rgb * (_SSS * wrap * sh) * mainLight.color * mainLight.distanceAttenuation;

                color.rgb = MixFog(color.rgb, i.fogFactor);
                return half4(color.rgb, 1.0h);
            }
            ENDHLSL
        }

        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode" = "ShadowCaster" }
            ZWrite On
            ZTest LEqual
            ColorMask 0
            Cull [_Cull]

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"

            float3 _LightDirection;
            float3 _LightPosition;

            struct V2F { float4 positionCS : SV_POSITION; float3 rest : TEXCOORD0; half3 nOS : TEXCOORD1; };

            V2F vert(ClayAttributes v)
            {
                V2F o;
                UNITY_SETUP_INSTANCE_ID(v);
                float3 rest = RestPos(v);
                float3 pos = ClayDeform(v.positionOS.xyz, v.normalOS, rest);
                float3 posWS = TransformObjectToWorld(pos);
                float3 nWS = TransformObjectToWorldNormal(v.normalOS);
            #if _CASTING_PUNCTUAL_LIGHT_SHADOW
                float3 lightDir = normalize(_LightPosition - posWS);
            #else
                float3 lightDir = _LightDirection;
            #endif
                float4 cs = TransformWorldToHClip(ApplyShadowBias(posWS, nWS, lightDir));
            #if UNITY_REVERSED_Z
                cs.z = min(cs.z, UNITY_NEAR_CLIP_VALUE);
            #else
                cs.z = max(cs.z, UNITY_NEAR_CLIP_VALUE);
            #endif
                o.positionCS = cs;
                o.rest = rest;
                o.nOS = v.normalOS;
                return o;
            }

            half4 frag(V2F i) : SV_Target { NetClip(i.rest, normalize(i.nOS)); return 0; }
            ENDHLSL
        }

        Pass
        {
            Name "DepthOnly"
            Tags { "LightMode" = "DepthOnly" }
            ZWrite On
            ColorMask R
            Cull [_Cull]

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing

            struct V2F { float4 positionCS : SV_POSITION; float3 rest : TEXCOORD0; half3 nOS : TEXCOORD1; };

            V2F vert(ClayAttributes v)
            {
                V2F o;
                UNITY_SETUP_INSTANCE_ID(v);
                float3 rest = RestPos(v);
                o.positionCS = TransformObjectToHClip(ClayDeform(v.positionOS.xyz, v.normalOS, rest));
                o.rest = rest;
                o.nOS = v.normalOS;
                return o;
            }

            half frag(V2F i) : SV_Target { NetClip(i.rest, normalize(i.nOS)); return i.positionCS.z; }
            ENDHLSL
        }

        Pass
        {
            Name "DepthNormals"
            Tags { "LightMode" = "DepthNormals" }
            ZWrite On
            Cull [_Cull]

            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #pragma multi_compile_fragment _ _GBUFFER_NORMALS_OCT

            struct V2F { float4 positionCS : SV_POSITION; half3 normalWS : TEXCOORD0; float3 rest : TEXCOORD1; half3 nOS : TEXCOORD2; };

            V2F vert(ClayAttributes v)
            {
                V2F o;
                UNITY_SETUP_INSTANCE_ID(v);
                float3 rest = RestPos(v);
                o.positionCS = TransformObjectToHClip(ClayDeform(v.positionOS.xyz, v.normalOS, rest));
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.rest = rest;
                o.nOS = v.normalOS;
                return o;
            }

            half4 frag(V2F i) : SV_Target
            {
                NetClip(i.rest, normalize(i.nOS));
                float3 n = normalize(i.normalWS);
            #if defined(_GBUFFER_NORMALS_OCT)
                float2 oct = PackNormalOctQuadEncode(n);
                return half4(PackFloat2To888(saturate(oct * 0.5 + 0.5)), 0.0);
            #else
                return half4(n, 0.0);
            #endif
            }
            ENDHLSL
        }
    }
    FallBack Off
}
