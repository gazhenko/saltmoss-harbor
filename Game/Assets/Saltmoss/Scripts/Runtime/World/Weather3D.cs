using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// The day's weather on the set: overcast and storm on the lighting desk (rougher further out to sea), glass-bead
    /// rain around the camera stepped on twos, and the wind that carries the cotton smoke.
    /// </summary>
    public class Weather3D : MonoBehaviour
    {
        ParticleSystem rain;
        ParticleSystem.EmitParams ep;
        float rainAmount, overcast, storm;

        void Start()
        {
            var go = new GameObject("Rain");
            go.transform.SetParent(transform, false);
            rain = go.AddComponent<ParticleSystem>();
            rain.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = rain.main;
            main.loop = true;
            main.startLifetime = 1.2f;
            main.startSpeed = 0f;
            main.startSize3D = true;
            main.startSizeX = 0.025f;
            main.startSizeY = 0.6f;
            main.startSizeZ = 1f;
            main.maxParticles = 3000;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.playOnAwake = false;
            var shape = rain.shape;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = new Vector3(40f, 1f, 40f);
            var vel = rain.velocityOverLifetime;
            vel.enabled = true;
            vel.space = ParticleSystemSimulationSpace.World;
            vel.x = new ParticleSystem.MinMaxCurve(-2f);
            vel.y = new ParticleSystem.MinMaxCurve(-16f);
            vel.z = new ParticleSystem.MinMaxCurve(-1.2f);
            var em = rain.emission;
            em.rateOverTime = 0f;
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.renderMode = ParticleSystemRenderMode.Stretch;
            r.velocityScale = 0.035f;
            r.lengthScale = 1.2f;
            r.sharedMaterial = Resources.Load<Material>("Rain");
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            rain.Play();
        }

        void Update()
        {
            var D = GameState.D;
            var w = (Weather)D.weather;
            var p = PlayerController.I;
            float rough = p != null && SeaState.I != null ? SeaState.I.Roughness01(p.transform.position) : 0f;
            float wantOver = w == Weather.Clear ? 0.05f : w == Weather.Breezy ? 0.2f : w == Weather.Showers ? 0.6f : w == Weather.Fog ? 0.8f : w == Weather.Squalls ? 0.7f : 0.9f;
            float wantStorm = w == Weather.Storm ? 0.4f + rough * 0.6f : w == Weather.Squalls ? rough * 0.6f : 0f;
            float wantRain = w == Weather.Showers ? 0.45f : w == Weather.Squalls ? 0.35f + rough * 0.5f : w == Weather.Storm ? 0.6f + rough * 0.4f : 0f;
            // the Grey Deep is always a bit wilder
            wantOver = Mathf.Max(wantOver, rough * 0.4f);
            if (TitleScreen.Showing) { wantOver = 0.1f; wantStorm = 0f; wantRain = 0f; }
            float k = Time.deltaTime * 0.15f;
            overcast = Mathf.MoveTowards(overcast, wantOver, k);
            storm = Mathf.MoveTowards(storm, wantStorm, k);
            rainAmount = Mathf.MoveTowards(rainAmount, wantRain, k);
            var dc = DayCycle.I;
            if (dc != null) { dc.overcast = overcast; dc.storm = storm; }
            CottonPuff.Wind = new Vector3(-0.6f, 0f, -0.4f) * (1f + storm * 3f + (w == Weather.Breezy ? 1f : 0f));
            if (dc != null) dc.fogBoost = Mathf.MoveTowards(dc.fogBoost, w == Weather.Fog && !TitleScreen.Showing ? 2.4f : 1f, Time.deltaTime * 0.2f);

            var cam = Camera.main;
            if (rain == null || cam == null) return;
            rain.transform.position = cam.transform.position + cam.transform.forward * 8f + Vector3.up * 12f;
            var em = rain.emission;
            em.rateOverTime = rainAmount * 2400f;
            // rain is animated like everything else: one exposure at a time
            if (ClayClock.Fps > 0)
            {
                if (rain.isPlaying) rain.Pause();
                if (ClayClock.SteppedThisFrame) rain.Simulate(ClayClock.StepDt, true, false, false);
            }
            else if (!rain.isPlaying) rain.Play();
        }
    }
}
