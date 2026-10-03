using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Treasure dredging: glimmering patches of water mark something shiny on the seabed (the sonar set pings them
    /// and reads out their depth). Stop over one, pay out the dredge chain to the right depth and crank it back up:
    /// treasure, sea glass, or — if you were way off — an old boot.
    /// </summary>
    public class Dredge : MonoBehaviour
    {
        public static Dredge I { get; private set; }

        class Glimmer
        {
            public Vector3 pos;
            public float depth;
            public float age, life;
            public Transform fx;
            public Zone zone;
        }

        readonly List<Glimmer> glimmers = new List<Glimmer>();
        float spawnTimer = 3f, pingTimer;
        public bool Working { get; private set; }
        readonly System.Random rng = new System.Random();
        public Vector3 wreck = new Vector3(-120f, 0f, 560f);

        void Awake() { I = this; }

        void Update()
        {
            var boat = BoatController.I;
            if (boat == null) return;
            bool atSea = boat.Aboard && !boat.Docked && !boat.InHarbour;
            spawnTimer -= Time.deltaTime;
            int max = GameState.Has("sonar") ? 4 : 3;
            if (atSea && spawnTimer <= 0f && glimmers.Count < max)
            {
                spawnTimer = Random.Range(10f, 22f) * (GameState.Has("sonar") ? 0.7f : 1f);
                // near the wreck, treasure gathers
                bool nearWreck = Vector3.Distance(boat.transform.position, wreck) < 180f;
                var c = nearWreck && Random.value < 0.6f ? wreck : boat.transform.position;
                var pos = c + Quaternion.Euler(0, Random.Range(0, 360f), 0) * Vector3.forward * Random.Range(25f, 70f);
                if (Vector2.Distance(new Vector2(pos.x, pos.z), boat.harbourMouth) > boat.worldRadius - 20f) return;
                var z = boat.ZoneAt(pos);
                var g = new Glimmer { pos = pos, depth = z == Zone.Shallows ? Random.Range(8f, 30f) : z == Zone.Kelp ? Random.Range(20f, 60f) : Random.Range(45f, 95f), life = Random.Range(150f, 260f), zone = z };
                var fx = new GameObject("Glimmer").transform;
                fx.position = pos;
                g.fx = fx;
                glimmers.Add(g);
            }
            for (int i = glimmers.Count - 1; i >= 0; i--)
            {
                var g = glimmers[i];
                g.age += Time.deltaTime;
                if (g.age > g.life || !atSea && !Working)
                {
                    if (g.fx) Destroy(g.fx.gameObject);
                    glimmers.RemoveAt(i);
                    continue;
                }
                if (ClayClock.SteppedThisFrame && SeaState.I != null)
                {
                    // glitter: a few white beads of sparkle that change every exposure
                    if (Random.value < 0.35f)
                    {
                        var sp = g.pos + new Vector3(Random.Range(-1.5f, 1.5f), 0f, Random.Range(-1.5f, 1.5f));
                        sp.y = SeaState.I.HeightAt(sp.x, sp.z) + 0.1f;
                        CottonPuff.Emit(sp, new Color(1.6f, 1.55f, 1.3f), 0.18f, new Vector3(0f, 0.5f, 0f), 0.35f);
                    }
                    SeaState.AddFoam(g.pos, 1.6f, 0.35f + Mathf.PingPong(Time.time, 0.3f));
                }
            }
            // the sonar set pings the nearest find
            if (GameState.Has("sonar") && atSea)
            {
                pingTimer -= Time.deltaTime;
                var n = Nearest(boat.transform.position, 120f);
                if (n != null && pingTimer <= 0f)
                {
                    float d = Vector3.Distance(n.pos, boat.transform.position);
                    pingTimer = Mathf.Lerp(0.8f, 3.5f, d / 120f);
                    AudioDirector.UI("sonar_ping", Mathf.Lerp(0.6f, 0.15f, d / 120f), 0f);
                }
            }
        }

        Glimmer Nearest(Vector3 p, float range)
        {
            Glimmer best = null;
            float bd = range;
            foreach (var g in glimmers)
            {
                float d = Vector3.Distance(new Vector3(p.x, 0, p.z), g.pos);
                if (d < bd) { bd = d; best = g; }
            }
            return best;
        }

        public bool CanDredge(BoatController boat) => !Working && Mathf.Abs(boat.Speed) < 1.8f && Nearest(boat.transform.position, 9f) != null;

        public void Lower(BoatController boat)
        {
            var g = Nearest(boat.transform.position, 9f);
            if (g == null || Working) return;
            StartCoroutine(Run(boat, g));
        }

        IEnumerator Run(BoatController boat, Glimmer g)
        {
            Working = true;
            boat.Busy = true;
            var p = PlayerController.I;
            p.MoveAboard(boat.winch != null ? boat.winch : boat.helm, Activity.Crank);
            var ui = MiniGameUI.Ensure();
            bool sonar = GameState.Has("sonar");
            string key = GameInput.Label(Bind.UseTool), stop = GameInput.Label(Bind.Interact);
            ui.Show("DREDGE", $"Hold {key} to let out chain · {stop} to haul up", "surface", "100 m");
            float target = g.depth / 100f;
            float window = sonar ? 0.05f : 0.09f;
            float depth = 0f;
            AudioDirector.Play("dredge_drop", boat.transform.position, 1f);
            SeaState.AddFoam(boat.transform.position - boat.transform.right * 3f, 2f, 1f);
            float t = 0f;
            var chain = gameObject.AddComponent<AudioSource>();
            chain.clip = AudioDirector.Bank.Get("chain_rattle");
            chain.loop = true;
            if (chain.clip != null) chain.Play();
            chain.volume = 0f;
            while (true)
            {
                t += Time.deltaTime;
                bool lower = GameInput.UseTool.IsPressed();
                if (lower) depth = Mathf.Min(1f, depth + Time.deltaTime * 0.16f);
                chain.volume = (lower ? 0.5f : 0f) * Settings.Sfx;
                p.anim.activityPhase = lower ? Mathf.Repeat(t * 2f, 1f) : p.anim.activityPhase;
                // the gauge reads top = surface: invert for display
                float shown = 1f - depth;
                float tShown = 1f - target;
                ui.Set(tShown, sonar ? window * 2f : window * 3.2f, shown, depth, Mathf.Abs(depth - target) < window);
                ui.Marker(tShown, true);
                ui.Hint(sonar ? $"Sonar: {g.depth:0} m — you're at {depth * 100f:0} m" : $"Somewhere around {Mathf.Round(g.depth / 10f) * 10f:0} m… you're at {depth * 100f:0} m");
                if (GameInput.Interact.WasPressedThisFrame() && depth > 0.03f) break;
                if (GameInput.Pause.WasPressedThisFrame()) { depth = 0f; break; }
                yield return null;
            }
            Destroy(chain);
            ui.Hint("Cranking up…");
            AudioDirector.Play("dredge_up", boat.transform.position, 1f);
            for (float c = 0; c < 1f; c += Time.deltaTime / 2.2f)
            {
                p.anim.activityPhase = Mathf.Repeat(c * 4f, 1f);
                ui.Set(1f - target, 0f, 1f - depth * (1f - c), depth, false);
                yield return null;
            }
            ui.Hide();
            SeaState.AddFoam(boat.transform.position - boat.transform.right * 3f, 2.4f, 1f);
            for (int i = 0; i < 6; i++) CottonPuff.Emit(boat.transform.position - boat.transform.right * 3f + Random.insideUnitSphere * 0.5f, Color.white, 0.4f, new Vector3(Random.Range(-1f, 1f), Random.Range(1.5f, 3f), Random.Range(-1f, 1f)), 0.8f);
            float err = Mathf.Abs(depth - target);
            ItemDef found;
            bool night = DayCycle.I != null && DayCycle.I.IsNight;
            float luck = GameState.D.restoration * 0.3f + (Vector3.Distance(g.pos, wreck) < 120f ? 1.2f : 0f);
            if (depth < 0.03f) found = null;
            else if (err < window) found = Catalog.Roll(Kind.Treasure, g.zone, night, 0f, rng, luck + 0.6f);
            else if (err < window * 2.5f) found = rng.NextDouble() < 0.6 ? Catalog.Get("sea_glass") : Catalog.Roll(Kind.Treasure, g.zone, night, 0f, rng, 0f);
            else found = Catalog.Roll(Kind.Junk, g.zone, night, 0f, rng);
            // the first dredge always brings up something nice for the museum
            if (!GameState.Flag("dredged") && found != null && found.kind == Kind.Junk) found = Catalog.Get("message_bottle");
            if (g.fx) Destroy(g.fx.gameObject);
            glimmers.Remove(g);
            p.MoveAboard(boat.helm, Activity.Helm);
            boat.Busy = false;
            Working = false;
            if (found == null) GameState.Say("Nothing but mud. Let out more chain next time!");
            else
            {
                GameState.SetFlag("dredged");
                GameState.Catch(found);
            }
        }

        public bool AnyNear(Vector3 p, float r) => Nearest(p, r) != null;
    }
}
