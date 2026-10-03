// A soft dark fish silhouette lying just under the varnished sea: an ellipse with a tail notch, multiplied in.
Shader "Saltmoss/ShadowBlob"
{
    Properties
    {
        _Color ("Colour", Color) = (0.04, 0.1, 0.12, 0.55)
    }
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
            struct A { float4 positionOS : POSITION; float2 uv : TEXCOORD0; };
            struct V { float4 positionCS : SV_POSITION; float2 uv : TEXCOORD0; };
            V vert(A v) { V o; o.positionCS = TransformObjectToHClip(v.positionOS.xyz); o.uv = v.uv; return o; }
            half4 frag(V i) : SV_Target
            {
                float2 p = i.uv * 2.0 - 1.0;              // y = along the body (head at +1)
                float body = length(float2(p.x * 1.05, (p.y - 0.12) * 1.25));
                float tail = length(float2(p.x * 2.2, (p.y + 0.82) * 3.0));
                float d = min(body, tail);
                half a = saturate((1.0 - d) * 3.0) * _Color.a;
                return half4(_Color.rgb, a);
            }
            ENDHLSL
        }
    }
}
