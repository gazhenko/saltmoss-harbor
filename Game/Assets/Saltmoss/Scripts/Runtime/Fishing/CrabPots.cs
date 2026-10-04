using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Crab pots, Deadliest-Catch style but cosy: drop a buoyed pot when the boat is slow, let it soak while you do
    /// other things (or overnight), then come back and haul it with the winch — keep the tension needle in the green
    /// as the boat heaves. Little crabs go back over the side; the keepers tumble onto the deck.
    /// </summary>
    public class CrabPots : MonoBehaviour
    {
        public static CrabPots I { get; private set; }
        public const float FillMinutes = 14f;      // game minutes per crab
        public static int OnDeck => GameState.PotCount - GameState.D.pots.Count;

        class Buoy { public PotState s; public Transform t; public Transform visual; }
        readonly List<Buoy> buoys = new List<Buoy>();
        public bool Hauling { get; private set; }
        static readonly Color[] colours = { new Color(0.85f, 0.3f, 0.2f), new Color(0.95f, 0.75f, 0.2f), new Color(0.25f, 0.55f, 0.85f), new Color(0.3f, 0.7f, 0.4f), new Color(0.85f, 0.45f, 0.75f), new Color(0.95f, 0.95f, 0.9f) };

        /// <summary>The buoy colour for a pot (as painted on its buoy), for the map.</summary>
        public static Color BuoyColour(int i) => colours[((i % colours.Length) + colours.Length) % colours.Length];

        void Awake() { I = this; }

        void Start() => Resync();

        /// <summary>Rebuild the buoys from the save (after New Game / Continue).</summary>
        public void Resync()
        {
            foreach (var b in buoys) if (b.t != null) Destroy(b.t.gameObject);
            buoys.Clear();
            foreach (var s in GameState.D.pots) SpawnBuoy(s);
        }

        void SpawnBuoy(PotState s)
        {
            var root = new GameObject("PotBuoy").transform;
            root.position = new Vector3(s.x, 0f, s.z);
            var vis = new GameObject("Visual").transform;
            vis.SetParent(root, false);
            vis.gameObject.AddComponent<ClayPuppet>();
            var m = ModelBank.I.Spawn("boat/buoy", root.position, Quaternion.Euler(0, Random.Range(0, 360f), 0), vis);
            var mpb = new MaterialPropertyBlock();
            foreach (var r in m.GetComponentsInChildren<Renderer>())
            {
                r.GetPropertyBlock(mpb);
                mpb.SetColor("_BaseColor", Color.Lerp(Color.white, colours[s.colour % colours.Length], 0.35f));
                r.SetPropertyBlock(mpb);
            }
            buoys.Add(new Buoy { s = s, t = root, visual = vis });
        }

        public PotState Nearest(Vector3 p, float range)
        {
            PotState best = null;
            float bd = range;
            foreach (var b in buoys)
            {
                float d = Vector3.Distance(new Vector3(p.x, 0, p.z), b.t.position);
                if (d < bd) { bd = d; best = b.s; }
            }
            return best;
        }

        public bool CanDrop(BoatController boat)
        {
            if (OnDeck <= 0 || boat.InHarbour || Mathf.Abs(boat.Speed) > 2.2f) return false;
            return Nearest(boat.transform.position, 14f) == null;
        }

        public static int Crabs(PotState s)
        {
            float soak = GameState.AbsMinutes - s.droppedAt;
            int max = s.zone == (int)Zone.Deep ? 9 : s.zone == (int)Zone.Kelp ? 8 : 6;
            return Mathf.Clamp(Mathf.FloorToInt(soak / FillMinutes), 0, max);
        }

        public void Drop(BoatController boat)
        {
            StartCoroutine(DropCo(boat));
        }

        IEnumerator DropCo(BoatController boat)
        {
            boat.Busy = true;
            var p = PlayerController.I;
            p.MoveAboard(boat.winch != null ? boat.winch : boat.helm, Activity.Haul);
            AudioDirector.Play("chain_rattle", boat.transform.position, 0.6f);
            yield return new WaitForSeconds(0.6f);
            var pos = boat.transform.position - boat.transform.right * 3.2f - boat.transform.forward * 1.5f;
            AudioDirector.Play("pot_drop", pos, 1f);
            SeaState.AddFoam(pos, 2.5f, 1f);
            for (int i = 0; i < 6; i++) CottonPuff.Emit(pos + Random.insideUnitSphere * 0.6f, Color.white, 0.5f, new Vector3(Random.Range(-1f, 1f), Random.Range(2f, 4f), Random.Range(-1f, 1f)), 0.9f);
            var s = new PotState { x = pos.x, z = pos.z, droppedAt = GameState.AbsMinutes, zone = (int)boat.ZoneAt(pos), colour = GameState.D.pots.Count };
            GameState.D.pots.Add(s);
            SpawnBuoy(s);
            GameState.Notify();
            yield return new WaitForSeconds(0.5f);
            p.MoveAboard(boat.helm, Activity.Helm);
            boat.Busy = false;
            if (!GameState.Flag("dropped_pot")) { GameState.SetFlag("dropped_pot"); GameState.Say("Pot's down! Give it a while to soak, then come back and haul it."); }
            else GameState.Say($"Pot dropped. {OnDeck} left on deck.");
            PotsVisual.Refresh();
        }

        public void Haul(BoatController boat, PotState s)
        {
            if (Hauling) return;
            StartCoroutine(HaulCo(boat, s));
        }

        IEnumerator HaulCo(BoatController boat, PotState s)
        {
            Hauling = true;
            boat.Busy = true;
            var p = PlayerController.I;
            p.MoveAboard(boat.winch != null ? boat.winch : boat.helm, Activity.Haul);
            var ui = MiniGameUI.Ensure();
            string key = GameInput.Label(Bind.UseTool);
            ui.Show("HAUL!", $"Hold {key} to winch — keep the needle in the green", "too tight", "slack");
            float rough = SeaState.I != null ? SeaState.I.Roughness01(boat.transform.position) : 0f;
            float width = (GameState.Has("winch") ? 0.3f : 0.22f) * (s.tangled ? 0.75f : 1f) * (1f - rough * 0.25f);
            float centre = 0.5f, tension = 0f, progress = 0f, t = 0f, groan = 0f;
            var winchAudio = gameObject.AddComponent<AudioSource>();
            winchAudio.clip = AudioDirector.Bank.Get("winch_loop");
            winchAudio.loop = true;
            winchAudio.volume = 0f;
            if (winchAudio.clip != null) winchAudio.Play();
            var drum = boat.model != null ? boat.model.Bone("winch") : null;
            while (progress < 1f)
            {
                float dt = Time.deltaTime;
                t += dt;
                // the boat heaves: the sweet spot rides up and down with the swell
                float drift = Mathf.Sin(t * (0.9f + rough * 1.6f)) * (0.12f + rough * 0.18f) + (Mathf.PerlinNoise(t * 0.7f, 3f) - 0.5f) * (0.1f + rough * 0.25f);
                centre = Mathf.Clamp(0.5f + drift, width * 0.5f + 0.02f, 1f - width * 0.5f - 0.02f);
                bool hold = GameInput.UseTool.IsPressed() || GameInput.Interact.IsPressed();
                tension = Mathf.MoveTowards(tension, hold ? 1f : 0f, dt * (hold ? 0.75f : 0.9f));
                bool inBand = Mathf.Abs(tension - centre) < width * 0.5f;
                if (inBand) progress += dt * 0.17f;
                if (tension > centre + width * 0.5f + 0.15f)
                {
                    groan -= dt;
                    if (groan <= 0f) { AudioDirector.Play("winch_strain", boat.transform.position, 0.8f); groan = 1.2f; GameInput.Impulse(0.3f, 0.2f, 0.2f); }
                }
                winchAudio.volume = (hold ? 0.6f : 0.15f) * Settings.Sfx;
                winchAudio.pitch = inBand ? 1f : 0.85f;
                if (drum != null && hold) drum.localRotation *= Quaternion.Euler(dt * 360f, 0, 0);
                p.anim.activityPhase = Mathf.Repeat(t * (hold ? 1.4f : 0.3f), 1f);
                ui.Set(centre, width, tension, progress, inBand);
                if (GameInput.Pause.WasPressedThisFrame()) break;
                yield return null;
            }
            Destroy(winchAudio);
            ui.Hide();
            // up she comes
            var pos = new Vector3(s.x, 0f, s.z);
            AudioDirector.Play("pot_surface", boat.transform.position, 1f);
            SeaState.AddFoam(pos, 3f, 1f);
            for (int i = 0; i < 8; i++) CottonPuff.Emit(boat.transform.position - boat.transform.right * 3f + Random.insideUnitSphere, Color.white, 0.45f, new Vector3(Random.Range(-1f, 1f), Random.Range(1.5f, 3.5f), Random.Range(-1f, 1f)), 1f);
            yield return new WaitForSeconds(0.5f);
            AudioDirector.Play("crab_clatter", boat.transform.position, 1f);
            // roll the catch
            int n = Crabs(s);
            var rng = new System.Random((int)(s.droppedAt * 13 + s.x));
            var tally = new Dictionary<string, int>();
            int tossed = 0;
            var firsts = new List<ItemDef>();
            bool night = DayCycle.I != null && DayCycle.I.IsNight;
            for (int i = 0; i < n; i++)
            {
                if (rng.NextDouble() < 0.18) { tossed++; continue; }   // too little: back it goes
                var d = Catalog.Roll(Kind.Crab, (Zone)s.zone, night, GameState.D.weather >= (int)Weather.Squalls ? 1f : 0f, rng, GameState.D.restoration * 0.3f);
                if (d == null) continue;
                if (rng.NextDouble() < 0.06) d = Catalog.Roll(Kind.Junk, (Zone)s.zone, night, 0f, rng);
                bool first = !GameState.D.discovered.Contains(d.id);
                if (!GameState.Catch(d)) break;   // hold full
                if (first || d.rare) firsts.Add(d);
                tally[d.id] = tally.TryGetValue(d.id, out var c) ? c + 1 : 1;
            }
            GameState.D.pots.Remove(s);
            var b = buoys.Find(x => x.s == s);
            if (b != null) { Destroy(b.t.gameObject); buoys.Remove(b); }
            GameState.Notify();
            PotsVisual.Refresh();
            DeckCatch.Spill(boat, tally);
            if (tally.Count == 0) GameState.Say(n == 0 ? "Empty! It needed longer to soak." : "Only little ones — all tossed back. Good steward!");
            else
            {
                var parts = new List<string>();
                foreach (var kv in tally) parts.Add($"{kv.Value} {Catalog.Get(kv.Key).name}");
                GameState.Say("Hauled " + string.Join(", ", parts) + (tossed > 0 ? $" · {tossed} little ones tossed back" : ""));
                AudioDirector.I?.Jingle(n >= 6 ? "jingle_catch_big" : "jingle_catch_small");
            }
            if (!GameState.Flag("hauled_pot")) GameState.SetFlag("hauled_pot");
            p.MoveAboard(boat.helm, Activity.Helm);
            boat.Busy = false;
            Hauling = false;
        }

        void Update()
        {
            if (!ClayClock.SteppedThisFrame || SeaState.I == null) return;
            foreach (var b in buoys)
            {
                var pos = b.t.position;
                float h = SeaState.I.HeightAt(pos.x, pos.z, out var n);
                b.visual.GetComponent<ClayPuppet>().offsetPos = new Vector3(0f, h, 0f);
                b.visual.GetComponent<ClayPuppet>().offsetRot = Quaternion.FromToRotation(Vector3.up, Vector3.Lerp(Vector3.up, n, 0.8f));
                SeaState.AddFoam(pos, 0.9f, 0.6f);
            }
        }
    }
}
