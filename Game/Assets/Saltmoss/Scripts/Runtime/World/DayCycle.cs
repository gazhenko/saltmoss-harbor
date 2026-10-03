using UnityEngine;
using UnityEngine.Rendering;

namespace Saltmoss
{
    /// <summary>
    /// Time of day and weather lighting for the set: the sun lamp (colour, angle, intensity), trilight ambient, fog,
    /// the painted backdrop colours, and the night glow of lamp glass. Keyframed palettes like a lighting desk's cues.
    /// </summary>
    [ExecuteAlways]
    public class DayCycle : MonoBehaviour
    {
        public static DayCycle I { get; private set; }

        [Range(0, 24)] public float hour = 10f;
        [Range(0, 1)] public float overcast;
        [Range(0, 1)] public float storm;
        public Light sun;
        /// <summary>Extra cool rim lamp opposite the sun, as on a stage set.</summary>
        public Light rim;
        /// <summary>Optional override (title screen, trailer): freeze the hour.</summary>
        public bool frozen;
        /// <summary>Extra fog (foggy days).</summary>
        public float fogBoost = 1f;

        struct Cue
        {
            public float h;
            public Color sun; public float sunI; public float elev;
            public Color skyTop, skyHor, skyLow, ambSky, ambEq, ambGround, fog;
            public Color cloud, cloudShadow;
            public float stars, glow;
        }

        static Color C(string hex) { ColorUtility.TryParseHtmlString(hex, out var c); return c; }

        static readonly Cue[] cues =
        {
            new Cue { h = 0f, sun = C("#6f86c9"), sunI = 0.18f, elev = 30f, skyTop = C("#0e1630"), skyHor = C("#2a3c66"), skyLow = C("#1b2747"), ambSky = C("#2c3d6e"), ambEq = C("#1d2a4c"), ambGround = C("#0f1424"), fog = C("#24365b"), cloud = C("#56658f"), cloudShadow = C("#26314f"), stars = 1f, glow = 1f },
            new Cue { h = 5f, sun = C("#7d8fd0"), sunI = 0.2f, elev = 8f, skyTop = C("#1a2550"), skyHor = C("#5d6a9a"), skyLow = C("#2f3a62"), ambSky = C("#3b4a7c"), ambEq = C("#3a4068"), ambGround = C("#171b2e"), fog = C("#4a5784"), cloud = C("#7e86ad"), cloudShadow = C("#3d4469"), stars = 0.6f, glow = 1f },
            new Cue { h = 6.5f, sun = C("#ffb27a"), sunI = 1.1f, elev = 6f, skyTop = C("#5a79b8"), skyHor = C("#f5b48a"), skyLow = C("#c99a8e"), ambSky = C("#8a9dc9"), ambEq = C("#c8a090"), ambGround = C("#4f4740"), fog = C("#e6b49a"), cloud = C("#ffe0c8"), cloudShadow = C("#a88aa3"), stars = 0.0f, glow = 0.6f },
            new Cue { h = 9f, sun = C("#ffe6c4"), sunI = 1.7f, elev = 30f, skyTop = C("#4f86c6"), skyHor = C("#cfe0ea"), skyLow = C("#a8bfcc"), ambSky = C("#9bb8dc"), ambEq = C("#bfc8c8"), ambGround = C("#6b6256"), fog = C("#c4d6e0"), cloud = C("#fff9f0"), cloudShadow = C("#a9b8cf"), stars = 0f, glow = 0f },
            new Cue { h = 13f, sun = C("#fff3e0"), sunI = 1.9f, elev = 52f, skyTop = C("#3f7dc4"), skyHor = C("#cfe3ee"), skyLow = C("#b2c7d2"), ambSky = C("#a3c0e2"), ambEq = C("#c7cfcf"), ambGround = C("#6e665a"), fog = C("#c8dbe5"), cloud = C("#ffffff"), cloudShadow = C("#aab9d0"), stars = 0f, glow = 0f },
            new Cue { h = 16.5f, sun = C("#ffd9a8"), sunI = 1.75f, elev = 28f, skyTop = C("#4b7fbe"), skyHor = C("#ead7bf"), skyLow = C("#c6b8a6"), ambSky = C("#9fb5d6"), ambEq = C("#d2bfa8"), ambGround = C("#6f6252"), fog = C("#ddd0bd"), cloud = C("#fff1dc"), cloudShadow = C("#b3a9b8"), stars = 0f, glow = 0.05f },
            new Cue { h = 19f, sun = C("#ff9a5c"), sunI = 1.2f, elev = 5f, skyTop = C("#4a5a9c"), skyHor = C("#f59a6c"), skyLow = C("#b07a7c"), ambSky = C("#7d86b8"), ambEq = C("#c98a74"), ambGround = C("#4a3c3a"), fog = C("#e59a7c"), cloud = C("#ffc59c"), cloudShadow = C("#8a6f8f"), stars = 0.05f, glow = 0.75f },
            new Cue { h = 20.5f, sun = C("#8a7fd0"), sunI = 0.35f, elev = 12f, skyTop = C("#1d2550"), skyHor = C("#7a5f8a"), skyLow = C("#3a3458"), ambSky = C("#46508a"), ambEq = C("#5a4a6c"), ambGround = C("#1c1a28"), fog = C("#56507a"), cloud = C("#8c7fa6"), cloudShadow = C("#3c3657"), stars = 0.5f, glow = 1f },
            new Cue { h = 24f, sun = C("#6f86c9"), sunI = 0.18f, elev = 30f, skyTop = C("#0e1630"), skyHor = C("#2a3c66"), skyLow = C("#1b2747"), ambSky = C("#2c3d6e"), ambEq = C("#1d2a4c"), ambGround = C("#0f1424"), fog = C("#24365b"), cloud = C("#56658f"), cloudShadow = C("#26314f"), stars = 1f, glow = 1f },
        };

