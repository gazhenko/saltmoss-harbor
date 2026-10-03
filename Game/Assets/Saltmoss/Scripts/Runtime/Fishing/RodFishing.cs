using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Line fishing, Animal Crossing style: fish shadows (dark clay silhouettes under the varnish) cruise near the
    /// boat; cast the bobber near one, wait through the nibbles, and press on the real bite. Big fish fight back:
    /// hold to reel, ease off when the line is too tight. Missing a bite costs nothing but the fish.
    /// </summary>
    public class RodFishing : MonoBehaviour
    {
        public static RodFishing I { get; private set; }
        public bool Fishing { get; private set; }

        class Shadow
        {
            public ItemDef def;
            public Transform t;
            public Vector3 vel;
            public float size;
            public bool chasing;
        }

        readonly List<Shadow> shadows = new List<Shadow>();
        Material shadowMat;
        float spawnTimer;
        Transform bobber;
        System.Random rng = new System.Random();

        void Awake() { I = this; }

        void Start()
        {
            shadowMat = Resources.Load<Material>("FishShadow");
        }

        static float SizeOf(ShadowSize s) => s switch
        {
            ShadowSize.Tiny => 0.35f, ShadowSize.Small => 0.55f, ShadowSize.Medium => 0.85f,
            ShadowSize.Large => 1.25f, ShadowSize.Huge => 1.9f, _ => 2.4f,
        };

        void Update()
        {
            var boat = BoatController.I;
            if (boat == null || SeaState.I == null) return;
            bool active = boat.Aboard && !boat.Docked;
            spawnTimer -= Time.deltaTime;
            if (active && spawnTimer <= 0f && shadows.Count < 5)
            {
                spawnTimer = Random.Range(4f, 9f);
                Spawn(boat);
            }
            for (int i = shadows.Count - 1; i >= 0; i--)
            {
                var s = shadows[i];
                if (!active || Vector3.Distance(s.t.position, boat.transform.position) > 45f) { Destroy(s.t.gameObject); shadows.RemoveAt(i); continue; }
                if (!s.chasing)
                {
                    if (Random.value < Time.deltaTime * 0.4f) s.vel = Quaternion.Euler(0, Random.Range(-70f, 70f), 0) * s.vel;
                    s.t.position += s.vel * Time.deltaTime;
                }
                var p = s.t.position;
                p.y = SeaState.I.HeightAt(p.x, p.z) + 0.04f;
                if (ClayClock.SteppedThisFrame)
                {
                    s.t.position = p;
                    if (s.vel.sqrMagnitude > 0.001f) s.t.rotation = Quaternion.LookRotation(s.vel) * Quaternion.Euler(90f, 0, Mathf.Sin(Time.time * 6f) * 12f);
                }
            }
        }

        void Spawn(BoatController boat)
        {
            bool night = DayCycle.I != null && DayCycle.I.IsNight;
            float storm = GameState.D.weather >= (int)Weather.Squalls ? 1f : 0f;
            var zone = boat.ZoneAt(boat.transform.position);
            var def = Catalog.Roll(Kind.Fish, zone, night, storm, rng, GameState.D.restoration * 0.25f);
            if (def == null) return;
            var ang = Random.Range(0f, 360f);
            var pos = boat.transform.position + Quaternion.Euler(0, ang, 0) * Vector3.forward * Random.Range(8f, 20f);
            var go = GameObject.CreatePrimitive(PrimitiveType.Quad);
            Destroy(go.GetComponent<Collider>());
            go.name = "FishShadow";
            go.GetComponent<Renderer>().sharedMaterial = shadowMat;
            go.GetComponent<Renderer>().shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            float sz = SizeOf(def.shadow);
            go.transform.localScale = def.shadow == ShadowSize.Long ? new Vector3(sz * 0.25f, sz * 1.4f, 1f) : new Vector3(sz * 0.45f, sz, 1f);
            go.transform.position = pos;
            shadows.Add(new Shadow { def = def, t = go.transform, vel = Quaternion.Euler(0, Random.Range(0, 360f), 0) * Vector3.forward * Random.Range(0.3f, 0.9f), size = sz });
        }

        public bool CanCast(BoatController boat) => !Fishing && Mathf.Abs(boat.Speed) < 1.4f && !boat.Busy;

        public void Cast(BoatController boat)
        {
            if (Fishing) return;
            StartCoroutine(CastCo(boat));
        }

        IEnumerator CastCo(BoatController boat)
        {
            Fishing = true;
            boat.Busy = true;
            var p = PlayerController.I;
            p.MoveAboard(boat.rail != null ? boat.rail : boat.helm, Activity.Cast);
            // aim: toward the nearest shadow in front of the camera, else straight out
            var cam = Camera.main.transform;
            var fwd = Vector3.ProjectOnPlane(cam.forward, Vector3.up).normalized;
            Vector3 origin = boat.rail != null ? boat.rail.position : boat.transform.position;
            Vector3 target = origin + fwd * 8f;
            Shadow aim = null;
            float best = 999f;
            foreach (var s in shadows)
            {
                var d = s.t.position - origin;
                d.y = 0f;
                float ang = Vector3.Angle(fwd, d);
                if (ang < 50f && d.magnitude < 22f && ang + d.magnitude < best) { best = ang + d.magnitude; aim = s; }
            }
            if (aim != null) target = aim.t.position + (origin - aim.t.position).normalized * 1.2f;
            for (float t = 0; t < 0.55f; t += Time.deltaTime) { p.anim.activityPhase = t / 0.55f; yield return null; }
            AudioDirector.Play("cast_whoosh", origin, 0.8f);
            if (bobber == null)
            {
                bobber = ModelBank.I.Spawn("boat/bobber", origin, Quaternion.identity).transform;
                bobber.gameObject.AddComponent<ClayPuppet>();
            }
            bobber.gameObject.SetActive(true);
            // arc out
            for (float t = 0; t < 1f; t += Time.deltaTime / 0.6f)
            {
                var pos = Vector3.Lerp(origin, target, t) + Vector3.up * Mathf.Sin(t * Mathf.PI) * 3f;
                bobber.position = pos;
                yield return null;
            }
            AudioDirector.Play("bobber_plop", target, 0.8f);
            SeaState.AddFoam(target, 0.8f, 1f);
            p.anim.activity = Activity.Reel;
            float wait = 0f, nibbleAt = Random.Range(1.5f, 3.5f);
            int nibbles = 0, nibbleCount = Random.Range(1, 4);
            Shadow fish = null;
            bool bite = false, hooked = false;
            float biteWindow = 0f;
            while (true)
            {
                float dt = Time.deltaTime;
                wait += dt;
                var bp = bobber.position;
                float h = SeaState.I.HeightAt(bp.x, bp.z);
                float dip = 0f;
                // a shadow notices the bobber
                if (fish == null)
                    foreach (var s in shadows)
                        if (Vector3.Distance(s.t.position, bp) < 6f) { fish = s; fish.chasing = true; break; }
                if (fish != null)
                {
                    var to = bp - fish.t.position;
                    to.y = 0f;
                    if (to.magnitude > fish.size * 0.45f)
                    {
                        fish.vel = to.normalized * 0.8f;
                        fish.t.position += fish.vel * dt;
                    }
                    else if (wait > nibbleAt)
                    {
                        if (nibbles < nibbleCount)
                        {
                            nibbles++;
                            nibbleAt = wait + Random.Range(0.9f, 2.2f);
                            AudioDirector.Play("nibble", bp, 0.7f);
                            dip = 0.08f;
                        }
                        else if (!bite)
                        {
                            bite = true;
                            biteWindow = 0.75f;
                            AudioDirector.Play("bite_splash", bp, 1f);
                            SeaState.AddFoam(bp, 1.2f, 1f);
                            GameInput.Impulse(0.5f, 0.5f, 0.25f);
                            BubbleText.Show(bp + Vector3.up * 1.2f, "!", 0.8f);
                        }
                    }
                }
                if (bite) { biteWindow -= dt; dip = 0.35f; }
                if (ClayClock.SteppedThisFrame) bobber.position = new Vector3(bp.x, h + 0.05f - dip, bp.z);
                HUD.ActionPrompt = bite ? "Hook it!" : "Reel in";
                HUD.ActionKey = "UseTool";
                if (GameInput.UseTool.WasPressedThisFrame())
                {
                    hooked = bite && biteWindow > 0f;
                    break;
                }
                if (bite && biteWindow <= 0f) break;
                if (Mathf.Abs(boat.Speed) > 1.6f || GameInput.Pause.WasPressedThisFrame()) break;
                yield return null;
            }
            bool caught = false;
            if (hooked && fish != null)
            {
                AudioDirector.Play("fish_splash", bobber.position, 1f);
                if (fish.def.shadow >= ShadowSize.Large)
                {
                    yield return Reel(boat, fish);
                    caught = reelWon;
                    if (!caught) GameState.Say("It wriggled free! So close…");
                }
                else caught = true;
            }
            else if (bite) GameState.Say(fish != null && fish.def.shadow >= ShadowSize.Large ? "Whoa, it got away! Something big…" : "It got away! Wait for the big tug.");
            if (fish != null)
            {
                shadows.Remove(fish);
                Destroy(fish.t.gameObject);
            }
            AudioDirector.Play("reel_loop", origin, 0.5f);
            for (float t = 0; t < 1f; t += Time.deltaTime / 0.4f)
            {
                bobber.position = Vector3.Lerp(bobber.position, origin, t);
                yield return null;
            }
            bobber.gameObject.SetActive(false);
            p.MoveAboard(boat.helm, Activity.Helm);
            boat.Busy = false;
            Fishing = false;
            if (caught)
            {
                AudioDirector.Play("fish_flop", origin, 0.9f);
                GameState.Catch(fish.def);
                if (!GameState.Flag("caught_fish")) GameState.SetFlag("caught_fish");
            }
        }

        bool reelWon;

        /// <summary>Big fish: hold to reel (progress), but the line tension climbs; release before it maxes.</summary>
        IEnumerator Reel(BoatController boat, Shadow fish)
        {
            var ui = MiniGameUI.Ensure();
            string key = GameInput.Label(Bind.UseTool);
            ui.Show("REEL!", $"Hold {key} to reel · let go when it's too tight", "snap!", "slack");
            float tension = 0.3f, progress = 0.25f, t = 0f;
            float strength = fish.def.shadow == ShadowSize.Huge ? 1.4f : fish.def.shadow == ShadowSize.Long ? 1.6f : 1.1f;
            reelWon = false;
            var p = PlayerController.I;
            while (progress < 1f)
            {
                float dt = Time.deltaTime;
                t += dt;
                bool hold = GameInput.UseTool.IsPressed();
                float surge = Mathf.Max(0f, Mathf.Sin(t * 2.3f) + Mathf.Sin(t * 5.1f) * 0.4f) * strength;
                tension = Mathf.Clamp01(tension + (hold ? 0.55f + surge * 0.5f : -0.9f) * dt);
                if (hold && tension < 0.85f) progress += dt * 0.28f / strength;
                if (!hold) progress -= dt * 0.06f * surge;
                if (tension >= 0.99f)
                {
                    // the line holds, but the fish takes some back
                    progress = Mathf.Max(0f, progress - 0.25f);
                    tension = 0.55f;
                    AudioDirector.Play("winch_strain", boat.transform.position, 0.6f);
                    GameInput.Impulse(0.4f, 0.6f, 0.3f);
                }
                p.anim.activityPhase = t;
                ui.Set(0.42f, 0.84f, tension, progress, tension < 0.85f);
                if (bobber != null && ClayClock.SteppedThisFrame) SeaState.AddFoam(bobber.position, 1f + surge * 0.5f, 0.9f);
                if (t > 20f) break;
                yield return null;
            }
            ui.Hide();
            reelWon = progress >= 1f;
        }
    }
}
