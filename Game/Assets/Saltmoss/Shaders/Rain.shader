// Glass-bead rain: thin pale streaks (stretched billboards), lit by the sky colour.
Shader "Saltmoss/Rain"
{
    Properties { _Color ("Colour", Color) = (0.85, 0.9, 1, 0.45) }
    SubShader
    {
        Tags { "RenderType" = "Transparent" "Queue" = "Transparent" "RenderPipeline" = "UniversalPipeline" }
        Pass
        {
            Tags { "LightMode" = "UniversalForward" }
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            Cull Off
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            CBUFFER_START(UnityPerMaterial)
                half4 _Color;
            CBUFFER_END
            half4 _SkyHorizon;
            struct A { float4 positionOS : POSITION; float2 uv : TEXCOORD0; half4 color : COLOR; };
            struct V { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; half4 color : COLOR; };
            V vert(A v) { V o; o.positionCS = TransformObjectToHClip(v.positionOS.xyz); o.uv = v.uv; o.color = v.color; return o; }
            half4 frag(V i) : SV_Target
            {
                float x = abs(i.uv.x - 0.5) * 2.0;
                half a = saturate(1.0 - x * x * 1.6) * saturate(sin(i.uv.y * 3.14159)) * _Color.a * i.color.a;
                half3 c = lerp(_Color.rgb, _SkyHorizon.rgb + 0.35, 0.5);
                return half4(c, a);
            }
            ENDHLSL
        }
    }
}