        static readonly int IdTop = Shader.PropertyToID("_SkyTop"), IdHor = Shader.PropertyToID("_SkyHorizon"), IdLow = Shader.PropertyToID("_SkyLow");
        static readonly int IdSun = Shader.PropertyToID("_SunColor"), IdSunDir = Shader.PropertyToID("_SunDirWS"), IdCloud = Shader.PropertyToID("_CloudTint");
        static readonly int IdCloudSh = Shader.PropertyToID("_CloudShadow"), IdStars = Shader.PropertyToID("_StarAmount"), IdOver = Shader.PropertyToID("_Overcast");
        static readonly int IdGlow = Shader.PropertyToID("_NightGlow");

        public float NightGlow { get; private set; }
        public bool IsNight => hour < 6f || hour > 20f;

        void OnEnable() { I = this; }

        void LateUpdate() { Apply(); }

        public void Apply()
        {
            float h = Mathf.Repeat(hour, 24f);
            int i = 0;
            while (i < cues.Length - 2 && cues[i + 1].h <= h) i++;
            var a = cues[i];
            var b = cues[i + 1];
            float t = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(a.h, b.h, h));
            Color L(Color x, Color y) => Color.Lerp(x, y, t);

            // weather: overcast desaturates toward grey-blue, a storm darkens and cools everything
            float ov = Mathf.Clamp01(Mathf.Max(overcast, storm));
            Color grey = new Color(0.52f, 0.56f, 0.6f);
            Color W(Color c, float k = 1f) => Color.Lerp(c, grey * (c.grayscale * 1.25f + 0.2f), ov * 0.75f * k) * (1f - storm * 0.38f);

            Color sunC = L(a.sun, b.sun);
            float sunI = Mathf.Lerp(a.sunI, b.sunI, t) * (1f - ov * 0.62f) * (1f - storm * 0.25f);
            float elev = Mathf.Lerp(a.elev, b.elev, t);
            // the sun's path arcs over the open sea (+Z): east at dawn, over the water at noon, west at dusk
            float dayT = Mathf.InverseLerp(5f, 20.5f, h);
            float az = Mathf.Lerp(80f, -80f, dayT);
            bool moon = h < 5.5f || h > 20.2f;
            if (moon) az = Mathf.Lerp(-30f, 30f, Mathf.Repeat(h + 4f, 24f) / 10f);
            var dir = Quaternion.Euler(elev, az + 180f, 0f) * Vector3.forward;   // direction the light travels
            if (sun != null)
            {
                sun.transform.rotation = Quaternion.LookRotation(dir);
                sun.color = W(sunC, 0.6f);
                sun.intensity = sunI;
                sun.shadowStrength = Mathf.Lerp(0.85f, 0.45f, ov);
            }
            if (rim != null)
            {
                rim.transform.rotation = Quaternion.LookRotation(Vector3.Reflect(dir, Vector3.up) * -1f + Vector3.down * 0.6f);
                rim.color = W(L(a.ambSky, b.ambSky));
                rim.intensity = 0.35f * (1f - ov * 0.4f) + (moon ? 0.15f : 0f);
            }

            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = W(L(a.ambSky, b.ambSky)) * 1.05f;
            RenderSettings.ambientEquatorColor = W(L(a.ambEq, b.ambEq));
            RenderSettings.ambientGroundColor = W(L(a.ambGround, b.ambGround));
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.ExponentialSquared;
            RenderSettings.fogColor = W(L(a.fog, b.fog));
            RenderSettings.fogDensity = (Mathf.Lerp(0.0021f, 0.0062f, ov) + storm * 0.004f) * fogBoost;

            Shader.SetGlobalColor(IdTop, W(L(a.skyTop, b.skyTop)));
            Shader.SetGlobalColor(IdHor, W(L(a.skyHor, b.skyHor)));
            Shader.SetGlobalColor(IdLow, W(L(a.skyLow, b.skyLow)));
            Shader.SetGlobalColor(IdSun, sunC * Mathf.Clamp01(sunI));
            Shader.SetGlobalVector(IdSunDir, -dir);
            Shader.SetGlobalColor(IdCloud, W(L(a.cloud, b.cloud), 0.6f));
            Shader.SetGlobalColor(IdCloudSh, W(L(a.cloudShadow, b.cloudShadow), 0.6f));
            Shader.SetGlobalFloat(IdStars, Mathf.Lerp(a.stars, b.stars, t) * (1f - ov));
            Shader.SetGlobalFloat(IdOver, ov);
            NightGlow = Mathf.Max(Mathf.Lerp(a.glow, b.glow, t), storm * 0.6f);
            Shader.SetGlobalFloat(IdGlow, NightGlow);
        }
    }
}
