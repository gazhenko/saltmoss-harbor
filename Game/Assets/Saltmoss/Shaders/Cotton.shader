// Cotton wool (clouds, chimney smoke, spray): fibrous, very soft wrap lighting, fuzzy alpha-to-coverage silhouette
// that re-teases every stop-motion step.
Shader "Saltmoss/Cotton"
{
    Properties
    {
        [MainColor] _BaseColor ("Tint", Color) = (1, 1, 1, 1)
        _VertexColor ("Use vertex colour", Range(0, 1)) = 1
        _RestFromUV1 ("Rest position in UV1", Float) = 1
        _Fuzz ("Fuzz", Range(0, 2)) = 1
        _FiberScale ("Fibre scale", Float) = 40
        _Puff ("Puff displacement (m)", Float) = 0.03
        _Wrap ("Wrap", Range(0, 1)) = 0.8
        _Shade ("Self shading", Range(0, 1)) = 0.45
        _Opacity ("Opacity", Range(0, 1)) = 1
    }
    SubShader
    {
        Tags { "RenderType" = "TransparentCutout" "RenderPipeline" = "UniversalPipeline" "Queue" = "AlphaTest" }

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
        #include "ClayCommon.hlsl"
        CBUFFER_START(UnityPerMaterial)
            half4 _BaseColor;
            half _VertexColor;
            float _RestFromUV1;
            half _Fuzz;
            float _FiberScale;
            float _Puff;
            half _Wrap;
            half _Shade;
            half _Opacity;
        CBUFFER_END

        struct CA { float4 positionOS : POSITION; float3 normalOS : NORMAL; half4 color : COLOR; float3 rest : TEXCOORD1; UNITY_VERTEX_INPUT_INSTANCE_ID };

        float3 CRest(CA v) { return _RestFromUV1 > 0.5 ? v.rest : v.positionOS.xyz; }

        float3 CDeform(CA v, float3 rest)
        {
            float fr = _ClayFrame;
            float n = ClayNoise3(rest * 3.1 + float3(ClayHash11(fr) * 13.0, ClayHash11(fr + 3.0) * 7.0, 0)) - 0.5;
            return v.positionOS.xyz + v.normalOS * (n * _Puff * (0.4 + 0.6 * _ClayBoil));
        }

        // wispy fibres: stretched noise, re-teased every step
        half Fibres(float3 rest)
        {
            float o = ClayHash11(_ClayFrame) * 5.0 * _ClayBoil;
            half a = ClayNoise3(rest * float3(_FiberScale, _FiberScale * 0.35, _FiberScale) + o);
            half b = ClayNoise3(rest * float3(_FiberScale * 0.4, _FiberScale * 1.3, _FiberScale * 0.6) + 17.0 + o);
            return a * 0.6h + b * 0.4h;
        }

        half CottonAlpha(float3 rest, half3 nWS, float3 posWS)
        {
            half3 V = GetWorldSpaceNormalizeViewDir(posWS);
            half rim = saturate(abs(dot(nWS, V)));
            half f = Fibres(rest);
            return saturate((rim * 2.4h - 0.35h + (f - 0.5h) * 1.5h * _Fuzz) * _Opacity * 1.6h);
        }
        ENDHLSL

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            AlphaToMask On
            Cull Back
            HLSLPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            #pragma multi_compile_fog
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            struct V { float4 positionCS : SV_POSITION; float3 positionWS : TEXCOORD0; half3 normalWS : TEXCOORD1; float3 rest : TEXCOORD2; half4 color : TEXCOORD3; half fog : TEXCOORD4; };

            V vert(CA v)
            {
                V o;
                UNITY_SETUP_INSTANCE_ID(v);
                float3 rest = CRest(v);
                VertexPositionInputs p = GetVertexPositionInputs(CDeform(v, rest));
                o.positionCS = p.positionCS;
                o.positionWS = p.positionWS;
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.rest = rest;
                o.color = v.color;
                o.fog = ComputeFogFactor(p.positionCS.z);
                return o;
            }

            half4 frag(V i) : SV_Target
            {
                half3 n = normalize(i.normalWS);
                half a = CottonAlpha(i.rest, n, i.positionWS);
                clip(a - 0.02h);
                half3 base = lerp(half3(1, 1, 1), ClaySrgbToLinear(i.color.rgb), _VertexColor) * _BaseColor.rgb;
                half f = Fibres(i.rest);
                base *= 0.88h + f * 0.2h;
                Light L = GetMainLight(TransformWorldToShadowCoord(i.positionWS));
                half ndl = dot(n, L.direction);
                half diff = pow(saturate((ndl + _Wrap) / (1.0h + _Wrap)), 1.4h);
                half sh = lerp(1.0h, L.shadowAttenuation, 0.7h);
                half3 lit = L.color * diff * sh * lerp(1.0h, f * 1.2h, _Shade);
                half3 amb = SampleSH(n) * (0.75h + 0.25h * f);
                half3 c = base * (lit + amb);
                c = MixFog(c, i.fog);
                return half4(c, a);
            }
            ENDHLSL
        }

        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode" = "ShadowCaster" }
            ZWrite On
            ColorMask 0
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl"
            float3 _LightDirection;
            struct V { float4 positionCS : SV_POSITION; float3 rest : TEXCOORD0; };
            V vert(CA v)
            {
                V o;
                UNITY_SETUP_INSTANCE_ID(v);
                float3 rest = CRest(v);
                float3 ws = TransformObjectToWorld(CDeform(v, rest));
                float4 cs = TransformWorldToHClip(ApplyShadowBias(ws, TransformObjectToWorldNormal(v.normalOS), _LightDirection));
            #if UNITY_REVERSED_Z
                cs.z = min(cs.z, UNITY_NEAR_CLIP_VALUE);
            #else
                cs.z = max(cs.z, UNITY_NEAR_CLIP_VALUE);
            #endif
                o.positionCS = cs;
                o.rest = rest;
                return o;
            }
            half4 frag(V i) : SV_Target { clip(Fibres(i.rest) - 0.35h); return 0; }
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
            #pragma multi_compile_instancing
            struct V { float4 positionCS : SV_POSITION; float3 positionWS : TEXCOORD0; half3 n : TEXCOORD1; float3 rest : TEXCOORD2; };
            V vert(CA v)
            {
                V o;
                UNITY_SETUP_INSTANCE_ID(v);
                float3 rest = CRest(v);
                float3 ws = TransformObjectToWorld(CDeform(v, rest));
                o.positionCS = TransformWorldToHClip(ws);
                o.positionWS = ws;
                o.n = TransformObjectToWorldNormal(v.normalOS);
                o.rest = rest;
                return o;
            }
            half frag(V i) : SV_Target { clip(CottonAlpha(i.rest, normalize(i.n), i.positionWS) - 0.5h); return i.positionCS.z; }
            ENDHLSL
        }
    }
    FallBack Off
}
