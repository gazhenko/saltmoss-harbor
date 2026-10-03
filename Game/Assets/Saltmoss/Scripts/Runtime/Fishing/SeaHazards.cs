using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// The drama: rogue waves in rough weather (warned by a horn and an arrow — take them on the bow or the engine
    /// sputters and the pots tangle) and icing in the Grey Deep (lumps of ice build up on the rails and slow the
    /// Sally Mae until Pip knocks them off with the mallet). Nothing is ever lost for good.
    /// </summary>
    public class SeaHazards : MonoBehaviour
    {
        public static SeaHazards I { get; private set; }
        float waveTimer = 60f;
        public bool WaveIncoming { get; private set; }
        public Vector3 WaveDir { get; private set; }
        readonly List<GameObject> iceLumps = new List<GameObject>();
        public bool Chipping { get; private set; }

        void Awake() { I = this; }

        void Update()
        {
            var boat = BoatController.I;
            if (boat == null || SeaState.I == null) return;
            bool atSea = boat.Aboard && !boat.Docked && !boat.InHarbour;
            var D = GameState.D;
            float rough = SeaState.I.Roughness01(boat.transform.position);
            bool stormy = D.weather >= (int)Weather.Squalls;
            SeaState.I.storm = Mathf.MoveTowards(SeaState.I.storm, D.weather == (int)Weather.Storm ? 1f : D.weather == (int)Weather.Squalls ? 0.6f : D.weather == (int)Weather.Showers ? 0.25f : 0.05f, Time.deltaTime * 0.05f);

            // rogue waves
            if (atSea && !WaveIncoming && rough > 0.45f && (stormy || rough > 0.7f))
            {
                waveTimer -= Time.deltaTime;
                if (waveTimer <= 0f) StartCoroutine(Rogue(boat));
            }
            else if (!atSea) waveTimer = Random.Range(40f, 70f);

            // ice in the Grey Deep, faster in fog/storm and at night
            if (atSea && boat.CurrentZone == Zone.Deep)
            {
                float rate = (stormy ? 1.6f : 1f) * (D.weather == (int)Weather.Fog ? 1.4f : 1f) * (DayCycle.I != null && DayCycle.I.IsNight ? 1.4f : 1f) * (GameState.Has("hull") ? 0.6f : 1f);
                boat.Ice = Mathf.Min(1f, boat.Ice + Time.deltaTime * rate / 150f);
                if (!GameState.Flag("ice_tip") && boat.Ice > 0.3f) { GameState.SetFlag("ice_tip"); GameState.Say("Ice is building on the rails! Knock it off before she gets sluggish."); }
            }
            else if (!atSea || boat.CurrentZone != Zone.Deep) boat.Ice = Mathf.Max(0f, boat.Ice - Time.deltaTime / (boat.Docked ? 10f : 90f));
            UpdateIceLumps(boat);
        }

        IEnumerator Rogue(BoatController boat)
        {
            WaveIncoming = true;
            // from somewhere off the bow or beam, never dead astern
            float ang = Random.Range(-110f, 110f);
            var from = Quaternion.Euler(0, boat.transform.eulerAngles.y + ang, 0) * Vector3.forward;
            WaveDir = -from;
            string side = Mathf.Abs(ang) < 30f ? "dead ahead" : ang > 0 ? "off the starboard bow" : "off the port bow";
            AudioDirector.Play("foghorn", boat.transform.position, 0.8f, 0f);
            GameState.Say($"ROGUE WAVE {side}! Turn into it!");
            GameInput.Impulse(0.2f, 0.1f, 0.4f);
            float warn = 5f;
            while (warn > 0f)
            {
                warn -= Time.deltaTime;
                var ahead = boat.transform.position + from * Mathf.Lerp(12f, 60f, warn / 5f);
                if (ClayClock.SteppedThisFrame)
                    for (int i = -3; i <= 3; i++) SeaState.AddFoam(ahead + Vector3.Cross(Vector3.up, from) * i * 4f, 3.2f, 1f);
                HUD.ActionPrompt = "Turn into the wave!";
                HUD.ActionKey = "Run";
                yield return null;
            }
            float facing = Vector3.Angle(boat.transform.forward, from);
            AudioDirector.Play("wave_crash_big", boat.transform.position, 1f, 0f);
            for (int i = 0; i < 18; i++)
                CottonPuff.Emit(boat.transform.position + from * 3f + Random.insideUnitSphere * 2.5f, Color.white, 0.8f, new Vector3(Random.Range(-2f, 2f), Random.Range(3f, 7f), Random.Range(-2f, 2f)) - from * 2f, 1.3f);
            if (boat.puppet != null) boat.puppet.offsetRot *= Quaternion.Euler(facing < 40f ? -14f : 0f, 0, facing < 40f ? 0f : (Vector3.Dot(boat.transform.right, from) > 0 ? -18f : 18f));
            if (facing < 40f || (GameState.Has("hull") && facing < 60f))
            {
                GameState.Say("Took it on the bow! Nice seamanship!");
                GameInput.Impulse(0.6f, 0.3f, 0.5f);
            }
            else
            {
                boat.Sputter = GameState.Has("hull") ? 2.5f : 5f;
                foreach (var p in GameState.D.pots) p.tangled = true;
                GameState.Say("Whoa! Caught side-on — the engine's coughing and the pot lines got tangled.");
                GameInput.Impulse(1f, 0.8f, 0.8f);
                AudioDirector.Play("hull_creak", boat.transform.position, 1f);
            }
            WaveIncoming = false;
            waveTimer = Random.Range(45f, 90f);
        }

        void UpdateIceLumps(BoatController boat)
        {
            if (!ClayClock.SteppedThisFrame || boat.model == null) return;
            int want = Mathf.RoundToInt(boat.Ice * 14f);
            var deck = boat.puppet != null ? boat.puppet.transform : boat.transform;
            while (iceLumps.Count < want)
            {
                int k = iceLumps.Count;
                var go = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                Destroy(go.GetComponent<Collider>());
                go.name = "Ice";
                go.transform.SetParent(deck, false);
                float side = k % 2 == 0 ? 1f : -1f;
                go.transform.localPosition = new Vector3(side * Random.Range(1.3f, 1.55f), Random.Range(1.2f, 1.5f), Random.Range(-3.5f, 3f));
                go.transform.localScale = new Vector3(Random.Range(0.25f, 0.5f), Random.Range(0.2f, 0.35f), Random.Range(0.3f, 0.6f));
                var mat = Resources.Load<Material>("Ice");
                if (mat != null) go.GetComponent<Renderer>().sharedMaterial = mat;
                iceLumps.Add(go);
            }
            while (iceLumps.Count > want)
            {
                var g = iceLumps[iceLumps.Count - 1];
                iceLumps.RemoveAt(iceLumps.Count - 1);
                Destroy(g);
            }
        }

        public bool CanChip(BoatController boat) => !Chipping && boat.Ice > 0.2f && Mathf.Abs(boat.Speed) < 2f;

        public void Chip(BoatController boat) => StartCoroutine(ChipCo(boat));

        IEnumerator ChipCo(BoatController boat)
        {
            Chipping = true;
            boat.Busy = true;
            var p = PlayerController.I;
            p.MoveAboard(boat.rail != null ? boat.rail : boat.helm, Activity.Hammer);
            var ui = MiniGameUI.Ensure();
            string key = GameInput.Label(Bind.Interact);
            ui.Show("ICE!", $"Tap {key} to swing the mallet", "", "");
            float swing = 0f;
            while (boat.Ice > 0.02f)
            {
                swing = Mathf.MoveTowards(swing, 0f, Time.deltaTime * 3f);
                p.anim.activityPhase = 1f - swing;
                if (GameInput.Interact.WasPressedThisFrame() || GameInput.UseTool.WasPressedThisFrame())
                {
                    swing = 1f;
                    boat.Ice = Mathf.Max(0f, boat.Ice - (GameState.Has("hull") ? 0.14f : 0.1f));
                    AudioDirector.Play("ice_hammer", boat.transform.position, 0.9f);
                    AudioDirector.Play("ice_crack", boat.transform.position, 0.6f);
                    GameInput.Impulse(0.3f, 0.5f, 0.12f);
                    var rail = boat.rail != null ? boat.rail.position : boat.transform.position;
                    for (int i = 0; i < 3; i++) CottonPuff.Emit(rail + Random.insideUnitSphere * 0.4f + Vector3.up * 0.5f, new Color(0.85f, 0.93f, 1f), 0.22f, new Vector3(Random.Range(-1.5f, 1.5f), Random.Range(1f, 2.5f), Random.Range(-1.5f, 1.5f)), 0.6f);
                }
                ui.Set(0f, 0f, swing, 1f - boat.Ice, false);
                if (GameInput.Pause.WasPressedThisFrame()) break;
                yield return null;
            }
            ui.Hide();
            if (boat.Ice <= 0.02f) GameState.Say("Ice cleared! She's light as a gull again.");
            p.MoveAboard(boat.helm, Activity.Helm);
            boat.Busy = false;
            Chipping = false;
        }
    }
}
