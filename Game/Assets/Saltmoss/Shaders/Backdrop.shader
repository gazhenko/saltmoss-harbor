// The painted cyclorama behind the set: a gouache sky gradient on paper, painted cloud bands, a soft sun, and at
// night little glitter-bead stars. Colours come from DayCycle (global _Sky* properties).
Shader "Saltmoss/Backdrop"
{
    Properties
    {
        [NoScaleOffset] _Clouds ("Painted clouds (RGBA, tiles around)", 2D) = "black" {}
        [NoScaleOffset] _Paper ("Paper grain", 2D) = "grey" {}
        _CloudRepeat ("Cloud strip repeats", Float) = 3
        _CloudHeight ("Cloud band (min, max) on the wall", Vector) = (0.02, 0.32, 0, 0)
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry+50" }
        Pass
        {
            Name "Backdrop"
            Tags { "LightMode" = "UniversalForward" }
            Cull Front
            ZWrite On
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "ClayCommon.hlsl"

            TEXTURE2D(_Clouds); SAMPLER(sampler_Clouds);
            TEXTURE2D(_Paper); SAMPLER(sampler_Paper);
            half4 _SkyTop, _SkyHorizon, _SkyLow, _SunColor, _CloudTint, _CloudShadow;
            float4 _SunDirWS;
            half _StarAmount, _Overcast;
            CBUFFER_START(UnityPerMaterial)
                float _CloudRepeat;
                float4 _CloudHeight;
            CBUFFER_END

            struct A { float4 positionOS : POSITION; };
            struct V { float4 positionCS : SV_POSITION; float3 dir : TEXCOORD0; };

            V vert(A v)
            {
                V o;
                float3 ws = TransformObjectToWorld(v.positionOS.xyz);
                o.positionCS = TransformWorldToHClip(ws);
                o.dir = normalize(ws - GetCameraPositionWS());
                return o;
            }

            half4 frag(V i) : SV_Target
            {
                float3 d = normalize(i.dir);
                float el = d.y;                                   // -1..1
                float az = atan2(d.x, d.z) / (2.0 * PI) + 0.5;    // 0..1 around
                half3 sky = el > 0 ? lerp(_SkyHorizon.rgb, _SkyTop.rgb, pow(saturate(el * 1.6), 0.7)) : lerp(_SkyHorizon.rgb, _SkyLow.rgb, saturate(-el * 6.0));
                // brush-stroke unevenness in the wash
                half wash = ClayNoise3(float3(az * 60.0, el * 18.0, 1.0)) - 0.5h + (ClayNoise3(float3(az * 220.0, el * 70.0, 5.0)) - 0.5h) * 0.35h;
                sky *= 1.0h + wash * 0.06h;
                // sun: a soft painted disc and glow
                half sd = dot(d, normalize(_SunDirWS.xyz));
                sky += _SunColor.rgb * (pow(saturate(sd), 300.0) * 1.3h + pow(saturate(sd), 12.0) * 0.25h) * (1.0h - _Overcast * 0.8h);
                // stars: little glitter beads
                float2 sg = float2(az * 420.0, el * 140.0);
                float2 cell = floor(sg);
                float2 fpos = frac(sg) - 0.5;
                float h = ClayHash13(float3(cell, 4.0));
                half star = h > 0.985 ? smoothstep(0.18, 0.0, length(fpos + (float2(ClayHash13(float3(cell, 1)), ClayHash13(float3(cell, 2))) - 0.5) * 0.5)) : 0;
                star *= saturate(el * 4.0) * _StarAmount * (0.6h + 0.4h * sin(_ClayFrame * 1.7 + h * 50.0));
                sky += star.xxx * 1.4h;
                // painted cloud band
                float cv = (el - _CloudHeight.x) / max(_CloudHeight.y - _CloudHeight.x, 1e-3);
                if (cv > 0 && cv < 1)
                {
                    half4 cl = SAMPLE_TEXTURE2D(_Clouds, sampler_Clouds, float2(az * _CloudRepeat, cv));
                    half3 cc = lerp(_CloudShadow.rgb, _CloudTint.rgb, cl.r);
                    sky = lerp(sky, cc, cl.a * (0.75h + _Overcast * 0.25h));
                }
                sky = lerp(sky, lerp(_SkyHorizon.rgb, _CloudShadow.rgb, 0.5h), _Overcast * 0.45h * saturate(el * 3.0 + 0.3));
                half paper = SAMPLE_TEXTURE2D(_Paper, sampler_Paper, float2(az * 24.0, el * 8.0)).r;
                sky *= 0.94h + paper * 0.12h;
                return half4(sky, 1);
            }
            ENDHLSL
        }
    }
    FallBack Off
}
